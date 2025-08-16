"""
URL patterns for Telegram webhook endpoints
"""

from django.urls import path
from integrations.telegram_webhook import telegram_webhook

urlpatterns = [
    path('telegram/webhook/', telegram_webhook, name='telegram_webhook'),
]
