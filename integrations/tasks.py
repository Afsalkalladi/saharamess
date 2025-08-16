"""
Background tasks for Google Sheets integration.
"""
import logging
from typing import Dict, Any
from django.conf import settings
from django.utils import timezone

from .google_sheets import sheets_service

logger = logging.getLogger(__name__)


def process_sheets_log(sheet_name: str, data: Dict[str, Any]) -> bool:
    """
    Process Google Sheets logging synchronously.
    Falls back to DLQ if Google Sheets is unavailable.
    """
    try:
        if not sheets_service:
            logger.warning("Google Sheets service not available, skipping log")
            return False
        
        success = sheets_service.append_data(sheet_name, data)
        
        if success:
            logger.info(f"Successfully logged to {sheet_name}: {data.get('event_type', 'unknown')}")
        else:
            logger.error(f"Failed to log to {sheet_name}")
            _fallback_to_dlq(sheet_name, data, "Sheets service returned False")
        
        return success
        
    except Exception as e:
        logger.error(f"Exception logging to {sheet_name}: {str(e)}")
        _fallback_to_dlq(sheet_name, data, str(e))
        return False


def _fallback_to_dlq(sheet_name: str, data: Dict[str, Any], error_message: str):
    """Fallback to DLQ when Google Sheets fails."""
    try:
        from core.models import DLQLog
        DLQLog.objects.create(
            operation=f"log_to_{sheet_name}",
            payload=data,
            error_message=error_message
        )
        logger.info(f"Moved failed operation to DLQ: {sheet_name}")
    except Exception as dlq_error:
        logger.error(f"Failed to create DLQ entry: {str(dlq_error)}")


def retry_dlq_operations():
    """Retry failed Google Sheets operations from DLQ."""
    if not sheets_service:
        logger.warning("Google Sheets service not available, skipping DLQ retry")
        return
    
    try:
        from core.models import DLQLog
        from datetime import timedelta
        
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
                success = sheets_service.append_data(sheet_name, dlq_item.payload)
                
                if success:
                    # Mark as processed
                    dlq_item.processed = True
                    dlq_item.save()
                    logger.info(f"Successfully retried DLQ item {dlq_item.id}")
                else:
                    raise Exception("Sheets service returned False")
                
            except Exception as e:
                # Increment retry count
                dlq_item.retry_count += 1
                dlq_item.error_message = f"{dlq_item.error_message}\n\nRetry {dlq_item.retry_count}: {str(e)}"
                dlq_item.save()
                
                logger.error(f"Failed to retry DLQ item {dlq_item.id}: {str(e)}")
        
        logger.info(f"Processed {len(dlq_items)} DLQ items")
        
    except Exception as e:
        logger.error(f"Failed to retry DLQ operations: {str(e)}")


def create_backup_summary() -> Dict[str, Any]:
    """Create a backup summary of backup status."""
    if not sheets_service:
        return {
            'status': 'unavailable',
            'message': 'Google Sheets service not configured'
        }
    
    try:
        summary = sheets_service.create_backup_summary()
        summary['status'] = 'available'
        return summary
    except Exception as e:
        logger.error(f"Failed to create backup summary: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }
