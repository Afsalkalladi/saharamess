from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

# Import models from core app since admin_panel doesn't have its own models
from core.models import Student, Payment, MessCut, ScanEvent, StaffToken, Settings


class AdminPanelSettingsAdmin(admin.ModelAdmin):
    """Admin interface for system settings in admin panel."""
    list_display = ['key', 'value', 'description', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of critical settings."""
        if obj and obj.key in ['MESS_OPEN_TIME', 'MESS_CLOSE_TIME', 'PAYMENT_DEADLINE']:
            return False
        return super().has_delete_permission(request, obj)


class AdminPanelMixin:
    """Mixin for admin panel specific functionality."""
    
    def get_admin_url(self, obj, action='change'):
        """Get admin URL for an object."""
        return reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_{action}', 
                      args=[obj.pk])
    
    def colored_status(self, status, true_text='Active', false_text='Inactive'):
        """Return colored status display."""
        if status:
            return format_html('<span style="color: green; font-weight: bold;">✓ {}</span>', true_text)
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ {}</span>', false_text)


# Customize existing admin classes for admin panel
class AdminPanelStudentAdmin(admin.ModelAdmin, AdminPanelMixin):
    """Enhanced student admin for admin panel."""
    list_display = ['roll_number', 'name', 'email', 'phone', 'status_display', 'registration_date']
    list_filter = ['status', 'registration_date', 'hostel']
    search_fields = ['roll_number', 'name', 'email', 'phone']
    ordering = ['-registration_date']
    
    def status_display(self, obj):
        return self.colored_status(obj.status == Student.Status.APPROVED, 'Approved', 'Pending')
    status_display.short_description = 'Status'


class AdminPanelPaymentAdmin(admin.ModelAdmin, AdminPanelMixin):
    """Enhanced payment admin for admin panel."""
    list_display = ['student', 'amount', 'period', 'status_display', 'uploaded_at', 'verified_at']
    list_filter = ['status', 'period', 'uploaded_at', 'verified_at']
    search_fields = ['student__roll_number', 'student__name', 'transaction_id']
    ordering = ['-uploaded_at']
    
    def status_display(self, obj):
        return self.colored_status(obj.status == Payment.Status.VERIFIED, 'Verified', 'Pending')
    status_display.short_description = 'Status'


class AdminPanelMessCutAdmin(admin.ModelAdmin, AdminPanelMixin):
    """Enhanced mess cut admin for admin panel."""
    list_display = ['student', 'start_date', 'end_date', 'status_display', 'applied_at']
    list_filter = ['status', 'applied_at', 'start_date']
    search_fields = ['student__roll_number', 'student__name', 'reason']
    ordering = ['-applied_at']
    
    def status_display(self, obj):
        return self.colored_status(obj.status == MessCut.Status.APPROVED, 'Approved', 'Pending')
    status_display.short_description = 'Status'


class AdminPanelScanEventAdmin(admin.ModelAdmin, AdminPanelMixin):
    """Enhanced scan event admin for admin panel."""
    list_display = ['student', 'meal_type', 'result_display', 'scanned_at', 'staff_token']
    list_filter = ['meal_type', 'result', 'scanned_at']
    search_fields = ['student__roll_number', 'student__name']
    ordering = ['-scanned_at']
    readonly_fields = ['scanned_at']
    
    def result_display(self, obj):
        colors = {
            ScanEvent.Result.ALLOWED: 'green',
            ScanEvent.Result.DENIED_NO_PAYMENT: 'red',
            ScanEvent.Result.DENIED_MESS_CUT: 'orange',
            ScanEvent.Result.DENIED_INVALID: 'red'
        }
        color = colors.get(obj.result, 'gray')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 
                          color, obj.get_result_display())
    result_display.short_description = 'Result'


class AdminPanelStaffTokenAdmin(admin.ModelAdmin, AdminPanelMixin):
    """Enhanced staff token admin for admin panel."""
    list_display = ['label', 'active_display', 'expires_at', 'issued_at', 'usage_count']
    list_filter = ['active', 'issued_at', 'expires_at']
    search_fields = ['label']
    ordering = ['-issued_at']
    readonly_fields = ['token_hash', 'issued_at']
    
    def active_display(self, obj):
        return self.colored_status(obj.active and obj.is_valid)
    active_display.short_description = 'Status'
    
    def usage_count(self, obj):
        return ScanEvent.objects.filter(staff_token=obj).count()
    usage_count.short_description = 'Scans'


# Note: Models are already registered in core/admin.py
# This file provides admin panel specific functionality and forms