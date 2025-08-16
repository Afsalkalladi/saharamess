import hashlib
import hmac
import json
import qrcode
from io import BytesIO
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional
import logging

from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from .models import Student, Payment, MessCut, MessClosure, ScanEvent, Settings, DLQLog

logger = logging.getLogger(__name__)


class QRService:
    """Service for QR code generation and verification."""
    
    @classmethod
    def generate_qr_payload(cls, student: Student) -> str:
        """Generate QR payload with HMAC signature."""
        settings_obj = Settings.get_settings()
        
        # Create payload
        issued_at = int(timezone.now().timestamp())
        payload_data = {
            'v': settings_obj.qr_secret_version,
            'student_id': str(student.id),
            'issued_at': issued_at,
            'nonce': student.qr_nonce
        }
        
        # Create message for HMAC
        message = f"{payload_data['v']}|{payload_data['student_id']}|{payload_data['issued_at']}|{payload_data['nonce']}"
        
        # Generate HMAC
        secret = settings.QR_SECRET.encode('utf-8')
        signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Final payload
        return f"{message}|{signature}"
    
    @classmethod
    def verify_qr_code(cls, qr_data: str) -> Optional[str]:
        """Verify QR code and return student ID if valid."""
        try:
            parts = qr_data.split('|')
            if len(parts) != 5:
                return None
            
            version, student_id, issued_at, nonce, signature = parts
            
            # Check version
            settings_obj = Settings.get_settings()
            if int(version) != settings_obj.qr_secret_version:
                logger.warning(f"QR version mismatch: {version} vs {settings_obj.qr_secret_version}")
                return None
            
            # Verify HMAC
            message = f"{version}|{student_id}|{issued_at}|{nonce}"
            secret = settings.QR_SECRET.encode('utf-8')
            expected_signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning(f"QR signature verification failed for student {student_id}")
                return None
            
            # Verify student exists and QR matches
            try:
                student = Student.objects.get(id=student_id, qr_nonce=nonce, qr_version=int(version))
                return str(student.id)
            except Student.DoesNotExist:
                logger.warning(f"Student not found or QR data mismatch: {student_id}")
                return None
                
        except (ValueError, IndexError) as e:
            logger.error(f"QR parsing error: {str(e)}")
            return None
    
    @classmethod
    def generate_qr_for_student(cls, student: Student) -> BytesIO:
        """Generate QR code image for student."""
        payload = cls.generate_qr_payload(student)
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to BytesIO
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return img_io


