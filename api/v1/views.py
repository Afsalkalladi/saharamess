from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

from core.models import Student, Payment, MessCut, ScanEvent, StaffToken

logger = logging.getLogger(__name__)


class APIHealthCheckView(APIView):
    """Health check endpoint for monitoring."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Perform health checks on system components."""
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'checks': {}
        }
        
        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_status['checks']['database'] = {
                    'status': 'healthy',
                    'response_time_ms': 0  # Could measure actual time
                }
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # Cache check (Redis)
        try:
            cache.set('health_check', 'ok', 10)
            result = cache.get('health_check')
            if result == 'ok':
                health_status['checks']['cache'] = {
                    'status': 'healthy'
                }
            else:
                raise Exception('Cache test failed')
        except Exception as e:
            health_status['checks']['cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Model counts (basic database connectivity)
        try:
            health_status['checks']['data'] = {
                'status': 'healthy',
                'students_count': Student.objects.count(),
                'payments_count': Payment.objects.count(),
                'active_tokens': StaffToken.objects.filter(active=True).count()
            }
        except Exception as e:
            health_status['checks']['data'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Determine overall status code
        if health_status['status'] == 'healthy':
            status_code = status.HTTP_200_OK
        elif health_status['status'] == 'degraded':
            status_code = status.HTTP_200_OK  # Still operational
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health_status, status=status_code)


class APIStatsView(APIView):
    """API statistics and metrics endpoint."""
    
    permission_classes = [AllowAny]  # Could restrict to admins
    
    def get(self, request):
        """Get system statistics."""
        try:
            # Time range
            now = timezone.now()
            today = now.date()
            yesterday = today - timedelta(days=1)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            stats = {
                'generated_at': now.isoformat(),
                'overview': {
                    'total_students': Student.objects.count(),
                    'approved_students': Student.objects.filter(status=Student.Status.APPROVED).count(),
                    'pending_students': Student.objects.filter(status=Student.Status.PENDING).count(),
                    'total_payments': Payment.objects.count(),
                    'verified_payments': Payment.objects.filter(status=Payment.Status.VERIFIED).count(),
                    'active_staff_tokens': StaffToken.objects.filter(active=True).count()
                },
                'today': {
                    'new_registrations': Student.objects.filter(created_at__date=today).count(),
                    'payments_uploaded': Payment.objects.filter(created_at__date=today).count(),
                    'mess_cuts_applied': MessCut.objects.filter(applied_at__date=today).count(),
                    'scan_events': ScanEvent.objects.filter(scanned_at__date=today).count(),
                    'successful_scans': ScanEvent.objects.filter(
                        scanned_at__date=today,
                        result=ScanEvent.Result.ALLOWED
                    ).count()
                },
                'yesterday': {
                    'scan_events': ScanEvent.objects.filter(scanned_at__date=yesterday).count(),
                    'successful_scans': ScanEvent.objects.filter(
                        scanned_at__date=yesterday,
                        result=ScanEvent.Result.ALLOWED
                    ).count()
                },
                'last_7_days': {
                    'new_students': Student.objects.filter(created_at__date__gte=week_ago).count(),
                    'payments_uploaded': Payment.objects.filter(created_at__date__gte=week_ago).count(),
                    'total_scans': ScanEvent.objects.filter(scanned_at__date__gte=week_ago).count()
                },
                'last_30_days': {
                    'new_students': Student.objects.filter(created_at__date__gte=month_ago).count(),
                    'payments_uploaded': Payment.objects.filter(created_at__date__gte=month_ago).count(),
                    'total_scans': ScanEvent.objects.filter(scanned_at__date__gte=month_ago).count()
                }
            }
            
            # Calculate success rates
            today_total = stats['today']['scan_events']
            today_successful = stats['today']['successful_scans']
            stats['today']['success_rate'] = (
                (today_successful / today_total * 100) if today_total > 0 else 0
            )
            
            yesterday_total = stats['yesterday']['scan_events']
            yesterday_successful = stats['yesterday']['successful_scans']
            stats['yesterday']['success_rate'] = (
                (yesterday_successful / yesterday_total * 100) if yesterday_total > 0 else 0
            )
            
            # Meal-wise breakdown for today
            stats['today']['meals'] = {
                'breakfast': ScanEvent.objects.filter(
                    scanned_at__date=today,
                    meal=ScanEvent.Meal.BREAKFAST,
                    result=ScanEvent.Result.ALLOWED
                ).count(),
                'lunch': ScanEvent.objects.filter(
                    scanned_at__date=today,
                    meal=ScanEvent.Meal.LUNCH,
                    result=ScanEvent.Result.ALLOWED
                ).count(),
                'dinner': ScanEvent.objects.filter(
                    scanned_at__date=today,
                    meal=ScanEvent.Meal.DINNER,
                    result=ScanEvent.Result.ALLOWED
                ).count()
            }
            
            # Pending items that need attention
            stats['pending_actions'] = {
                'registrations_to_review': Student.objects.filter(status=Student.Status.PENDING).count(),
                'payments_to_verify': Payment.objects.filter(status=Payment.Status.UPLOADED).count(),
                'expired_tokens': StaffToken.objects.filter(
                    expires_at__lt=now,
                    active=True
                ).count()
            }
            
            # System health indicators
            stats['health_indicators'] = {
                'avg_daily_scans_last_week': (
                    ScanEvent.objects.filter(scanned_at__date__gte=week_ago).count() / 7
                ),
                'payment_verification_rate': (
                    Payment.objects.filter(status=Payment.Status.VERIFIED).count() /
                    max(Payment.objects.count(), 1) * 100
                ),
                'student_approval_rate': (
                    Student.objects.filter(status=Student.Status.APPROVED).count() /
                    max(Student.objects.count(), 1) * 100
                )
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Failed to generate stats: {str(e)}")
            return Response({
                'error': 'Failed to generate statistics',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class APIInfoView(APIView):
    """API information and documentation endpoint."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get API information."""
        api_info = {
            'name': 'Mess Management System API',
            'version': '1.0.0',
            'description': 'RESTful API for mess management with QR-based access control',
            'documentation': request.build_absolute_uri('/docs/api/'),
            'endpoints': {
                'health': '/api/v1/health/',
                'stats': '/api/v1/stats/',
                'students': '/api/v1/students/',
                'payments': '/api/v1/payments/',
                'mess_cuts': '/api/v1/mess-cuts/',
                'scanner': '/api/v1/scanner/scan',
                'admin': '/api/v1/admin/'
            },
            'authentication': {
                'staff_tokens': 'Bearer token authentication for scanner access',
                'admin_auth': 'Telegram ID based authentication for admin operations'
            },
            'rate_limits': {
                'general_api': '100 requests per minute',
                'admin_api': '200 requests per minute',
                'registration': '10 requests per 5 minutes',
                'payment_upload': '20 requests per 5 minutes'
            },
            'support': {
                'contact': 'admin@messsystem.com',
                'documentation': 'https://docs.messsystem.com',
                'github': 'https://github.com/your-org/mess-management'
            }
        }
        
        return Response(api_info)