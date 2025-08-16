from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from datetime import timedelta
import json
import csv

from core.models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog
from core.services import MessService, QRService
from notifications.telegram import sync_send_message
from integrations.google_sheets import sheets_service


def admin_required(view_func):
    """Decorator to check if user is admin (has valid Telegram ID)."""
    def wrapper(request, *args, **kwargs):
        # In a real implementation, you'd check session or token
        # For now, we'll use a simple password check
        if not request.session.get('is_admin'):
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_login(request):
    """Admin login page."""
    if request.method == 'POST':
        password = request.POST.get('password')
        # Simple password check (in production, use proper auth)
        if password == getattr(settings, 'ADMIN_DASHBOARD_PASSWORD', 'admin123'):
            request.session['is_admin'] = True
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid password')
    
    return render(request, 'admin_panel/login.html')


def admin_logout(request):
    """Admin logout."""
    request.session.pop('is_admin', None)
    return redirect('admin_login')


@admin_required
def admin_dashboard(request):
    """Main admin dashboard."""
    # Get dashboard statistics
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    stats = {
        'students': {
            'total': Student.objects.count(),
            'approved': Student.objects.filter(status=Student.Status.APPROVED).count(),
            'pending': Student.objects.filter(status=Student.Status.PENDING).count(),
            'denied': Student.objects.filter(status=Student.Status.DENIED).count(),
        },
        'payments': {
            'total': Payment.objects.count(),
            'verified': Payment.objects.filter(status=Payment.Status.VERIFIED).count(),
            'uploaded': Payment.objects.filter(status=Payment.Status.UPLOADED).count(),
            'denied': Payment.objects.filter(status=Payment.Status.DENIED).count(),
        },
        'today': {
            'registrations': Student.objects.filter(created_at__date=today).count(),
            'scans': ScanEvent.objects.filter(scanned_at__date=today).count(),
            'successful_scans': ScanEvent.objects.filter(
                scanned_at__date=today,
                result=ScanEvent.Result.ALLOWED
            ).count(),
        },
        'recent_activity': {
            'last_7_days_scans': ScanEvent.objects.filter(
                scanned_at__date__gte=week_ago
            ).count(),
            'pending_payments': Payment.objects.filter(status=Payment.Status.UPLOADED).count(),
            'active_tokens': StaffToken.objects.filter(active=True).count(),
        }
    }
    
    # Recent activities for the activity feed
    recent_activities = []
    
    # Recent registrations
    recent_registrations = Student.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at')[:5]
    
    for student in recent_registrations:
        recent_activities.append({
            'type': 'registration',
            'message': f"New registration: {student.name} ({student.roll_no})",
            'timestamp': student.created_at,
            'status': student.status
        })
    
    # Recent payments
    recent_payments = Payment.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('student').order_by('-created_at')[:5]
    
    for payment in recent_payments:
        recent_activities.append({
            'type': 'payment',
            'message': f"Payment upload: {payment.student.name} - ₹{payment.amount}",
            'timestamp': payment.created_at,
            'status': payment.status
        })
    
    # Sort activities by timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:10]
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities,
        'page_title': 'Dashboard'
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@admin_required
def students_list(request):
    """Students management page."""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Build queryset
    students = Student.objects.all()
    
    if status_filter != 'all':
        students = students.filter(status=status_filter.upper())
    
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) |
            Q(roll_no__icontains=search_query) |
            Q(room_no__icontains=search_query)
        )
    
    students = students.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(students, 25)
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)
    
    context = {
        'students': students_page,
        'status_filter': status_filter,
        'search_query': search_query,
        'page_title': 'Students Management'
    }
    
    return render(request, 'admin_panel/students.html', context)


