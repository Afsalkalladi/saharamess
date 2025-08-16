"""
URL configuration for mess_management project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from core.views import telegram_webhook
from scanner.views import scanner_page
from admin_panel.views import admin_dashboard

# API Router
router = DefaultRouter()

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/', include(router.urls)),
    path('api/v1/', include('api.v1.urls')),
    
    # Telegram Webhook
    path('webhook/', telegram_webhook, name='telegram_webhook'),
    path('telegram/webhook/', telegram_webhook, name='telegram_webhook_alt'),
    
    # Scanner Interface
    path('scanner/', scanner_page, name='scanner_page'),
    
    # Admin Dashboard
    path('dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # Root redirect
    path('', scanner_page, name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)