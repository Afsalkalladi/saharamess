"""
Manual Payment Verification System
Handles payment verification through Google Sheets and Telegram buttons
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import cloudinary.uploader
from .models import Payment, Student
from integrations.telegram import send_telegram_message

logger = logging.getLogger(__name__)


class PaymentVerificationManager:
    """Manages manual payment verification workflow"""
    
    def __init__(self):
        self.setup_sheets_client()
    
    def setup_sheets_client(self):
        """Initialize Google Sheets client"""
        try:
            if hasattr(settings, 'SHEETS_CREDENTIALS_JSON') and settings.SHEETS_CREDENTIALS_JSON:
                credentials_dict = json.loads(settings.SHEETS_CREDENTIALS_JSON)
                scope = [
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive'
                ]
                credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                    credentials_dict, scope
                )
                self.sheets_client = gspread.authorize(credentials)
                self.verification_sheet = self.sheets_client.open_by_key(
                    settings.PAYMENT_VERIFICATION_SHEET_ID
                ).worksheet(settings.PAYMENT_VERIFICATION_SHEET_NAME)
            else:
                self.sheets_client = None
                self.verification_sheet = None
                logger.warning("Google Sheets not configured for payment verification")
        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {e}")
            self.sheets_client = None
            self.verification_sheet = None
    
    def submit_payment_for_verification(self, payment_id: int, receipt_file, 
                                      student_id: int, amount: float, 
                                      payment_method: str, notes: str = "") -> Dict:
        """
        Submit payment receipt for manual verification
        
        Args:
            payment_id: Payment record ID
            receipt_file: Uploaded receipt file
            student_id: Student ID
            amount: Payment amount
            payment_method: Payment method (UPI, Bank Transfer, etc.)
            notes: Additional notes
            
        Returns:
            Dict with status and details
        """
        try:
            # Upload receipt to Cloudinary
            receipt_url = self.upload_receipt_to_cloudinary(receipt_file, payment_id)
            
            # Get student details
            student = Student.objects.get(id=student_id)
            
            # Create verification entry in Google Sheets
            sheet_row_id = self.add_to_verification_sheet(
                payment_id=payment_id,
                student_name=student.name,
                student_id=student.student_id,
                amount=amount,
                payment_method=payment_method,
                receipt_url=receipt_url,
                notes=notes
            )
            
            # Send Telegram notification to admins
            self.send_telegram_verification_request(
                payment_id=payment_id,
                student_name=student.name,
                amount=amount,
                receipt_url=receipt_url,
                sheet_row_id=sheet_row_id
            )
            
            # Update payment status
            payment = Payment.objects.get(id=payment_id)
            payment.status = 'pending_verification'
            payment.receipt_url = receipt_url
            payment.verification_submitted_at = timezone.now()
            payment.save()
            
            return {
                'status': 'success',
                'message': 'Payment submitted for verification',
                'receipt_url': receipt_url,
                'sheet_row_id': sheet_row_id
            }
            
        except Exception as e:
            logger.error(f"Failed to submit payment for verification: {e}")
            return {
                'status': 'error',
                'message': f'Failed to submit payment: {str(e)}'
            }
    
    def upload_receipt_to_cloudinary(self, receipt_file, payment_id: int) -> str:
        """Upload payment receipt to Cloudinary"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"payment_{payment_id}_{timestamp}"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                receipt_file,
                folder=settings.PAYMENT_RECEIPT_FOLDER,
                public_id=filename,
                resource_type="auto",  # Handles images and PDFs
                format="jpg" if receipt_file.content_type.startswith('image') else None
            )
            
            return result['secure_url']
            
        except Exception as e:
            logger.error(f"Failed to upload receipt to Cloudinary: {e}")
            raise ValidationError(f"Failed to upload receipt: {str(e)}")
    
    def add_to_verification_sheet(self, payment_id: int, student_name: str,
                                student_id: str, amount: float, payment_method: str,
                                receipt_url: str, notes: str = "") -> Optional[int]:
        """Add payment verification entry to Google Sheets"""
        if not self.verification_sheet:
            logger.warning("Google Sheets not available")
            return None
            
        try:
            # Prepare row data
            row_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Timestamp
                payment_id,                                    # Payment ID
                student_name,                                  # Student Name
                student_id,                                    # Student ID
                amount,                                        # Amount
                payment_method,                               # Payment Method
                receipt_url,                                  # Receipt URL
                'PENDING',                                    # Status
                '',                                          # Approved By
                '',                                          # Approved At
                notes,                                       # Notes
                '',                                          # Admin Comments
            ]
            
            # Add row to sheet
            self.verification_sheet.append_row(row_data)
            
            # Get row number (assuming headers in row 1)
            all_records = self.verification_sheet.get_all_records()
            row_number = len(all_records) + 1  # +1 for header row
            
            # Add approve/deny buttons using sheet formulas
            self.add_sheet_buttons(row_number, payment_id)
            
            return row_number
            
        except Exception as e:
            logger.error(f"Failed to add to verification sheet: {e}")
            return None
    
    def add_sheet_buttons(self, row_number: int, payment_id: int):
        """Add approve/deny buttons to Google Sheets row"""
        try:
            # Create webhook URLs for approve/deny actions
            base_url = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'
            approve_url = f"https://{base_url}/api/v1/payments/{payment_id}/approve/"
            deny_url = f"https://{base_url}/api/v1/payments/{payment_id}/deny/"
            
            # Add buttons using HYPERLINK formula
            approve_button = f'=HYPERLINK("{approve_url}", "✅ APPROVE")'
            deny_button = f'=HYPERLINK("{deny_url}", "❌ DENY")'
            
            # Update cells with buttons (assuming columns M and N for buttons)
            self.verification_sheet.update(f'M{row_number}', approve_button)
            self.verification_sheet.update(f'N{row_number}', deny_button)
            
        except Exception as e:
            logger.error(f"Failed to add sheet buttons: {e}")
    
    def send_telegram_verification_request(self, payment_id: int, student_name: str,
                                         amount: float, receipt_url: str, 
                                         sheet_row_id: Optional[int]):
        """Send payment verification request to Telegram admins"""
        try:
            # Create message
            message = f"""
🔔 **New Payment Verification Request**

👤 **Student**: {student_name}
💰 **Amount**: ₹{amount}
🆔 **Payment ID**: {payment_id}
📄 **Receipt**: [View Receipt]({receipt_url})
📊 **Sheet Row**: {sheet_row_id or 'N/A'}

Please verify this payment and take action.
            """
            
            # Create inline keyboard with approve/deny buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", 
                                       callback_data=f"approve_payment_{payment_id}"),
                    InlineKeyboardButton("❌ Deny", 
                                       callback_data=f"deny_payment_{payment_id}")
                ],
                [
                    InlineKeyboardButton("📄 View Receipt", url=receipt_url),
                    InlineKeyboardButton("📊 Open Sheet", 
                                       url=f"https://docs.google.com/spreadsheets/d/{settings.PAYMENT_VERIFICATION_SHEET_ID}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send to admin chat
            chat_id = getattr(settings, 'PAYMENT_NOTIFICATION_CHAT_ID', None)
            if not chat_id:
                # Fall back to individual admin IDs
                admin_ids = settings.ADMIN_TG_IDS.split(',')
                for admin_id in admin_ids:
                    send_telegram_message(
                        chat_id=admin_id.strip(),
                        message=message,
                        reply_markup=reply_markup
                    )
            else:
                send_telegram_message(
                    chat_id=chat_id,
                    message=message,
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Failed to send Telegram verification request: {e}")
    
    def approve_payment(self, payment_id: int, admin_user_id: str, 
                       admin_comments: str = "") -> Dict:
        """Approve a payment verification"""
        try:
            payment = Payment.objects.get(id=payment_id)
            
            # Update payment status
            payment.status = 'verified'
            payment.verified_by = admin_user_id
            payment.verified_at = timezone.now()
            payment.admin_comments = admin_comments
            payment.save()
            
            # Update Google Sheets
            self.update_verification_sheet(payment_id, 'APPROVED', admin_user_id, admin_comments)
            
            # Notify student
            self.notify_student_payment_status(payment, 'approved')
            
            # Notify admins
            self.notify_admins_payment_decision(payment, 'approved', admin_user_id)
            
            return {
                'status': 'success',
                'message': 'Payment approved successfully'
            }
            
        except Payment.DoesNotExist:
            return {
                'status': 'error',
                'message': 'Payment not found'
            }
        except Exception as e:
            logger.error(f"Failed to approve payment: {e}")
            return {
                'status': 'error',
                'message': f'Failed to approve payment: {str(e)}'
            }
    
    def deny_payment(self, payment_id: int, admin_user_id: str, 
                    reason: str = "") -> Dict:
        """Deny a payment verification"""
        try:
            payment = Payment.objects.get(id=payment_id)
            
            # Update payment status
            payment.status = 'rejected'
            payment.verified_by = admin_user_id
            payment.verified_at = timezone.now()
            payment.admin_comments = reason
            payment.save()
            
            # Update Google Sheets
            self.update_verification_sheet(payment_id, 'DENIED', admin_user_id, reason)
            
            # Notify student
            self.notify_student_payment_status(payment, 'denied', reason)
            
            # Notify admins
            self.notify_admins_payment_decision(payment, 'denied', admin_user_id)
            
            return {
                'status': 'success',
                'message': 'Payment denied successfully'
            }
            
        except Payment.DoesNotExist:
            return {
                'status': 'error',
                'message': 'Payment not found'
            }
        except Exception as e:
            logger.error(f"Failed to deny payment: {e}")
            return {
                'status': 'error',
                'message': f'Failed to deny payment: {str(e)}'
            }
    
    def update_verification_sheet(self, payment_id: int, status: str, 
                                admin_user_id: str, comments: str = ""):
        """Update payment status in Google Sheets"""
        if not self.verification_sheet:
            return
            
        try:
            # Find the row with this payment ID
            all_records = self.verification_sheet.get_all_records()
            for i, record in enumerate(all_records):
                if str(record.get('Payment ID', '')) == str(payment_id):
                    row_number = i + 2  # +2 for header row and 0-based index
                    
                    # Update status, admin, and timestamp
                    updates = [
                        {
                            'range': f'H{row_number}',  # Status column
                            'values': [[status]]
                        },
                        {
                            'range': f'I{row_number}',  # Approved By column
                            'values': [[admin_user_id]]
                        },
                        {
                            'range': f'J{row_number}',  # Approved At column
                            'values': [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
                        },
                        {
                            'range': f'L{row_number}',  # Admin Comments column
                            'values': [[comments]]
                        }
                    ]
                    
                    # Batch update
                    self.verification_sheet.batch_update(updates)
                    break
                    
        except Exception as e:
            logger.error(f"Failed to update verification sheet: {e}")
    
    def notify_student_payment_status(self, payment: Payment, status: str, reason: str = ""):
        """Notify student about payment verification status"""
        try:
            student = payment.student
            
            if status == 'approved':
                message = f"""
✅ **Payment Approved**

Hello {student.name},

Your payment of ₹{payment.amount} has been approved!

**Payment ID**: {payment.id}
**Status**: Verified ✅
**Date**: {payment.verified_at.strftime('%Y-%m-%d %H:%M')}

Your mess account has been updated.
                """
            else:  # denied
                message = f"""
❌ **Payment Denied**

Hello {student.name},

Your payment of ₹{payment.amount} has been denied.

**Payment ID**: {payment.id}
**Reason**: {reason}
**Date**: {payment.verified_at.strftime('%Y-%m-%d %H:%M')}

Please contact the mess administration for clarification.
                """
            
            # Send via Telegram if student has telegram_id
            if hasattr(student, 'telegram_id') and student.telegram_id:
                send_telegram_message(
                    chat_id=student.telegram_id,
                    message=message
                )
            
        except Exception as e:
            logger.error(f"Failed to notify student: {e}")
    
    def notify_admins_payment_decision(self, payment: Payment, decision: str, admin_user_id: str):
        """Notify other admins about payment decision"""
        try:
            student = payment.student
            
            message = f"""
📋 **Payment Decision Made**

**Decision**: {decision.upper()} {'✅' if decision == 'approved' else '❌'}
**By**: {admin_user_id}
**Student**: {student.name}
**Amount**: ₹{payment.amount}
**Payment ID**: {payment.id}
**Time**: {timezone.now().strftime('%Y-%m-%d %H:%M')}
            """
            
            # Send to admin group
            chat_id = getattr(settings, 'PAYMENT_NOTIFICATION_CHAT_ID', None)
            if chat_id:
                send_telegram_message(
                    chat_id=chat_id,
                    message=message
                )
            
        except Exception as e:
            logger.error(f"Failed to notify admins: {e}")
    
    def get_pending_verifications(self) -> List[Dict]:
        """Get list of pending payment verifications"""
        try:
            pending_payments = Payment.objects.filter(
                status='pending_verification'
            ).select_related('student')
            
            return [
                {
                    'payment_id': payment.id,
                    'student_name': payment.student.name,
                    'amount': payment.amount,
                    'submitted_at': payment.verification_submitted_at,
                    'receipt_url': payment.receipt_url,
                    'days_pending': (timezone.now() - payment.verification_submitted_at).days
                }
                for payment in pending_payments
            ]
            
        except Exception as e:
            logger.error(f"Failed to get pending verifications: {e}")
            return []
    
    def send_pending_reminders(self):
        """Send reminders for pending payment verifications"""
        try:
            pending_payments = Payment.objects.filter(
                status='pending_verification',
                verification_submitted_at__lt=timezone.now() - timedelta(
                    hours=settings.AUTO_REMINDER_INTERVAL_HOURS
                )
            )
            
            if not pending_payments.exists():
                return
            
            message = f"""
⏰ **Payment Verification Reminders**

You have {pending_payments.count()} pending payment verifications:

"""
            
            for payment in pending_payments[:10]:  # Limit to 10 for readability
                days_pending = (timezone.now() - payment.verification_submitted_at).days
                message += f"• **{payment.student.name}** - ₹{payment.amount} ({days_pending} days)\n"
            
            if pending_payments.count() > 10:
                message += f"\n... and {pending_payments.count() - 10} more"
            
            message += f"\n\n📊 [Open Verification Sheet](https://docs.google.com/spreadsheets/d/{settings.PAYMENT_VERIFICATION_SHEET_ID})"
            
            # Send to admin group
            chat_id = getattr(settings, 'PAYMENT_NOTIFICATION_CHAT_ID', None)
            if chat_id:
                send_telegram_message(
                    chat_id=chat_id,
                    message=message
                )
            
        except Exception as e:
            logger.error(f"Failed to send pending reminders: {e}")


# Initialize global instance
payment_verification_manager = PaymentVerificationManager()