@admin_required
@require_http_methods(["POST"])
def approve_student(request, student_id):
    """Approve a student registration."""
    student = get_object_or_404(Student, id=student_id)
    
    if student.status != Student.Status.PENDING:
        return JsonResponse({
            'success': False,
            'error': 'Student is not in pending status'
        })
    
    try:
        # Update status
        student.status = Student.Status.APPROVED
        student.save()
        
        # Generate QR code
        QRService.generate_qr_for_student(student)
        
        # Send notification
        student_data = {
            'name': student.name,
            'tg_user_id': student.tg_user_id
        }
        sync_send_message(
            student.tg_user_id,
            f"✅ Registration Approved!\n\nCongratulations {student.name}! Your mess access is now active."
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Student {student.name} approved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@admin_required
@require_http_methods(["POST"])
def deny_student(request, student_id):
    """Deny a student registration."""
    student = get_object_or_404(Student, id=student_id)
    
    if student.status != Student.Status.PENDING:
        return JsonResponse({
            'success': False,
            'error': 'Student is not in pending status'
        })
    
    try:
        # Update status
        student.status = Student.Status.DENIED
        student.save()
        
        # Send notification
        sync_send_message(
            student.tg_user_id,
            f"❌ Registration Denied\n\nSorry {student.name}, your registration could not be approved."
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Student {student.name} denied'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@admin_required
def payments_list(request):
    """Payments management page."""
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Build queryset
    payments = Payment.objects.select_related('student').all()
    
    if status_filter != 'all':
        payments = payments.filter(status=status_filter.upper())
    
    if search_query:
        payments = payments.filter(
            Q(student__name__icontains=search_query) |
            Q(student__roll_no__icontains=search_query)
        )
    
    payments = payments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    payments_page = paginator.get_page(page_number)
    
    context = {
        'payments': payments_page,
        'status_filter': status_filter,
        'search_query': search_query,
        'page_title': 'Payments Management'
    }
    
    return render(request, 'admin_panel/payments.html', context)


@admin_required
@require_http_methods(["POST"])
def verify_payment(request, payment_id):
    """Verify a payment."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status != Payment.Status.UPLOADED:
        return JsonResponse({
            'success': False,
            'error': 'Payment is not in uploaded status'
        })
    
    try:
        # Update payment
        payment.status = Payment.Status.VERIFIED
        payment.reviewed_at = timezone.now()
        payment.save()
        
        # Send notification
        sync_send_message(
            payment.student.tg_user_id,
            f"✅ Payment Verified!\n\nYour payment has been verified for {payment.cycle_start} to {payment.cycle_end}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Payment verified successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@admin_required
@require_http_methods(["POST"])
def deny_payment(request, payment_id):
    """Deny a payment."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if payment.status != Payment.Status.UPLOADED:
        return JsonResponse({
            'success': False,
            'error': 'Payment is not in uploaded status'
        })
    
    try:
        # Update payment
        payment.status = Payment.Status.DENIED
        payment.reviewed_at = timezone.now()
        payment.save()
        
        # Send notification
        sync_send_message(
            payment.student.tg_user_id,
            f"⚠️ Payment Verification Failed\n\nPlease upload a clearer screenshot."
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Payment denied'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@admin_required
def reports(request):
    """Reports and analytics page."""
    # Get date range
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    if not from_date:
        from_date = (timezone.now() - timedelta(days=30)).date()
    else:
        from_date = timezone.datetime.strptime(from_date, '%Y-%m-%d').date()
    
    if not to_date:
        to_date = timezone.now().date()
    else:
        to_date = timezone.datetime.strptime(to_date, '%Y-%m-%d').date()
    
    # Generate reports
    reports_data = {
        'date_range': {
            'from_date': from_date,
            'to_date': to_date
        },
        'payments': MessService.generate_payment_report({
            'from_date': from_date,
            'to_date': to_date
        }),
        'mess_cuts': MessService.generate_mess_cut_report({
            'from_date': from_date,
            'to_date': to_date
        }),
        'scan_statistics': {
            'total_scans': ScanEvent.objects.filter(
                scanned_at__date__range=[from_date, to_date]
            ).count(),
            'successful_scans': ScanEvent.objects.filter(
                scanned_at__date__range=[from_date, to_date],
                result=ScanEvent.Result.ALLOWED
            ).count(),
            'meal_breakdown': {
                'breakfast': ScanEvent.objects.filter(
                    scanned_at__date__range=[from_date, to_date],
                    meal=ScanEvent.Meal.BREAKFAST,
                    result=ScanEvent.Result.ALLOWED
                ).count(),
                'lunch': ScanEvent.objects.filter(
                    scanned_at__date__range=[from_date, to_date],
                    meal=ScanEvent.Meal.LUNCH,
                    result=ScanEvent.Result.ALLOWED
                ).count(),
                'dinner': ScanEvent.objects.filter(
                    scanned_at__date__range=[from_date, to_date],
                    meal=ScanEvent.Meal.DINNER,
                    result=ScanEvent.Result.ALLOWED
                ).count(),
            }
        }
    }
    
    context = {
        'reports': reports_data,
        'page_title': 'Reports & Analytics'
    }
    
    return render(request, 'admin_panel/reports.html', context)


@admin_required
def export_data(request):
    """Export data as CSV."""
    export_type = request.GET.get('type', 'students')
    
    response = HttpResponse(content_type='text/csv')
    
    if export_type == 'students':
        response['Content-Disposition'] = 'attachment; filename="students.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Name', 'Roll No', 'Room No', 'Phone', 'Status', 'Created At'])
        
        students = Student.objects.all().order_by('roll_no')
        for student in students:
            writer.writerow([
                str(student.id),
                student.name,
                student.roll_no,
                student.room_no,
                student.phone,
                student.status,
                student.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
    
    elif export_type == 'payments':
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Student', 'Roll No', 'Cycle Start', 'Cycle End', 'Amount', 'Status', 'Created At'])
        
        payments = Payment.objects.select_related('student').all().order_by('-created_at')
        for payment in payments:
            writer.writerow([
                str(payment.id),
                payment.student.name,
                payment.student.roll_no,
                payment.cycle_start,
                payment.cycle_end,
                payment.amount,
                payment.status,
                payment.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
    
    elif export_type == 'scan_events':
        response['Content-Disposition'] = 'attachment; filename="scan_events.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Student', 'Roll No', 'Meal', 'Result', 'Scanned At'])
        
        scans = ScanEvent.objects.select_related('student').all().order_by('-scanned_at')[:1000]  # Limit to last 1000
        for scan in scans:
            writer.writerow([
                str(scan.id),
                scan.student.name,
                scan.student.roll_no,
                scan.meal,
                scan.result,
                scan.scanned_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
    
    return response


@admin_required
def settings_page(request):
    """Settings and configuration page."""
    if request.method == 'POST':
        # Handle settings updates
        action = request.POST.get('action')
        
        if action == 'regenerate_qr':
            try:
                # Regenerate all QR codes
                from core.models import Settings
                settings_obj = Settings.get_settings()
                settings_obj.qr_secret_version += 1
                settings_obj.save()
                
                # Update all approved students
                approved_students = Student.objects.filter(status=Student.Status.APPROVED)
                count = 0
                
                for student in approved_students:
                    student.qr_version = settings_obj.qr_secret_version
                    student.save()
                    QRService.generate_qr_for_student(student)
                    count += 1
                
                messages.success(request, f'Regenerated QR codes for {count} students')
                
            except Exception as e:
                messages.error(request, f'Failed to regenerate QR codes: {str(e)}')
        
        elif action == 'backup_to_sheets':
            try:
                # Trigger manual backup
                from core.tasks import backup_critical_data
                backup_critical_data.delay()
                messages.success(request, 'Backup to Google Sheets initiated')
                
            except Exception as e:
                messages.error(request, f'Failed to initiate backup: {str(e)}')
    
    # Get current settings
    staff_tokens = StaffToken.objects.filter(active=True).order_by('-created_at')
    
    context = {
        'staff_tokens': staff_tokens,
        'page_title': 'Settings'
    }
    
    return render(request, 'admin_panel/settings.html', context)