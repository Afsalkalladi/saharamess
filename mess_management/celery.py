import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mess_management.settings')

app = Celery('mess_management')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
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

app.conf.timezone = 'Asia/Kolkata'

# Celery configuration
app.conf.update(
    # Broker settings
    broker_url=getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=getattr(settings, 'TIME_ZONE', 'Asia/Kolkata'),
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        'core.tasks.process_sheets_log': {'queue': 'high_priority'},
        'core.tasks.send_daily_summary_report': {'queue': 'notifications'},
        'core.tasks.check_expired_payments': {'queue': 'notifications'},
        'core.tasks.cleanup_old_audit_logs': {'queue': 'maintenance'},
        'core.tasks.cleanup_old_scan_events': {'queue': 'maintenance'},
        'core.tasks.backup_critical_data': {'queue': 'backup'},
    },
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_backend_db=1,
    
    # Task execution settings
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes hard limit
    task_reject_on_worker_lost=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Process failed Google Sheets operations every 5 minutes
    'retry-dlq-operations': {
        'task': 'core.tasks.retry_dlq_operations',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'high_priority'}
    },
    
    # Cleanup old audit logs daily at 2 AM
    'cleanup-old-audit-logs': {
        'task': 'core.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'maintenance'}
    },
    
    # Cleanup old scan events daily at 2:30 AM
    'cleanup-old-scan-events': {
        'task': 'core.tasks.cleanup_old_scan_events',
        'schedule': crontab(hour=2, minute=30),
        'options': {'queue': 'maintenance'}
    },
    
    # Send daily summary report at 8 AM
    'send-daily-summary': {
        'task': 'core.tasks.send_daily_summary_report',
        'schedule': crontab(hour=8, minute=0),
        'options': {'queue': 'notifications'}
    },
    
    # Check expired payments daily at 9 AM
    'check-expired-payments': {
        'task': 'core.tasks.check_expired_payments',
        'schedule': crontab(hour=9, minute=0),
        'options': {'queue': 'notifications'}
    },
    
    # Backup critical data daily at 1 AM
    'backup-critical-data': {
        'task': 'core.tasks.backup_critical_data',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'backup'}
    },
    
    # Health check every hour
    'system-health-check': {
        'task': 'core.tasks.system_health_check',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'monitoring'}
    },
    
    # Generate hourly statistics
    'generate-hourly-stats': {
        'task': 'core.tasks.generate_hourly_stats',
        'schedule': crontab(minute=5),  # 5 minutes past every hour
        'options': {'queue': 'analytics'}
    },
    
    # Send payment expiry warnings at 10 AM daily
    'payment-expiry-warnings': {
        'task': 'core.tasks.send_payment_expiry_warnings',
        'schedule': crontab(hour=10, minute=0),
        'options': {'queue': 'notifications'}
    },
    
    # Cleanup expired staff tokens weekly on Sunday at 3 AM
    'cleanup-expired-tokens': {
        'task': 'core.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'options': {'queue': 'maintenance'}
    },
    
    # Generate weekly reports on Monday at 9 AM
    'weekly-reports': {
        'task': 'core.tasks.generate_weekly_reports',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
        'options': {'queue': 'reports'}
    },
    
    # Monthly data archival on 1st of each month at midnight
    'monthly-data-archival': {
        'task': 'core.tasks.archive_monthly_data',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),
        'options': {'queue': 'archival'}
    },
}

# Queue configuration
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_exchange_type = 'direct'
app.conf.task_default_routing_key = 'default'

