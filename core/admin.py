from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
import json

from .models import (
    Student, Payment, MessCut, MessClosure, ScanEvent, 
    StaffToken, AuditLog, Settings, DLQLog
)


class CreatedAtFilter(SimpleListFilter):
    """Filter for created_at dates."""
    title = 'Created Date'
    parameter_name = 'created_at'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('week', 'Past 7 days'),
            ('month', 'Past 30 days'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'yesterday':
            yesterday = now.date() - timezone.timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif self.value() == 'week':
            week_ago = now - timezone.timedelta(days=7)
            return queryset.filter(created_at__gte=week_ago)
        elif self.value() == 'month':
            month_ago = now - timezone.timedelta(days=30)
            return queryset.filter(created_at__gte=month_ago)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Admin interface for Student model."""
    
    list_display = [
        'roll_no', 'name', 'room_no', 'status', 
        'qr_version', 'created_at', 'actions'
    ]
    list_filter = ['status', CreatedAtFilter, 'qr_version']
    search_fields = ['name', 'roll_no', 'room_no', 'phone']
    ordering = ['-created_at']
    readonly_fields = ['id', 'qr_nonce', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'roll_no', 'room_no', 'phone', 'tg_user_id')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('QR Code', {
            'fields': ('qr_version', 'qr_nonce'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_students', 'deny_students', 'regenerate_qr_codes']
    
    def actions(self, obj):
        """Custom actions column."""
        if obj.status == Student.Status.APPROVED:
            qr_url = reverse('admin:generate_qr', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" target="_blank">View QR</a>',
                qr_url
            )
        return '-'
    actions.short_description = 'Actions'
    
    def approve_students(self, request, queryset):
        """Bulk approve students."""
        count = queryset.filter(status=Student.Status.PENDING).update(
            status=Student.Status.APPROVED
        )
        self.message_user(request, f'{count} students approved successfully.')
    approve_students.short_description = "Approve selected students"
    
    def deny_students(self, request, queryset):
        """Bulk deny students."""
        count = queryset.filter(status=Student.Status.PENDING).update(
            status=Student.Status.DENIED
        )
        self.message_user(request, f'{count} students denied.')
    deny_students.short_description = "Deny selected students"
    
    def regenerate_qr_codes(self, request, queryset):
        """Regenerate QR codes for selected students."""
        approved_students = queryset.filter(status=Student.Status.APPROVED)
        count = 0
        
        for student in approved_students:
            student.qr_version += 1
            student.save()
            count += 1
        
        self.message_user(request, f'QR codes regenerated for {count} students.')
    regenerate_qr_codes.short_description = "Regenerate QR codes"
    
    def get_queryset(self, request):
        """Optimize queryset with annotations."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            payment_count=Count('payments'),
            scan_count=Count('scan_events')
        )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment model."""
    
    list_display = [
        'student_roll', 'student_name', 'cycle_period', 
        'amount', 'status', 'source', 'created_at'
    ]
    list_filter = ['status', 'source', CreatedAtFilter]
    search_fields = ['student__name', 'student__roll_no']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'reviewed_at']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('student', 'cycle_start', 'cycle_end', 'amount')
        }),
        ('Status', {
            'fields': ('status', 'source', 'reviewer_admin_id', 'reviewed_at')
        }),
        ('Screenshot', {
            'fields': ('screenshot_url', 'screenshot_preview'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_payments', 'deny_payments']
    
    def student_roll(self, obj):
        """Display student roll number."""
        return obj.student.roll_no
    student_roll.short_description = 'Roll No'
    student_roll.admin_order_field = 'student__roll_no'
    
    def student_name(self, obj):
        """Display student name."""
        return obj.student.name
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__name'
    
    def cycle_period(self, obj):
        """Display payment cycle period."""
        return f"{obj.cycle_start} to {obj.cycle_end}"
    cycle_period.short_description = 'Cycle Period'
    
    def screenshot_preview(self, obj):
        """Display screenshot preview."""
        if obj.screenshot_url:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 200px; max-height: 150px;" />'
                '</a>',
                obj.screenshot_url, obj.screenshot_url
            )
        return 'No screenshot'
    screenshot_preview.short_description = 'Screenshot Preview'
    
    def verify_payments(self, request, queryset):
        """Bulk verify payments."""
        count = queryset.filter(status=Payment.Status.UPLOADED).update(
            status=Payment.Status.VERIFIED,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} payments verified.')
    verify_payments.short_description = "Verify selected payments"
    
    def deny_payments(self, request, queryset):
        """Bulk deny payments."""
        count = queryset.filter(status=Payment.Status.UPLOADED).update(
            status=Payment.Status.DENIED,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} payments denied.')
    deny_payments.short_description = "Deny selected payments"


@admin.register(MessCut)
class MessCutAdmin(admin.ModelAdmin):
    """Admin interface for MessCut model."""
    
    list_display = [
        'student_roll', 'student_name', 'date_range', 
        'duration', 'applied_by', 'applied_at'
    ]
    list_filter = ['applied_by', CreatedAtFilter]
    search_fields = ['student__name', 'student__roll_no']
    ordering = ['-applied_at']
    readonly_fields = ['id', 'applied_at', 'cutoff_ok']
    
    def student_roll(self, obj):
        return obj.student.roll_no
    student_roll.short_description = 'Roll No'
    student_roll.admin_order_field = 'student__roll_no'
    
    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__name'
    
    def date_range(self, obj):
        return f"{obj.from_date} to {obj.to_date}"
    date_range.short_description = 'Date Range'
    
    def duration(self, obj):
        days = (obj.to_date - obj.from_date).days + 1
        return f"{days} day{'s' if days != 1 else ''}"
    duration.short_description = 'Duration'


@admin.register(MessClosure)
class MessClosureAdmin(admin.ModelAdmin):
    """Admin interface for MessClosure model."""
    
    list_display = [
        'date_range', 'duration', 'reason_summary', 
        'created_by_admin_id', 'created_at'
    ]
    list_filter = [CreatedAtFilter]
    search_fields = ['reason']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def date_range(self, obj):
        return f"{obj.from_date} to {obj.to_date}"
    date_range.short_description = 'Date Range'
    
    def duration(self, obj):
        days = (obj.to_date - obj.from_date).days + 1
        return f"{days} day{'s' if days != 1 else ''}"
    duration.short_description = 'Duration'
    
    def reason_summary(self, obj):
        if obj.reason:
            return obj.reason[:50] + ('...' if len(obj.reason) > 50 else '')
        return 'No reason provided'
    reason_summary.short_description = 'Reason'


@admin.register(ScanEvent)
class ScanEventAdmin(admin.ModelAdmin):
    """Admin interface for ScanEvent model."""
    
    list_display = [
        'student_roll', 'student_name', 'meal', 
        'result', 'scanned_at', 'staff_token_label'
    ]
    list_filter = ['meal', 'result', CreatedAtFilter]
    search_fields = ['student__name', 'student__roll_no']
    ordering = ['-scanned_at']
    readonly_fields = ['id', 'scanned_at']
    
    def student_roll(self, obj):
        return obj.student.roll_no
    student_roll.short_description = 'Roll No'
    
    def student_name(self, obj):
        return obj.student.name
    student_name.short_description = 'Student'
    
    def staff_token_label(self, obj):
        return obj.staff_token.label if obj.staff_token else 'N/A'
    staff_token_label.short_description = 'Scanner'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'student', 'staff_token'
        )


@admin.register(StaffToken)
class StaffTokenAdmin(admin.ModelAdmin):
    """Admin interface for StaffToken model."""
    
    list_display = [
        'label', 'active', 'is_expired', 
        'issued_at', 'expires_at', 'usage_count'
    ]
    list_filter = ['active', CreatedAtFilter]
    search_fields = ['label']
    ordering = ['-issued_at']
    readonly_fields = ['id', 'token_hash', 'issued_at', 'usage_count']
    
    def is_expired(self, obj):
        """Check if token is expired."""
        if obj.expires_at:
            is_exp = obj.expires_at < timezone.now()
            if is_exp:
                return format_html('<span style="color: red;">Yes</span>')
            else:
                return format_html('<span style="color: green;">No</span>')
        return 'Never'
    is_expired.short_description = 'Expired'
    
    def usage_count(self, obj):
        """Count scan events using this token."""
        return obj.scan_events.count()
    usage_count.short_description = 'Scans'
    
    actions = ['deactivate_tokens', 'activate_tokens']
    
    def deactivate_tokens(self, request, queryset):
        """Deactivate selected tokens."""
        count = queryset.update(active=False)
        self.message_user(request, f'{count} tokens deactivated.')
    deactivate_tokens.short_description = "Deactivate selected tokens"
    
    def activate_tokens(self, request, queryset):
        """Activate selected tokens."""
        count = queryset.update(active=True)
        self.message_user(request, f'{count} tokens activated.')
    activate_tokens.short_description = "Activate selected tokens"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model."""
    
    list_display = [
        'event_type', 'actor_type', 'actor_id', 
        'created_at', 'payload_summary'
    ]
    list_filter = ['actor_type', 'event_type', CreatedAtFilter]
    search_fields = ['event_type', 'actor_id']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'formatted_payload']
    
    def payload_summary(self, obj):
        """Display payload summary."""
        if obj.payload:
            summary = str(obj.payload)
            return summary[:100] + ('...' if len(summary) > 100 else '')
        return 'Empty'
    payload_summary.short_description = 'Payload'
    
    def formatted_payload(self, obj):
        """Display formatted JSON payload."""
        if obj.payload:
            try:
                formatted = json.dumps(obj.payload, indent=2)
                return format_html('<pre>{}</pre>', formatted)
            except:
                return obj.payload
        return 'Empty'
    formatted_payload.short_description = 'Formatted Payload'


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    """Admin interface for Settings model."""
    
    list_display = ['id', 'tz', 'cutoff_time', 'qr_secret_version']
    readonly_fields = ['id']
    
    def has_add_permission(self, request):
        """Only allow one settings instance."""
        return not Settings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of settings."""
        return False


@admin.register(DLQLog)
class DLQLogAdmin(admin.ModelAdmin):
    """Admin interface for DLQ logs."""
    
    list_display = [
        'operation', 'retry_count', 'processed', 
        'created_at', 'error_summary'
    ]
    list_filter = ['processed', 'operation', CreatedAtFilter]
    search_fields = ['operation', 'error_message']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'formatted_payload']
    
    def error_summary(self, obj):
        """Display error message summary."""
        if obj.error_message:
            return obj.error_message[:100] + ('...' if len(obj.error_message) > 100 else '')
        return 'No error'
    error_summary.short_description = 'Error'
    
    def formatted_payload(self, obj):
        """Display formatted JSON payload."""
        if obj.payload:
            try:
                formatted = json.dumps(obj.payload, indent=2)
                return format_html('<pre>{}</pre>', formatted)
            except:
                return obj.payload
        return 'Empty'
    formatted_payload.short_description = 'Formatted Payload'
    
    actions = ['mark_as_processed', 'retry_operations']
    
    def mark_as_processed(self, request, queryset):
        """Mark selected operations as processed."""
        count = queryset.update(processed=True)
        self.message_user(request, f'{count} operations marked as processed.')
    mark_as_processed.short_description = "Mark as processed"
    
    def retry_operations(self, request, queryset):
        """Retry selected operations."""
        from .tasks import process_sheets_log
        
        count = 0
        for dlq_item in queryset.filter(processed=False):
            try:
                sheet_name = dlq_item.operation.replace('log_to_', '')
                process_sheets_log.delay(sheet_name, dlq_item.payload)
                count += 1
            except Exception as e:
                self.message_user(request, f'Failed to retry {dlq_item.operation}: {str(e)}', level='error')
        
        self.message_user(request, f'{count} operations queued for retry.')
    retry_operations.short_description = "Retry selected operations"


# Custom admin site configuration
admin.site.site_header = 'Mess Management System'
admin.site.site_title = 'Mess Admin'
admin.site.index_title = 'Administration Dashboard'

# Add custom views to admin
from django.urls import path
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def generate_qr_view(request, student_id):
    """Generate and display QR code for a student."""
    student = get_object_or_404(Student, id=student_id)
    
    if student.status != Student.Status.APPROVED:
        return HttpResponse('Student is not approved', status=400)
    
    try:
        from .services import QRService
        qr_image = QRService.generate_qr_for_student(student)
        
        response = HttpResponse(qr_image.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'inline; filename="qr_{student.roll_no}.png"'
        return response
        
    except Exception as e:
        return HttpResponse(f'Error generating QR: {str(e)}', status=500)

@staff_member_required
def system_stats_view(request):
    """Display system statistics."""
    from django.template.response import TemplateResponse
    from django.db.models import Count
    
    today = timezone.now().date()
    
    stats = {
        'students': {
            'total': Student.objects.count(),
            'approved': Student.objects.filter(status=Student.Status.APPROVED).count(),
            'pending': Student.objects.filter(status=Student.Status.PENDING).count(),
            'today': Student.objects.filter(created_at__date=today).count(),
        },
        'payments': {
            'total': Payment.objects.count(),
            'verified': Payment.objects.filter(status=Payment.Status.VERIFIED).count(),
            'pending': Payment.objects.filter(status=Payment.Status.UPLOADED).count(),
            'today': Payment.objects.filter(created_at__date=today).count(),
        },
        'scans': {
            'total': ScanEvent.objects.count(),
            'today': ScanEvent.objects.filter(scanned_at__date=today).count(),
            'successful_today': ScanEvent.objects.filter(
                scanned_at__date=today,
                result=ScanEvent.Result.ALLOWED
            ).count(),
        },
        'tokens': {
            'active': StaffToken.objects.filter(active=True).count(),
            'expired': StaffToken.objects.filter(
                expires_at__lt=timezone.now(),
                active=True
            ).count(),
        }
    }
    
    context = {
        'title': 'System Statistics',
        'stats': stats,
        'opts': {'app_label': 'core'},
    }
    
    return TemplateResponse(request, 'admin/system_stats.html', context)

# Add custom URLs to admin
def get_admin_urls():
    """Get custom admin URLs."""
    urls = [
        path('generate-qr/<uuid:student_id>/', generate_qr_view, name='generate_qr'),
        path('system-stats/', system_stats_view, name='system_stats'),
    ]
    return urls

# Register custom URLs
original_get_urls = admin.site.get_urls
admin.site.get_urls = lambda: get_admin_urls() + original_get_urls()

# Add dashboard customization
def custom_admin_index(request, extra_context=None):
    """Custom admin index with additional context."""
    extra_context = extra_context or {}
    
    # Add quick stats to dashboard
    today = timezone.now().date()
    
    quick_stats = {
        'pending_registrations': Student.objects.filter(status=Student.Status.PENDING).count(),
        'pending_payments': Payment.objects.filter(status=Payment.Status.UPLOADED).count(),
        'todays_scans': ScanEvent.objects.filter(scanned_at__date=today).count(),
        'active_tokens': StaffToken.objects.filter(active=True).count(),
        'dlq_items': DLQLog.objects.filter(processed=False).count(),
    }
    
    extra_context['quick_stats'] = quick_stats
    
    return admin.site.index(request, extra_context)

# Override admin index
admin.site.index = custom_admin_index

# Custom admin actions
def export_selected_as_csv(modeladmin, request, queryset):
    """Export selected items as CSV."""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{modeladmin.model._meta.verbose_name_plural}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    field_names = [field.name for field in modeladmin.model._meta.fields]
    writer.writerow(field_names)
    
    # Write data
    for obj in queryset:
        row = []
        for field_name in field_names:
            value = getattr(obj, field_name)
            if hasattr(value, 'strftime'):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            elif value is None:
                value = ''
            row.append(str(value))
        writer.writerow(row)
    
    return response

export_selected_as_csv.short_description = "Export selected items as CSV"

# Add export action to all admin classes
for admin_class in [StudentAdmin, PaymentAdmin, MessCutAdmin, ScanEventAdmin]:
    if hasattr(admin_class, 'actions') and admin_class.actions:
        if callable(admin_class.actions):
            admin_class.actions = [export_selected_as_csv]
        else:
            admin_class.actions = list(admin_class.actions) + [export_selected_as_csv]
    else:
        admin_class.actions = [export_selected_as_csv]