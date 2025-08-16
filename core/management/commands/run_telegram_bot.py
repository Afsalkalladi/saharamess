from django.core.management.base import BaseCommand
from django.conf import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the Telegram bot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--webhook',
            action='store_true',
            help='Run bot with webhook (for production)',
        )
        parser.add_argument(
            '--polling',
            action='store_true',
            help='Run bot with polling (for development)',
        )

    def handle(self, *args, **options):
        from core.telegram_bot import bot_instance

        if options['webhook']:
            self.stdout.write(
                self.style.SUCCESS('Starting Telegram bot with webhook...')
            )
            
            webhook_url = getattr(settings, 'TELEGRAM_WEBHOOK_URL', '')
            if not webhook_url:
                self.stdout.write(
                    self.style.ERROR('TELEGRAM_WEBHOOK_URL not configured')
                )
                return
            
            try:
                bot_instance.run_webhook(webhook_url)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('Bot stopped by user')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Bot error: {str(e)}')
                )
                
        elif options['polling']:
            self.stdout.write(
                self.style.SUCCESS('Starting Telegram bot with polling...')
            )
            
            try:
                bot_instance.run_polling()
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('Bot stopped by user')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Bot error: {str(e)}')
                )
        else:
            # Auto-detect based on environment
            webhook_url = getattr(settings, 'TELEGRAM_WEBHOOK_URL', '')
            
            if webhook_url and not settings.DEBUG:
                self.stdout.write(
                    self.style.SUCCESS('Auto-detected: Running with webhook')
                )
                try:
                    bot_instance.run_webhook(webhook_url)
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Webhook failed: {str(e)}')
                    )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Auto-detected: Running with polling')
                )
                try:
                    bot_instance.run_polling()
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Polling failed: {str(e)}')
                    )