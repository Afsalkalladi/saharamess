from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
import logging
import uuid

from .models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog
from .exceptions import ValidationError
from notifications.telegram import sync_send_message, sync_notify_registration_pending
from integrations.google_sheets import sheets_service

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Student)
def student_post_save(sender, instance, created, **kwargs):
    """Handle student creation and updates."""
    
    if created:
        # Generate QR nonce if not present
        if not instance.qr_nonce:
            instance.qr_nonce = uuid.uuid4().hex[:12]
            instance.save(update_fields=['qr_nonce'])
        
        # Log to Google Sheets
        try:
            data = {
                'timestamp': instance.created_at.isoformat(),
                'event_type': 'STUDENT_CREATED',
                'student_id': str(instance.id),
                'student_name': instance.name,
                'roll_no': instance.roll_no,
                'room_no': instance.room_no,
                'phone': instance.phone,
                'status': instance.status,
                'tg_user_id': str(instance.tg_user_id)
            }
            sheets_service.append_data('registrations', data)
        except Exception as e:
            logger.error(f"Failed to log student creation to sheets: {str(e)}")
        
        # Notify admins about new registration
        if instance.status == Student.Status.PENDING:
            try:
                student_data = {
                    'name': instance.name,
                    'roll_no': instance.roll_no,
                    'room_no': instance.room_no,
                    'phone': instance.phone,
                    'tg_user_id': instance.tg_user_id,
                    'created_at': instance.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                sync_notify_registration_pending(student_data)
            except Exception as e:
                logger.error(f"Failed to notify admins about new registration: {str(e)}")
    
    else:
        # Log status changes
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            try:
                data = {
                    'timestamp': timezone.now().isoformat(),
                    'event_type': 'STUDENT_STATUS_CHANGED',
                    'student_id': str(instance.id),
                    'student_name': instance.name,
                    'roll_no': instance.roll_no,
                    'old_status': instance._original_status,
                    'new_status': instance.status
                }
                sheets_service.append_data('registrations', data)
            except Exception as e:
                logger.error(f"Failed to log status change to sheets: {str(e)}")


@receiver(pre_save, sender=Student)
def student_pre_save(sender, instance, **kwargs):
    """Handle student pre-save operations."""
    
    # Store original status for comparison
    if instance.pk:
        try:
            original = Student.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Student.DoesNotExist:
            instance._original_status = None
    
    # Validate unique constraints
    if instance.pk:
        # Check for duplicate roll number
        duplicate_roll = Student.objects.filter(
            roll_no=instance.roll_no
        ).exclude(pk=instance.pk).first()
        
        if duplicate_roll:
            raise ValidationError(f"Roll number {instance.roll_no} is already registered")
        
        # Check for duplicate telegram ID
        duplicate_tg = Student.objects.filter(
            tg_user_id=instance.tg_user_id
        ).exclude(pk=instance.pk).first()
        
        if duplicate_tg:
            raise ValidationError(f"Telegram user ID {instance.tg_user_id} is already registered")


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """Handle payment creation and updates."""
    
    if created:
        # Log to Google Sheets
        try:
            data = {
                'timestamp': instance.created_at.isoformat(),
                'event_type': 'PAYMENT_CREATED',
                'payment_id': str(instance.id),
                'student_id': str(instance.student.id),
                'student_name': instance.student.name,
                'roll_no': instance.student.roll_no,
                'cycle_start': instance.cycle_start.isoformat(),
                'cycle_end': instance.cycle_end.isoformat(),
                'amount': float(instance.amount),
                'status': instance.status,
                'source': instance.source,
                'screenshot_url': instance.screenshot_url or ''
            }
            sheets_service.append_data('payments', data)
        except Exception as e:
            logger.error(f"Failed to log payment creation to sheets: {str(e)}")
    
    else:
        # Log status changes
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            try:
                data = {
                    'timestamp': timezone.now().isoformat(),
                    'event_type': 'PAYMENT_STATUS_CHANGED',
                    'payment_id': str(instance.id),
                    'student_id': str(instance.student.id),
                    'student_name': instance.student.name,
                    'roll_no': instance.student.roll_no,
                    'old_status': instance._original_status,
                    'new_status': instance.status,
                    'reviewer_admin_id': instance.reviewer_admin_id
                }
                sheets_service.append_data('payments', data)
            except Exception as e:
                logger.error(f"Failed to log payment status change to sheets: {str(e)}")


@receiver(pre_save, sender=Payment)
def payment_pre_save(sender, instance, **kwargs):
    """Handle payment pre-save operations."""
    
    # Store original status for comparison
    if instance.pk:
        try:
            original = Payment.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Payment.DoesNotExist:
            instance._original_status = None
    
    # Validate cycle dates
    if instance.cycle_start >= instance.cycle_end:
        raise ValidationError("Cycle start date must be before end date")
    
    # Check for overlapping payments for the same student
    if instance.pk:
        overlapping = Payment.objects.filter(
            student=instance.student,
            cycle_start__lt=instance.cycle_end,
            cycle_end__gt=instance.cycle_start,
            status__in=[Payment.Status.UPLOADED, Payment.Status.VERIFIED]
        ).exclude(pk=instance.pk)
        
        if overlapping.exists():
            raise ValidationError("Payment cycle overlaps with existing payment")


@receiver(post_save, sender=MessCut)
def mess_cut_post_save(sender, instance, created, **kwargs):
    """Handle mess cut creation."""
    
    if created:
        # Log to Google Sheets
        try:
            data = {
                'timestamp': instance.applied_at.isoformat(),
                'event_type': 'MESS_CUT_CREATED',
                'mess_cut_id': str(instance.id),
                'student_id': str(instance.student.id),
                'student_name': instance.student.name,
                'roll_no': instance.student.roll_no,
                'from_date': instance.from_date.isoformat(),
                'to_date': instance.to_date.isoformat(),
                'applied_by': instance.applied_by
            }
            sheets_service.append_data('mess_cuts', data)
        except Exception as e:
            logger.error(f"Failed to log mess cut to sheets: {str(e)}")


@receiver(pre_save, sender=MessCut)
def mess_cut_pre_save(sender, instance, **kwargs):
    """Handle mess cut pre-save validation."""
    
    # Validate dates
    if instance.from_date > instance.to_date:
        raise ValidationError("From date must be before or equal to to date")
    
    # Check for overlapping mess cuts
    overlapping = MessCut.objects.filter(
        student=instance.student,
        from_date__lte=instance.to_date,
        to_date__gte=instance.from_date
    )
    
    if instance.pk:
        overlapping = overlapping.exclude(pk=instance.pk)
    
    if overlapping.exists():
        raise ValidationError("Mess cut overlaps with existing cut")


@receiver(post_save, sender=MessClosure)
def mess_closure_post_save(sender, instance, created, **kwargs):
    """Handle mess closure creation."""
    
    if created:
        # Log to Google Sheets
        try:
            data = {
                'timestamp': instance.created_at.isoformat(),
                'event_type': 'MESS_CLOSURE_CREATED',
                'closure_id': str(instance.id),
                'from_date': instance.from_date.isoformat(),
                'to_date': instance.to_date.isoformat(),
                'reason': instance.reason,
                'created_by_admin_id': instance.created_by_admin_id
            }
            sheets_service.append_data('mess_closures', data)
        except Exception as e:
            logger.error(f"Failed to log mess closure to sheets: {str(e)}")


@receiver(post_save, sender=ScanEvent)
def scan_event_post_save(sender, instance, created, **kwargs):
    """Handle scan event creation."""
    
    if created:
        # Log to Google Sheets
        try:
            data = {
                'timestamp': instance.scanned_at.isoformat(),
                'scan_id': str(instance.id),
                'student_id': str(instance.student.id),
                'student_name': instance.student.name,
                'roll_no': instance.student.roll_no,
                'meal': instance.meal,
                'result': instance.result,
                'device_info': instance.device_info,
                'staff_token_id': str(instance.staff_token.id) if instance.staff_token else '',
                'scanned_at': instance.scanned_at.isoformat()
            }
            sheets_service.append_data('scan_events', data)
        except Exception as e:
            logger.error(f"Failed to log scan event to sheets: {str(e)}")


@receiver(post_save, sender=StaffToken)
def staff_token_post_save(sender, instance, created, **kwargs):
    """Handle staff token creation."""
    
    if created:
        logger.info(f"New staff token created: {instance.label}")
        
        # Create audit log
        try:
            AuditLog.objects.create(
                actor_type=AuditLog.ActorType.ADMIN,
                event_type='STAFF_TOKEN_CREATED',
                payload={
                    'token_id': str(instance.id),
                    'label': instance.label,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None
                }
            )
        except Exception as e:
            logger.error(f"Failed to create audit log for staff token: {str(e)}")


@receiver(pre_delete, sender=StaffToken)
def staff_token_pre_delete(sender, instance, **kwargs):
    """Handle staff token deletion."""
    
    logger.info(f"Staff token deleted: {instance.label}")
    
    # Create audit log
    try:
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            event_type='STAFF_TOKEN_DELETED',
            payload={
                'token_id': str(instance.id),
                'label': instance.label,
                'was_active': instance.active
            }
        )
    except Exception as e:
        logger.error(f"Failed to create audit log for staff token deletion: {str(e)}")


