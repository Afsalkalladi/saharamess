from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from core.views import (
    StudentViewSet, PaymentViewSet, MessCutViewSet, MessClosureViewSet,
    scan_qr, student_snapshot, regenerate_qr_codes, payment_reports,
    mess_cut_reports, register_student, upload_payment
)
from .viewsets import StaffTokenViewSet
from .views import APIHealthCheckView, APIStatsView

# API Router for ViewSets
router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='students')
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'mess-cuts', MessCutViewSet, basename='mess-cuts')
router.register(r'mess-closures', MessClosureViewSet, basename='mess-closures')
router.register(r'staff-tokens', StaffTokenViewSet, basename='staff-tokens')

# Custom API endpoints
urlpatterns = [
    # Health and status
    path('health/', APIHealthCheckView.as_view(), name='api_health'),
    path('stats/', APIStatsView.as_view(), name='api_stats'),
    
    # Include router URLs
    path('', include(router.urls)),
    
    # Scanner endpoints
    path('scanner/scan', scan_qr, name='scan_qr'),
    path('scanner/student/<uuid:student_id>/', student_snapshot, name='student_snapshot'),
    
    # Admin endpoints
    path('admin/qr/regenerate-all', regenerate_qr_codes, name='regenerate_qr_codes'),
    path('admin/reports/payments', payment_reports, name='payment_reports'),
    path('admin/reports/mess-cuts', mess_cut_reports, name='mess_cut_reports'),
    
    # Telegram bot endpoints
    path('telegram/register', register_student, name='register_student'),
    path('telegram/upload-payment', upload_payment, name='upload_payment'),
    
    # Telegram webhook
    path('', include('api.v1.telegram_urls')),
]