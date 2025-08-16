"""
Django management command to ensure database is migrated
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.db.utils import OperationalError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ensure database is migrated'

    def handle(self, *args, **options):
        """Run migrations if needed"""
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Run migrations
            call_command('migrate', verbosity=1, interactive=False)
            self.stdout.write(
                self.style.SUCCESS('Database migrations completed successfully')
            )
            
        except OperationalError as e:
            self.stdout.write(
                self.style.ERROR(f'Database connection failed: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Migration failed: {e}')
            )
