"""
URL patterns for Telegram webhook endpoints
"""

from django.urls import path
from .telegram_views import telegram_webhook, webhook_info, set_webhook, delete_webhook

urlpatterns = [
    path('webhook/', telegram_webhook, name='telegram_webhook'),
    path('webhook/info/', webhook_info, name='webhook_info'),
    path('webhook/set/', set_webhook, name='set_webhook'),
    path('webhook/delete/', delete_webhook, name='delete_webhook'),
]
