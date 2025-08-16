from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
import json
import time

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError

from .models import DLQLog, Student, Payment, MessCut, MessClosure, ScanEvent

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_sheets_log(self, sheet_name: str, data: dict):
    """Process Google Sheets logging with retry logic."""
    try:
        sheets_service = get_sheets_service()
        
        # Prepare row data
        row_data = prepare_row_data(sheet_name, data)
        
        # Append to sheet
        append_to_sheet(sheets_service, sheet_name, row_data)
        
        logger.info(f"Successfully logged to {sheet_name}: {data.get('event_type', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Failed to log to {sheet_name}: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = (2 ** self.request.retries) * 60  # 1min, 2min, 4min
            logger.info(f"Retrying in {retry_delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            # Move to DLQ
            DLQLog.objects.create(
                operation=f"log_to_{sheet_name}",
                payload=data,
                error_message=str(e),
                retry_count=self.request.retries
            )
            logger.error(f"Max retries exceeded, moved to DLQ: {sheet_name}")


@shared_task
def retry_dlq_operations():
    """Retry failed Google Sheets operations from DLQ."""
    # Get unprocessed DLQ items older than 5 minutes
    cutoff_time = timezone.now() - timedelta(minutes=5)
    dlq_items = DLQLog.objects.filter(
        processed=False,
        retry_count__lt=5,  # Max 5 retries for DLQ items
        created_at__lt=cutoff_time
    ).order_by('created_at')[:10]  # Process 10 at a time
    
    for dlq_item in dlq_items:
        try:
            # Extract sheet name from operation
            sheet_name = dlq_item.operation.replace('log_to_', '')
            
            # Retry the operation
            process_sheets_log.delay(sheet_name, dlq_item.payload)
            
            # Mark as processed
            dlq_item.processed = True
            dlq_item.save()
            
            logger.info(f"Retried DLQ item {dlq_item.id}")
            
        except Exception as e:
            # Increment retry count
            dlq_item.retry_count += 1
            dlq_item.error_message = f"{dlq_item.error_message}\n\nRetry {dlq_item.retry_count}: {str(e)}"
            dlq_item.save()
            
            logger.error(f"Failed to retry DLQ item {dlq_item.id}: {str(e)}")


@shared_task
def cleanup_old_audit_logs():
    """Clean up old audit logs to prevent database bloat."""
    # Keep logs for 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    from .models import AuditLog
    deleted_count = AuditLog.objects.filter(created_at__lt=cutoff_date).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old audit log entries")
    return deleted_count


@shared_task
def cleanup_old_scan_events():
    """Clean up old scan events to prevent database bloat."""
    # Keep scan events for 30 days
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_count = ScanEvent.objects.filter(scanned_at__lt=cutoff_date).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old scan event entries")
    return deleted_count


@shared_task
def send_daily_summary_report():
    """Send daily summary report to admins."""
    try:
        from .telegram_bot import bot_instance
        import asyncio
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get yesterday's statistics
        stats = {
            'registrations': Student.objects.filter(created_at__date=yesterday).count(),
            'payments_uploaded': Payment.objects.filter(created_at__date=yesterday, status=Payment.Status.UPLOADED).count(),
            'payments_verified': Payment.objects.filter(reviewed_at__date=yesterday, status=Payment.Status.VERIFIED).count(),
            'mess_cuts': MessCut.objects.filter(applied_at__date=yesterday).count(),
            'scan_events': ScanEvent.objects.filter(scanned_at__date=yesterday).count(),
            'successful_scans': ScanEvent.objects.filter(
                scanned_at__date=yesterday, 
                result=ScanEvent.Result.ALLOWED
            ).count(),
        }
        
        # Get meal breakdown
        meal_stats = {}
        for meal in ['BREAKFAST', 'LUNCH', 'DINNER']:
            meal_stats[meal] = ScanEvent.objects.filter(
                scanned_at__date=yesterday,
                meal=meal,
                result=ScanEvent.Result.ALLOWED
            ).count()
        
        # Prepare report message
        message = f"""
📊 **Daily Summary Report - {yesterday.strftime('%Y-%m-%d')}**

📝 **Registrations**: {stats['registrations']}
💳 **Payments Uploaded**: {stats['payments_uploaded']}
✅ **Payments Verified**: {stats['payments_verified']}
✂️ **Mess Cuts Applied**: {stats['mess_cuts']}

🍽️ **Meal Access**
Total Scans: {stats['scan_events']}
Successful: {stats['successful_scans']}

🍳 Breakfast: {meal_stats['BREAKFAST']}
🍽️ Lunch: {meal_stats['LUNCH']}
🍽️ Dinner: {meal_stats['DINNER']}

📈 **Success Rate**: {(stats['successful_scans'] / max(stats['scan_events'], 1)) * 100:.1f}%
        """
        
        # Send to all admins
        async def send_reports():
            for admin_id in settings.ADMIN_TG_IDS:
                try:
                    await bot_instance.application.bot.send_message(
                        chat_id=admin_id,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Failed to send report to admin {admin_id}: {str(e)}")
        
        # Run async function
        asyncio.run(send_reports())
        
        logger.info("Daily summary report sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send daily summary report: {str(e)}")


@shared_task
def check_expired_payments():
    """Check for expired payments and notify students."""
    try:
        from .telegram_bot import bot_instance
        import asyncio
        
        # Find payments expiring in 3 days
        warning_date = timezone.now().date() + timedelta(days=3)
        expiring_payments = Payment.objects.filter(
            status=Payment.Status.VERIFIED,
            cycle_end=warning_date
        ).select_related('student')
        
        # Find payments expiring today
        today = timezone.now().date()
        expired_today = Payment.objects.filter(
            status=Payment.Status.VERIFIED,
            cycle_end=today
        ).select_related('student')
        
        async def send_notifications():
            # Warning notifications (3 days before)
            for payment in expiring_payments:
                try:
                    message = f"""
⏰ **Payment Expiring Soon**

Hi {payment.student.name},

Your mess payment is expiring in 3 days:
📅 Expires: {payment.cycle_end}
💰 Amount: ₹{payment.amount}

Please upload your next payment to avoid service interruption.
                    """
                    
                    await bot_instance.application.bot.send_message(
                        chat_id=payment.student.tg_user_id,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Failed to send warning to {payment.student.tg_user_id}: {str(e)}")
            
            # Expiry notifications (on expiry date)
            for payment in expired_today:
                try:
                    message = f"""
❌ **Payment Expired**

Hi {payment.student.name},

Your mess payment has expired today:
📅 Expired: {payment.cycle_end}
💰 Amount: ₹{payment.amount}

Please upload your new payment immediately to continue accessing meals.
                    """
                    
                    await bot_instance.application.bot.send_message(
                        chat_id=payment.student.tg_user_id,
                        text=message
                    )
                except Exception as e:
                    logger.error(f"Failed to send expiry notice to {payment.student.tg_user_id}: {str(e)}")
        
        # Run notifications
        asyncio.run(send_notifications())
        
        logger.info(f"Sent {len(expiring_payments)} warning and {len(expired_today)} expiry notifications")
        
    except Exception as e:
        logger.error(f"Failed to check expired payments: {str(e)}")


@shared_task
def backup_critical_data():
    """Backup critical data to Google Sheets."""
    try:
        sheets_service = get_sheets_service()
        
        # Backup recent data (last 7 days)
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Students
        students = Student.objects.filter(created_at__gte=cutoff_date)
        for student in students:
            data = {
                'timestamp': student.created_at.isoformat(),
                'event_type': 'BACKUP',
                'student_id': str(student.id),
                'student_name': student.name,
                'roll_no': student.roll_no,
                'status': student.status
            }
            row_data = prepare_row_data('registrations', data)
            append_to_sheet(sheets_service, 'registrations', row_data)
        
        # Payments
        payments = Payment.objects.filter(created_at__gte=cutoff_date).select_related('student')
        for payment in payments:
            data = {
                'timestamp': payment.created_at.isoformat(),
                'event_type': 'BACKUP',
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
            row_data = prepare_row_data('payments', data)
            append_to_sheet(sheets_service, 'payments', row_data)
        
        logger.info(f"Backed up {len(students)} students and {len(payments)} payments to Google Sheets")
        
    except Exception as e:
        logger.error(f"Failed to backup critical data: {str(e)}")


def get_sheets_service():
    """Get authenticated Google Sheets service."""
    try:
        credentials_info = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS)
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Failed to create Sheets service: {str(e)}")
        raise


def prepare_row_data(sheet_name: str, data: dict) -> list:
    """Prepare data for Google Sheets row."""
    # Define column mappings for each sheet
    column_mappings = {
        'registrations': [
            'timestamp', 'event_type', 'student_id', 'student_name', 
            'roll_no', 'status'
        ],
        'payments': [
            'timestamp', 'event_type', 'payment_id', 'student_id',
            'student_name', 'roll_no', 'cycle_start', 'cycle_end',
            'amount', 'status', 'source'
        ],
        'mess_cuts': [
            'timestamp', 'event_type', 'mess_cut_id', 'student_id',
            'student_name', 'roll_no', 'from_date', 'to_date', 'applied_by'
        ],
        'mess_closures': [
            'timestamp', 'event_type', 'closure_id', 'from_date',
            'to_date', 'reason', 'created_by_admin_id'
        ],
        'scan_events': [
            'timestamp', 'scan_id', 'student_id', 'student_name',
            'roll_no', 'meal', 'result', 'device_info'
        ]
    }
    
    columns = column_mappings.get(sheet_name, [])
    row_data = []
    
    for column in columns:
        value = data.get(column, '')
        # Convert to string and handle None values
        row_data.append(str(value) if value is not None else '')
    
    return row_data


def append_to_sheet(service, sheet_name: str, row_data: list):
    """Append data to Google Sheets."""
    try:
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        range_name = f"{sheet_name}!A:Z"
        
        body = {
            'values': [row_data]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        return result
        
    except HttpError as e:
        logger.error(f"Google Sheets API error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to append to sheet {sheet_name}: {str(e)}")
        raise


# Periodic task setup (add to Django settings or celery beat schedule)
"""
Add to settings.py:

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'retry-dlq-operations': {
        'task': 'core.tasks.retry_dlq_operations',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-old-audit-logs': {
        'task': 'core.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-scan-events': {
        'task': 'core.tasks.cleanup_old_scan_events',
        'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM
    },
    'send-daily-summary': {
        'task': 'core.tasks.send_daily_summary_report',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'check-expired-payments': {
        'task': 'core.tasks.check_expired_payments',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'backup-critical-data': {
        'task': 'core.tasks.backup_critical_data',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
}

CELERY_TIMEZONE = 'Asia/Kolkata'
"""