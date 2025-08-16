from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import os

from core.models import Settings, Student, StaffToken


class Command(BaseCommand):
    help = 'Setup initial data for the mess management system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser account',
        )
        parser.add_argument(
            '--create-staff-token',
            action='store_true',
            help='Create initial staff token',
        )
        parser.add_argument(
            '--setup-settings',
            action='store_true',
            help='Setup default system settings',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Setup all initial data',
        )

    def handle(self, *args, **options):
        """Setup initial data based on options."""
        
        if options['all']:
            options['create_superuser'] = True
            options['create_staff_token'] = True
            options['setup_settings'] = True

        if options['setup_settings']:
            self.setup_default_settings()

        if options['create_superuser']:
            self.create_superuser()

        if options['create_staff_token']:
            self.create_staff_token()

        self.stdout.write(
            self.style.SUCCESS('Initial data setup completed successfully!')
        )

    def setup_default_settings(self):
        """Create default system settings."""
        from datetime import time
        
        # Default meal timings
        default_meals = {
            'breakfast': {
                'start': '07:00',
                'end': '09:30',
                'enabled': True
            },
            'lunch': {
                'start': '12:00',
                'end': '14:30',
                'enabled': True
            },
            'dinner': {
                'start': '19:00',
                'end': '21:30',
                'enabled': True
            }
        }
        
        # Check if settings already exist
        if Settings.objects.exists():
            self.stdout.write(
                self.style.WARNING('Settings already exist, skipping creation')
            )
            return
        
        # Create or update the singleton settings instance
        settings_instance = Settings.objects.create(
            tz='Asia/Kolkata',
            cutoff_time=time(23, 0),  # 11:00 PM cutoff
            qr_secret_version=1,
            qr_secret_hash='default-hash-change-in-production',
            meals=default_meals
        )
        
        self.stdout.write(
            self.style.SUCCESS('Created default system settings')
        )
        self.stdout.write(f"Timezone: {settings_instance.tz}")
        self.stdout.write(f"Cutoff time: {settings_instance.cutoff_time}")
        self.stdout.write(f"Meal timings configured: {len(default_meals)} meals")

    def create_superuser(self):
        """Create a superuser if none exists."""
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING('Superuser already exists, skipping creation')
            )
            return

        username = input('Enter superuser username (default: admin): ') or 'admin'
        email = input('Enter superuser email: ')
        
        if not email:
            email = 'admin@example.com'
            self.stdout.write(f'Using default email: {email}')

        password = input('Enter superuser password (default: admin123): ') or 'admin123'

        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully')
        )

    def create_staff_token(self):
        """Create an initial staff token."""
        if StaffToken.objects.exists():
            self.stdout.write(
                self.style.WARNING('Staff tokens already exist, skipping creation')
            )
            return

        token = StaffToken.objects.create(
            label='Initial Scanner Token',
            expires_at=timezone.now() + timedelta(days=30),
            active=True
        )

        self.stdout.write(
            self.style.SUCCESS(f'Created staff token: {token.label}')
        )
        self.stdout.write(
            self.style.WARNING(
                'Remember to generate a proper scanner URL using the admin panel'
            )
        )