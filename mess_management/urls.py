"""
URL configuration for mess_management project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from core.views import (
    StudentViewSet, PaymentViewSet, MessCutViewSet, MessClosureViewSet,
    scan_qr, student_snapshot, regenerate_qr_codes, payment_reports,
    mess_cut_reports, telegram_webhook, register_student, upload_payment
)
from scanner.views import scanner_page, staff_login
from admin_panel.views import admin_dashboard

# API Router
router = DefaultRouter()
router.register(r'students', StudentViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'mess-cuts', MessCutViewSet)
router.register(r'mess-closures', MessClosureViewSet)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/', include(router.urls)),
    path('api/v1/scanner/scan', scan_qr, name='scan_qr'),
    path('api/v1/students/<uuid:student_id>/snapshot', student_snapshot, name='student_snapshot'),
    path('api/v1/admin/qr/regenerate-all', regenerate_qr_codes, name='regenerate_qr_codes'),
    path('api/v1/admin/reports/payments', payment_reports, name='payment_reports'),
    path('api/v1/admin/reports/mess-cuts', mess_cut_reports, name='mess_cut_reports'),
    
    # Telegram Bot
    path('telegram/webhook', telegram_webhook, name='telegram_webhook'),
    path('api/v1/telegram/register', register_student, name='register_student'),
    path('api/v1/telegram/upload-payment', upload_payment, name='upload_payment'),
    
    # Scanner Interface
    path('scanner/', scanner_page, name='scanner_page'),
    path('scanner/login', staff_login, name='staff_login'),
    
    # Admin Dashboard
    path('dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # Root redirect
    path('', scanner_page, name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)