@receiver(post_save, sender=AuditLog)
def audit_log_post_save(sender, instance, created, **kwargs):
    """Handle audit log creation."""
    
    if created:
        # Log critical events to Google Sheets
        critical_events = [
            'STUDENT_APPROVED', 'STUDENT_DENIED',
            'PAYMENT_VERIFIED', 'PAYMENT_DENIED',
            'QR_CODES_REGENERATED', 'STAFF_TOKEN_CREATED'
        ]
        
        if instance.event_type in critical_events:
            try:
                data = {
                    'timestamp': instance.created_at.isoformat(),
                    'actor_type': instance.actor_type,
                    'actor_id': instance.actor_id or '',
                    'event_type': instance.event_type,
                    'payload': str(instance.payload)
                }
                sheets_service.append_data('audit_logs', data)
            except Exception as e:
                logger.error(f"Failed to log audit event to sheets: {str(e)}")


# Signal for cleanup operations
@receiver(post_delete, sender=Student)
def student_post_delete(sender, instance, **kwargs):
    """Handle student deletion cleanup."""
    
    logger.info(f"Student deleted: {instance.name} ({instance.roll_no})")
    
    # Clean up related QR codes from Cloudinary
    try:
        from integrations.cloudinary import CloudinaryService
        CloudinaryService.delete_file(f"qr_codes/{instance.id}_v{instance.qr_version}")
    except Exception as e:
        logger.error(f"Failed to cleanup QR code for deleted student: {str(e)}")


