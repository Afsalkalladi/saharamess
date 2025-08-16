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
        try:
            from . import signals
            signals.connect_signals()
            logger.info("Core app initialized successfully")
        except Exception as e:
            logger.error(f"Core app initialization failed: {str(e)}")