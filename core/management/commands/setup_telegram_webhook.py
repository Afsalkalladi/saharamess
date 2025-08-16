"""
Django management command to set up Telegram webhook
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from integrations.telegram_webhook import setup_telegram_webhook, get_webhook_info


class Command(BaseCommand):
    help = 'Set up Telegram webhook for production deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--info',
            action='store_true',
            help='Show current webhook information',
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove webhook (for development)',
        )

    def handle(self, *args, **options):
        if options['info']:
            self.stdout.write("Getting webhook info...")
            info = get_webhook_info()
            
            if 'error' in info:
                self.stdout.write(
                    self.style.ERROR(f"Error: {info['error']}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("Current webhook info:")
                )
                for key, value in info.items():
                    self.stdout.write(f"  {key}: {value}")
                    
        elif options['remove']:
            self.stdout.write("Removing webhook...")
            from integrations.telegram_webhook import remove_telegram_webhook
            
            if remove_telegram_webhook():
                self.stdout.write(
                    self.style.SUCCESS("Webhook removed successfully")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("Failed to remove webhook")
                )
                
        else:
            self.stdout.write("Setting up webhook...")
            
            if not settings.TELEGRAM_BOT_TOKEN:
                self.stdout.write(
                    self.style.ERROR("TELEGRAM_BOT_TOKEN not configured")
                )
                return
                
            if setup_telegram_webhook():
                self.stdout.write(
                    self.style.SUCCESS("Webhook set up successfully")
                )
                
                # Show webhook info
                info = get_webhook_info()
                if 'error' not in info:
                    self.stdout.write(f"Webhook URL: {info.get('url', 'N/A')}")
                    
            else:
                self.stdout.write(
                    self.style.ERROR("Failed to set up webhook")
                )