# Define queues
app.conf.task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'high_priority': {
        'exchange': 'high_priority',
        'routing_key': 'high_priority',
    },
    'notifications': {
        'exchange': 'notifications',
        'routing_key': 'notifications',
    },
    'maintenance': {
        'exchange': 'maintenance',
        'routing_key': 'maintenance',
    },
    'backup': {
        'exchange': 'backup',
        'routing_key': 'backup',
    },
    'monitoring': {
        'exchange': 'monitoring',
        'routing_key': 'monitoring',
    },
    'analytics': {
        'exchange': 'analytics',
        'routing_key': 'analytics',
    },
    'reports': {
        'exchange': 'reports',
        'routing_key': 'reports',
    },
    'archival': {
        'exchange': 'archival',
        'routing_key': 'archival',
    },
}

# Error handling
app.conf.task_annotations = {
    '*': {
        'rate_limit': '100/m',  # Global rate limit
        'time_limit': 600,      # 10 minutes
        'soft_time_limit': 300, # 5 minutes
    },
    'core.tasks.process_sheets_log': {
        'rate_limit': '50/m',   # Higher rate for critical tasks
        'max_retries': 3,
        'default_retry_delay': 60,
    },
    'core.tasks.send_*': {
        'rate_limit': '30/m',   # Moderate rate for notifications
        'max_retries': 5,
        'default_retry_delay': 300,  # 5 minutes
    },
    'core.tasks.cleanup_*': {
        'rate_limit': '10/m',   # Lower rate for cleanup tasks
        'max_retries': 2,
    },
}

# Logging configuration
app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
app.conf.worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Monitoring and metrics
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True
app.conf.worker_enable_remote_control = True

# Development settings
if getattr(settings, 'DEBUG', False):
    app.conf.update(
        task_always_eager=False,  # Set to True to run tasks synchronously in development
        task_eager_propagates=True,
        worker_log_level='DEBUG',
    )

# Production optimizations
else:
    app.conf.update(
        worker_prefetch_multiplier=4,
        task_compression='gzip',
        result_compression='gzip',
        worker_max_memory_per_child=200000,  # 200MB
    )


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
    return 'Debug task completed successfully'


# Celery signal handlers
from celery.signals import task_prerun, task_postrun, task_failure, worker_ready
import logging

logger = logging.getLogger(__name__)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start."""
    logger.info(f'Task {task.name}[{task_id}] started')


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Log task completion."""
    logger.info(f'Task {task.name}[{task_id}] completed with state: {state}')


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failures."""
    logger.error(f'Task {sender.name}[{task_id}] failed: {exception}', exc_info=einfo)


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready."""
    logger.info(f'Celery worker {sender.hostname} is ready')


# Custom task base class
from celery import Task
import time


class CallbackTask(Task):
    """Task class with callbacks and monitoring."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        logger.info(f'Task {self.name}[{task_id}] succeeded: {retval}')
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(f'Task {self.name}[{task_id}] failed: {exc}')
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        logger.warning(f'Task {self.name}[{task_id}] retrying: {exc}')


# Set default task base class
app.Task = CallbackTask


# Utility functions for task management
def get_active_tasks():
    """Get list of active tasks."""
    inspect = app.control.inspect()
    return inspect.active()


def get_scheduled_tasks():
    """Get list of scheduled tasks."""
    inspect = app.control.inspect()
    return inspect.scheduled()


def get_task_stats():
    """Get task execution statistics."""
    inspect = app.control.inspect()
    return inspect.stats()


def purge_queue(queue_name):
    """Purge a specific queue."""
    app.control.purge()


def revoke_task(task_id, terminate=False):
    """Revoke a specific task."""
    app.control.revoke(task_id, terminate=terminate)


# Health check for Celery
def celery_health_check():
    """Check if Celery is healthy."""
    try:
        # Test basic connectivity
        inspect = app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return False, "No workers available"
        
        # Check if workers are responding
        active = inspect.active()
        if active is None:
            return False, "Workers not responding"
        
        # Test task execution
        result = debug_task.delay()
        try:
            result.get(timeout=10)
            return True, "Celery is healthy"
        except:
            return False, "Task execution failed"
            
    except Exception as e:
        return False, f"Celery health check failed: {str(e)}"


if __name__ == '__main__':
    app.start()