class MessService:
    """Service for mess-related business logic."""
    
    @classmethod
    def check_meal_access(cls, student: Student, meal: str) -> Dict[str, Any]:
        """Check if student can access meal."""
        today = timezone.now().date()
        
        # Check student status
        if student.status != Student.Status.APPROVED:
            return {
                'result': ScanEvent.Result.BLOCKED_STATUS,
                'reason': 'Student not approved'
            }
        
        # Check payment
        valid_payment = cls.get_valid_payment_for_date(student, today)
        if not valid_payment:
            return {
                'result': ScanEvent.Result.BLOCKED_NO_PAYMENT,
                'reason': 'No valid payment for current period'
            }
        
        # Check mess cut
        if cls.is_student_cut_for_date(student, today):
            return {
                'result': ScanEvent.Result.BLOCKED_CUT,
                'reason': 'Student has mess cut for today'
            }
        
        # Check mess closure
        if cls.is_mess_closed_for_date(today):
            return {
                'result': ScanEvent.Result.BLOCKED_CUT,
                'reason': 'Mess is closed today'
            }
        
        return {
            'result': ScanEvent.Result.ALLOWED,
            'reason': 'Access granted'
        }
    
    @classmethod
    def get_valid_payment_for_date(cls, student: Student, date) -> Optional[Payment]:
        """Get valid payment for given date."""
        return Payment.objects.filter(
            student=student,
            status=Payment.Status.VERIFIED,
            cycle_start__lte=date,
            cycle_end__gte=date
        ).first()
    
    @classmethod
    def is_student_cut_for_date(cls, student: Student, date) -> bool:
        """Check if student has mess cut for given date."""
        return MessCut.objects.filter(
            student=student,
            from_date__lte=date,
            to_date__gte=date
        ).exists()
    
    @classmethod
    def is_mess_closed_for_date(cls, date) -> bool:
        """Check if mess is closed for given date."""
        return MessClosure.objects.filter(
            from_date__lte=date,
            to_date__gte=date
        ).exists()
    
    @classmethod
    def get_student_snapshot(cls, student: Student) -> Dict[str, Any]:
        """Get student snapshot for display."""
        today = timezone.now().date()
        
        # Check payment status
        valid_payment = cls.get_valid_payment_for_date(student, today)
        payment_ok = valid_payment is not None
        
        # Check mess cut
        today_cut = cls.is_student_cut_for_date(student, today)
        
        # Check mess closure
        closure_today = cls.is_mess_closed_for_date(today)
        
        # Overall status
        if student.status != Student.Status.APPROVED:
            overall_status = "NOT_APPROVED"
        elif not payment_ok:
            overall_status = "NO_PAYMENT"
        elif today_cut or closure_today:
            overall_status = "CUT_OR_CLOSED"
        else:
            overall_status = "ALLOWED"
        
        return {
            'id': student.id,
            'name': student.name,
            'roll_no': student.roll_no,
            'room_no': student.room_no,
            'status': student.status,
            'payment_ok': payment_ok,
            'today_cut': today_cut,
            'closure_today': closure_today,
            'overall_status': overall_status
        }
    
    @classmethod
    def check_cutoff_rule(cls, target_date) -> bool:
        """Check if cutoff rule allows mess cut for target date."""
        now = timezone.now()
        cutoff_time = time(23, 0)  # 11:00 PM
        
        # If it's past cutoff, minimum target is day after tomorrow
        if now.time() >= cutoff_time:
            min_date = (now + timedelta(days=2)).date()
        else:
            min_date = (now + timedelta(days=1)).date()
        
        return target_date >= min_date
    
    @classmethod
    def get_current_meal_window(cls) -> Optional[str]:
        """Get current meal based on time."""
        now = timezone.now().time()
        
        # Default meal windows
        windows = settings.DEFAULT_MEAL_WINDOWS
        
        for meal, window in windows.items():
            start_time = datetime.strptime(window['start'], '%H:%M').time()
            end_time = datetime.strptime(window['end'], '%H:%M').time()
            
            if start_time <= now <= end_time:
                return meal
        
        return None
    
    @classmethod
    def generate_payment_report(cls, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate payment status report."""
        queryset = Payment.objects.select_related('student')
        
        # Apply filters
        if 'status' in filters:
            status_map = {
                'verified': Payment.Status.VERIFIED,
                'uploaded': Payment.Status.UPLOADED,
                'denied': Payment.Status.DENIED,
            }
            if filters['status'] in status_map:
                queryset = queryset.filter(status=status_map[filters['status']])
            elif filters['status'] == 'not_uploaded':
                # Students without uploaded payments
                uploaded_student_ids = Payment.objects.filter(
                    status__in=[Payment.Status.UPLOADED, Payment.Status.VERIFIED]
                ).values_list('student_id', flat=True)
                students_without_payment = Student.objects.exclude(id__in=uploaded_student_ids)
                return {
                    'type': 'students_without_payment',
                    'count': students_without_payment.count(),
                    'students': [
                        {
                            'id': str(s.id),
                            'name': s.name,
                            'roll_no': s.roll_no,
                            'status': s.status
                        }
                        for s in students_without_payment[:100]
                    ]
                }
        
        if 'from_date' in filters:
            queryset = queryset.filter(cycle_start__gte=filters['from_date'])
        
        if 'to_date' in filters:
            queryset = queryset.filter(cycle_end__lte=filters['to_date'])
        
        # Generate summary
        total_count = queryset.count()
        
        status_counts = {
            'verified': queryset.filter(status=Payment.Status.VERIFIED).count(),
            'uploaded': queryset.filter(status=Payment.Status.UPLOADED).count(),
            'denied': queryset.filter(status=Payment.Status.DENIED).count(),
        }
        
        recent_payments = queryset.order_by('-created_at')[:50]
        
        return {
            'type': 'payment_summary',
            'total_count': total_count,
            'status_counts': status_counts,
            'recent_payments': [
                {
                    'id': str(p.id),
                    'student_name': p.student.name,
                    'student_roll': p.student.roll_no,
                    'amount': float(p.amount),
                    'cycle_start': p.cycle_start.isoformat(),
                    'cycle_end': p.cycle_end.isoformat(),
                    'status': p.status,
                    'created_at': p.created_at.isoformat()
                }
                for p in recent_payments
            ]
        }
    
    @classmethod
    def generate_mess_cut_report(cls, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mess cut report."""
        queryset = MessCut.objects.select_related('student')
        
        # Apply filters
        if 'from_date' in filters:
            queryset = queryset.filter(from_date__gte=filters['from_date'])
        
        if 'to_date' in filters:
            queryset = queryset.filter(to_date__lte=filters['to_date'])
        
        if 'student_id' in filters:
            queryset = queryset.filter(student_id=filters['student_id'])
        
        # Generate summary
        total_count = queryset.count()
        
        # Upcoming cuts (next 7 days)
        today = timezone.now().date()
        upcoming_cuts = queryset.filter(
            from_date__gte=today,
            from_date__lte=today + timedelta(days=7)
        ).order_by('from_date')
        
        # Group by date
        cuts_by_date = {}
        for cut in upcoming_cuts:
            date_str = cut.from_date.isoformat()
            if date_str not in cuts_by_date:
                cuts_by_date[date_str] = []
            
            cuts_by_date[date_str].append({
                'id': str(cut.id),
                'student_name': cut.student.name,
                'student_roll': cut.student.roll_no,
                'from_date': cut.from_date.isoformat(),
                'to_date': cut.to_date.isoformat(),
                'applied_at': cut.applied_at.isoformat()
            })
        
        return {
            'total_count': total_count,
            'upcoming_cuts_by_date': cuts_by_date,
            'summary_period': {
                'from_date': filters.get('from_date', today - timedelta(days=30)),
                'to_date': filters.get('to_date', today + timedelta(days=30))
            }
        }


class NotificationService:
    """Service for sending notifications via Telegram."""
    
    @classmethod
    async def send_approval_notification(cls, student: Student):
        """Send approval notification to student."""
        from .telegram_bot import bot_instance
        
        message = (
            f"✅ **Registration Approved!**\n\n"
            f"Congratulations {student.name}! Your mess access is now active.\n\n"
            f"Here's your permanent QR code. Use /start to access all features."
        )
        
        try:
            # Send QR code with approval message
            qr_image = QRService.generate_qr_for_student(student)
            await bot_instance.application.bot.send_photo(
                chat_id=student.tg_user_id,
                photo=qr_image,
                caption=message
            )
        except Exception as e:
            logger.error(f"Failed to send approval notification to {student.tg_user_id}: {str(e)}")
    
    @classmethod
    async def send_denial_notification(cls, student: Student):
        """Send denial notification to student."""
        from .telegram_bot import bot_instance
        
        message = (
            f"❌ **Registration Denied**\n\n"
            f"Sorry {student.name}, your registration could not be approved.\n\n"
            f"Please contact the mess admin if you believe this is an error."
        )
        
        try:
            await bot_instance.application.bot.send_message(
                chat_id=student.tg_user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Failed to send denial notification to {student.tg_user_id}: {str(e)}")
    
    @classmethod
    async def send_payment_verified_notification(cls, payment: Payment):
        """Send payment verified notification."""
        from .telegram_bot import bot_instance
        
        message = (
            f"✅ **Payment Verified!**\n\n"
            f"Your payment has been verified for the period:\n"
            f"📅 {payment.cycle_start} to {payment.cycle_end}\n"
            f"💰 Amount: ₹{payment.amount}\n\n"
            f"You can now access meals during this period."
        )
        
        try:
            await bot_instance.application.bot.send_message(
                chat_id=payment.student.tg_user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Failed to send payment verified notification: {str(e)}")
    
    @classmethod
    async def send_payment_denied_notification(cls, payment: Payment):
        """Send payment denied notification."""
        from .telegram_bot import bot_instance
        
        message = (
            f"⚠️ **Payment Could Not Be Verified**\n\n"
            f"Your payment screenshot for the period {payment.cycle_start} to {payment.cycle_end} "
            f"could not be verified.\n\n"
            f"Please upload a clearer screenshot or contact the admin."
        )
        
        try:
            await bot_instance.application.bot.send_message(
                chat_id=payment.student.tg_user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Failed to send payment denied notification: {str(e)}")
    
    @classmethod
    async def send_mess_cut_confirmation(cls, mess_cut: MessCut):
        """Send mess cut confirmation."""
        from .telegram_bot import bot_instance
        
        duration = (mess_cut.to_date - mess_cut.from_date).days + 1
        
        message = (
            f"✂️ **Mess Cut Confirmed**\n\n"
            f"From: {mess_cut.from_date}\n"
            f"To: {mess_cut.to_date}\n"
            f"Duration: {duration} days\n\n"
            f"Your mess cut has been successfully applied. "
            f"You won't be charged for these days."
        )
        
        try:
            await bot_instance.application.bot.send_message(
                chat_id=mess_cut.student.tg_user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Failed to send mess cut confirmation: {str(e)}")
    
    @classmethod
    async def send_scan_notification(cls, student: Student, meal: str):
        """Send QR scan notification."""
        from .telegram_bot import bot_instance
        
        now = timezone.now()
        meal_emoji = {
            'BREAKFAST': '🍳',
            'LUNCH': '🍽️',
            'DINNER': '🍽️'
        }
        
        message = (
            f"🍽️ **QR Scanned**\n\n"
            f"{meal_emoji.get(meal, '🍽️')} {meal.title()} access granted\n"
            f"⏰ Time: {now.strftime('%H:%M')}\n"
            f"📅 Date: {now.strftime('%Y-%m-%d')}\n\n"
            f"Bon appétit, {student.name}!"
        )
        
        try:
            await bot_instance.application.bot.send_message(
                chat_id=student.tg_user_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Failed to send scan notification: {str(e)}")
    
    @classmethod
    async def broadcast_mess_closure(cls, closure: MessClosure):
        """Broadcast mess closure to all students."""
        from .telegram_bot import bot_instance
        
        duration = (closure.to_date - closure.from_date).days + 1
        reason_text = f"\n\nReason: {closure.reason}" if closure.reason else ""
        
        message = (
            f"📢 **Mess Closure Notice**\n\n"
            f"The mess will be closed from:\n"
            f"📅 {closure.from_date} to {closure.to_date}\n"
            f"Duration: {duration} days{reason_text}\n\n"
            f"You won't be charged for these days. No action needed."
        )
        
        # Get all approved students
        students = Student.objects.filter(status=Student.Status.APPROVED)
        
        for student in students:
            try:
                await bot_instance.application.bot.send_message(
                    chat_id=student.tg_user_id,
                    text=message
                )
            except Exception as e:
                logger.error(f"Failed to notify student {student.tg_user_id} about closure: {str(e)}")
    
    @classmethod
    async def notify_admins_new_registration(cls, student: Student):
        """Notify admins of new registration."""
        from .telegram_bot import bot_instance
        
        message = (
            f"📝 **New Registration**\n\n"
            f"Name: {student.name}\n"
            f"Roll: {student.roll_no}\n"
            f"Room: {student.room_no}\n"
            f"Phone: {student.phone}\n"
            f"Telegram ID: {student.tg_user_id}\n\n"
            f"Use the admin panel to approve/deny."
        )
        
        for admin_id in settings.ADMIN_TG_IDS:
            try:
                await bot_instance.application.bot.send_message(
                    chat_id=admin_id,
                    text=message
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")
    
    @classmethod
    async def notify_admins_payment_upload(cls, payment: Payment):
        """Notify admins of payment upload."""
        from .telegram_bot import bot_instance
        
        message = (
            f"💳 **Payment Upload**\n\n"
            f"Student: {payment.student.name} ({payment.student.roll_no})\n"
            f"Period: {payment.cycle_start} to {payment.cycle_end}\n"
            f"Amount: ₹{payment.amount}\n\n"
            f"Use the admin panel to verify/deny."
        )
        
        for admin_id in settings.ADMIN_TG_IDS:
            try:
                await bot_instance.application.bot.send_message(
                    chat_id=admin_id,
                    text=message
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")


class SheetsService:
    """Service for Google Sheets backup logging."""
    
    @classmethod
    def log_registration_event(cls, student: Student, event_type: str):
        """Log registration event to Google Sheets."""
        data = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'student_id': str(student.id),
            'student_name': student.name,
            'roll_no': student.roll_no,
            'status': student.status
        }
        cls._enqueue_sheets_operation('registrations', data)
    
    @classmethod
    def log_payment_event(cls, payment: Payment, event_type: str):
        """Log payment event to Google Sheets."""
        data = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'payment_id': str(payment.id),
            'student_id': str(payment.student.id),
            'student_name': payment.student.name,
            'roll_no': payment.student.roll_no,
            'cycle_start': payment.cycle_start.isoformat(),
            'cycle_end': payment.cycle_end.isoformat(),
            'amount': float(payment.amount),
            'status': payment.status,
            'source': payment.source
        }
        cls._enqueue_sheets_operation('payments', data)
    
    @classmethod
    def log_mess_cut_event(cls, mess_cut: MessCut, event_type: str):
        """Log mess cut event to Google Sheets."""
        data = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'mess_cut_id': str(mess_cut.id),
            'student_id': str(mess_cut.student.id),
            'student_name': mess_cut.student.name,
            'roll_no': mess_cut.student.roll_no,
            'from_date': mess_cut.from_date.isoformat(),
            'to_date': mess_cut.to_date.isoformat(),
            'applied_by': mess_cut.applied_by
        }
        cls._enqueue_sheets_operation('mess_cuts', data)
    
    @classmethod
    def log_mess_closure_event(cls, closure: MessClosure, event_type: str):
        """Log mess closure event to Google Sheets."""
        data = {
            'timestamp': timezone.now().isoformat(),
            'event_type': event_type,
            'closure_id': str(closure.id),
            'from_date': closure.from_date.isoformat(),
            'to_date': closure.to_date.isoformat(),
            'reason': closure.reason,
            'created_by_admin_id': closure.created_by_admin_id
        }
        cls._enqueue_sheets_operation('mess_closures', data)
    
    @classmethod
    def log_scan_event(cls, scan_event: ScanEvent):
        """Log scan event to Google Sheets."""
        data = {
            'timestamp': scan_event.scanned_at.isoformat(),
            'scan_id': str(scan_event.id),
            'student_id': str(scan_event.student.id),
            'student_name': scan_event.student.name,
            'roll_no': scan_event.student.roll_no,
            'meal': scan_event.meal,
            'result': scan_event.result,
            'device_info': scan_event.device_info
        }
        cls._enqueue_sheets_operation('scan_events', data)
    
    @classmethod
    def _enqueue_sheets_operation(cls, sheet_name: str, data: Dict[str, Any]):
        """Enqueue operation for background processing."""
        try:
            from integrations.tasks import process_sheets_log
            process_sheets_log(sheet_name, data)
        except Exception as e:
            # Fallback to DLQ
            logger.error(f"Failed to enqueue sheets operation: {str(e)}")
            DLQLog.objects.create(
                operation=f"log_to_{sheet_name}",
                payload=data,
                error_message=str(e)
            )