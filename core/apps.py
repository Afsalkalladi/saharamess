from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    """Configuration for the core application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Mess Management Core'
    
    def ready(self):
        """Initialize the application when Django starts."""
        
        # Import signals to connect them
        try:
            from . import signals
            signals.connect_signals()
            logger.info("Core app signals connected successfully")
        except ImportError as e:
            logger.error(f"Failed to import signals: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to connect signals: {str(e)}")
        
        # Initialize services
        try:
            self._initialize_services()
            logger.info("Core app services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
        
        # Setup periodic tasks
        try:
            self._setup_periodic_tasks()
            logger.info("Periodic tasks configured successfully")
        except Exception as e:
            logger.error(f"Failed to setup periodic tasks: {str(e)}")
    
    def _initialize_services(self):
        """Initialize core services."""
        
        # Initialize QR Service
        from .services import QRService
        try:
            # Validate QR secret configuration
            from django.conf import settings
            if not hasattr(settings, 'QR_SECRET') or not settings.QR_SECRET:
                logger.warning("QR_SECRET not configured properly")
            else:
                logger.info("QR Service initialized with secret configured")
        except Exception as e:
            logger.error(f"QR Service initialization error: {str(e)}")
        
        # Initialize Telegram service
        try:
            from notifications.telegram import telegram_service
            logger.info("Telegram notification service initialized")
        except Exception as e:
            logger.error(f"Telegram service initialization error: {str(e)}")
        
        # Initialize Google Sheets service
        try:
            from integrations.google_sheets import sheets_service
            logger.info("Google Sheets service initialized")
        except Exception as e:
            logger.error(f"Google Sheets service initialization error: {str(e)}")
        
        # Initialize Cloudinary service
        try:
            from integrations.cloudinary import CloudinaryService
            logger.info("Cloudinary service initialized")
        except Exception as e:
            logger.error(f"Cloudinary service initialization error: {str(e)}")
        
    
    def _setup_periodic_tasks(self):
        """Setup periodic tasks using Celery Beat."""
        
        try:
            from django.conf import settings
            
            # Only setup in production or when Celery is configured
            if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
                from celery.schedules import crontab
                
                # Update beat schedule dynamically
                beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
                
                # Add default schedules if not present
                default_schedules = {
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
                
                # Add missing schedules
                for schedule_name, schedule_config in default_schedules.items():
                    if schedule_name not in beat_schedule:
                        beat_schedule[schedule_name] = schedule_config
                
                settings.CELERY_BEAT_SCHEDULE = beat_schedule
                logger.info(f"Configured {len(default_schedules)} periodic tasks")
            
        except Exception as e:
            logger.error(f"Failed to setup periodic tasks: {str(e)}")
    
    def _validate_configuration(self):
        """Validate application configuration."""
        
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        
        required_settings = [
            'TELEGRAM_BOT_TOKEN',
            'QR_SECRET',
            'ADMIN_TG_IDS',
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not hasattr(settings, setting) or not getattr(settings, setting):
                missing_settings.append(setting)
        
        if missing_settings:
            logger.warning(
                f"Missing required settings: {', '.join(missing_settings)}. "
                "Some features may not work properly."
            )
        
        # Validate Telegram admin IDs
        try:
            admin_ids = getattr(settings, 'ADMIN_TG_IDS', [])
            if not isinstance(admin_ids, list) or not admin_ids:
                logger.warning("ADMIN_TG_IDS should be a non-empty list of integers")
            else:
                for admin_id in admin_ids:
                    if not isinstance(admin_id, int):
                        logger.warning(f"Invalid admin Telegram ID: {admin_id}")
        except Exception as e:
            logger.error(f"Error validating admin IDs: {str(e)}")
        
        # Validate database configuration
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            logger.info("Database connection validated successfully")
        except Exception as e:
            logger.error(f"Database connection validation failed: {str(e)}")
        
        # Validate timezone configuration
        try:
            import pytz
            timezone_name = getattr(settings, 'TIME_ZONE', 'UTC')
            pytz.timezone(timezone_name)
            logger.info(f"Timezone configuration validated: {timezone_name}")
        except Exception as e:
            logger.error(f"Invalid timezone configuration: {str(e)}")
    
    def _setup_logging_configuration(self):
        """Setup additional logging configuration."""
        
        import logging.config
        from django.conf import settings
        
        # Add custom log filters and formatters if needed
        try:
            # Custom formatter for structured logging
            class StructuredFormatter(logging.Formatter):
                def format(self, record):
                    # Add structured data to log records
                    if hasattr(record, 'extra_data'):
                        record.msg = f"{record.msg} | {record.extra_data}"
                    return super().format(record)
            
            # Add formatter to existing handlers
            for handler in logging.getLogger().handlers:
                if hasattr(handler, 'setFormatter'):
                    handler.setFormatter(StructuredFormatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    ))
            
            logger.info("Custom logging configuration applied")
            
        except Exception as e:
            logger.error(f"Failed to setup custom logging: {str(e)}")
    
    def _register_custom_checks(self):
        """Register custom Django system checks."""
        
        from django.core.checks import register, Error, Warning
        from django.conf import settings
        
        @register()
        def check_qr_secret_configuration(app_configs, **kwargs):
            """Check QR secret configuration."""
            errors = []
            
            qr_secret = getattr(settings, 'QR_SECRET', None)
            if not qr_secret:
                errors.append(
                    Error(
                        'QR_SECRET setting is not configured',
                        hint='Set QR_SECRET in your settings file',
                        id='core.E001',
                    )
                )
            elif len(qr_secret) < 32:
                errors.append(
                    Warning(
                        'QR_SECRET is shorter than recommended (32+ characters)',
                        hint='Use a longer secret for better security',
                        id='core.W001',
                    )
                )
            
            return errors
        
        @register()
        def check_telegram_configuration(app_configs, **kwargs):
            """Check Telegram configuration."""
            errors = []
            
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            if not bot_token:
                errors.append(
                    Error(
                        'TELEGRAM_BOT_TOKEN setting is not configured',
                        hint='Set TELEGRAM_BOT_TOKEN in your settings file',
                        id='core.E002',
                    )
                )
            
            admin_ids = getattr(settings, 'ADMIN_TG_IDS', [])
            if not admin_ids:
                errors.append(
                    Warning(
                        'ADMIN_TG_IDS setting is empty',
                        hint='Set at least one admin Telegram ID',
                        id='core.W002',
                    )
                )
            
            return errors
        
        @register()
        def check_meal_windows_configuration(app_configs, **kwargs):
            """Check meal windows configuration."""
            errors = []
            
            meal_windows = getattr(settings, 'DEFAULT_MEAL_WINDOWS', {})
            required_meals = ['BREAKFAST', 'LUNCH', 'DINNER']
            
            for meal in required_meals:
                if meal not in meal_windows:
                    errors.append(
                        Warning(
                            f'Missing meal window configuration for {meal}',
                            hint=f'Add {meal} configuration to DEFAULT_MEAL_WINDOWS',
                            id=f'core.W003',
                        )
                    )
            
            return errors
        
        logger.info("Custom Django checks registered")
    
    def _setup_cache_configuration(self):
        """Setup cache configuration and warming."""
        
        from django.core.cache import cache
        
        try:
            # Test cache connectivity
            cache.set('startup_test', 'ok', 10)
            if cache.get('startup_test') == 'ok':
                logger.info("Cache system is working properly")
                cache.delete('startup_test')
            else:
                logger.warning("Cache system test failed")
            
            # Warm up frequently accessed data
            self._warm_up_cache()
            
        except Exception as e:
            logger.error(f"Cache configuration error: {str(e)}")
    

    def _warm_up_cache(self):
        """Warm up cache with frequently accessed data."""
        
        try:
            from django.core.cache import cache
            from .models import Settings
            
            # Cache system settings
            settings_obj = Settings.get_settings()
            cache.set('system_settings', settings_obj, 3600)  # 1 hour
            
            # Cache meal windows
            from django.conf import settings
            meal_windows = getattr(settings, 'DEFAULT_MEAL_WINDOWS', {})
            cache.set('meal_windows', meal_windows, 3600)
            
            logger.info("Cache warmed up successfully")
            
        except Exception as e:
            logger.error(f"Cache warm-up failed: {str(e)}")
    
    def _setup_metrics_collection(self):
        """Setup metrics collection for monitoring."""
        
        try:
            # Initialize metrics collectors
            from django.core.cache import cache
            
            # Reset daily metrics at startup
            from django.utils import timezone
            metrics_key = 'daily_metrics'
            daily_metrics = {
                'app_starts': cache.get('app_starts', 0) + 1,
                'last_startup': timezone.now().isoformat(),
            }
            cache.set('app_starts', daily_metrics['app_starts'], 86400)  # 24 hours
            cache.set(metrics_key, daily_metrics, 86400)
            
            logger.info(f"Metrics initialized - App starts: {daily_metrics['app_starts']}")
            
        except Exception as e:
            logger.error(f"Metrics setup failed: {str(e)}")
    
    def ready(self):
        """Complete application initialization."""
        
        logger.info("Initializing Core application...")
        
        # Run all initialization steps
        initialization_steps = [
            ('Connecting signals', self._connect_signals),
            ('Initializing services', self._initialize_services),
            ('Validating configuration', self._validate_configuration),
            ('Setting up periodic tasks', self._setup_periodic_tasks),
            ('Configuring logging', self._setup_logging_configuration),
            ('Registering custom checks', self._register_custom_checks),
            ('Setting up cache', self._setup_cache_configuration),
            ('Setting up metrics', self._setup_metrics_collection),
        ]
        
        successful_steps = 0
        for step_name, step_function in initialization_steps:
            try:
                step_function()
                successful_steps += 1
                logger.debug(f"✓ {step_name}")
            except Exception as e:
                logger.error(f"✗ {step_name}: {str(e)}")
        
        logger.info(
            f"Core application initialization completed: "
            f"{successful_steps}/{len(initialization_steps)} steps successful"
        )
    
    def _connect_signals(self):
        """Connect Django signals."""
        from . import signals
        signals.connect_signals()