@receiver(post_delete, sender=Payment)
def payment_post_delete(sender, instance, **kwargs):
    """Handle payment deletion cleanup."""
    
    logger.info(f"Payment deleted: {instance.id} for student {instance.student.roll_no}")
    
    # Clean up screenshot from Cloudinary
    if instance.screenshot_url:
        try:
            from integrations.cloudinary import CloudinaryService
            # Extract public_id from URL
            if 'cloudinary.com' in instance.screenshot_url:
                public_id = instance.screenshot_url.split('/')[-1].split('.')[0]
                CloudinaryService.delete_file(f"mess_payments/{public_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup payment screenshot: {str(e)}")


# Custom signal for QR regeneration
from django.dispatch import Signal

qr_codes_regenerated = Signal()

@receiver(qr_codes_regenerated)
def handle_qr_regeneration(sender, **kwargs):
    """Handle QR code regeneration event."""
    
    version = kwargs.get('version')
    affected_count = kwargs.get('affected_count', 0)
    
    logger.info(f"QR codes regenerated: version {version}, affected {affected_count} students")
    
    # Create audit log
    try:
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=kwargs.get('admin_id'),
            event_type='QR_CODES_REGENERATED',
            payload={
                'new_version': version,
                'affected_students': affected_count,
                'timestamp': timezone.now().isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Failed to create audit log for QR regeneration: {str(e)}")


# Signal for payment expiry notifications
payment_expiry_warning = Signal()

@receiver(payment_expiry_warning)
def handle_payment_expiry_warning(sender, **kwargs):
    """Handle payment expiry warning."""
    
    student = kwargs.get('student')
    payment = kwargs.get('payment')
    days_left = kwargs.get('days_left')
    
    if student and payment:
        logger.info(f"Payment expiry warning for {student.roll_no}: {days_left} days left")
        
        # Send notification
        try:
            from notifications.telegram import sync_send_message
            message = f"⏰ Payment Expiring Soon\n\nYour payment expires in {days_left} days on {payment.cycle_end}.\n\nPlease upload your next payment to avoid service interruption."
            sync_send_message(student.tg_user_id, message)
        except Exception as e:
            logger.error(f"Failed to send payment expiry warning: {str(e)}")


# Connect signals only once
def connect_signals():
    """Ensure signals are connected only once."""
    
    # This function can be called from apps.py to ensure signals are connected
    logger.info("Mess management signals connected successfully")


# Disconnect signals (useful for testing)
def disconnect_signals():
    """Disconnect all signals."""
    
    signals_to_disconnect = [
        (post_save, student_post_save, Student),
        (pre_save, student_pre_save, Student),
        (post_save, payment_post_save, Payment),
        (pre_save, payment_pre_save, Payment),
        (post_save, mess_cut_post_save, MessCut),
        (pre_save, mess_cut_pre_save, MessCut),
        (post_save, mess_closure_post_save, MessClosure),
        (post_save, scan_event_post_save, ScanEvent),
        (post_save, staff_token_post_save, StaffToken),
        (pre_delete, staff_token_pre_delete, StaffToken),
        (post_delete, student_post_delete, Student),
        (post_delete, payment_post_delete, Payment),
    ]
    
    for signal_type, handler, sender in signals_to_disconnect:
        try:
            signal_type.disconnect(handler, sender=sender)
        except Exception:
            pass  # Signal may not be connected
    
    logger.info("Mess management signals disconnected")