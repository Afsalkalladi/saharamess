from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from datetime import timedelta
import secrets
import hashlib

from core.models import StaffToken, ScanEvent


@admin.register(StaffToken)
class StaffTokenAdminConfig(admin.ModelAdmin):
    """Enhanced admin interface for StaffToken management."""
    
    list_display = [
        'label', 'active_status', 'validity_status', 'issued_at', 
        'expires_at', 'usage_count', 'last_used', 'actions'
    ]
    list_filter = ['active', 'issued_at', 'expires_at']
    search_fields = ['label', 'token_hash']
    ordering = ['-issued_at']
    readonly_fields = ['id', 'token_hash', 'issued_at', 'token_info', 'usage_statistics']
    
    fieldsets = (
        ('Token Information', {
            'fields': ('label', 'active')
        }),
        ('Validity', {
            'fields': ('expires_at',)
        }),
        ('System Information', {
            'fields': ('id', 'token_hash', 'issued_at', 'token_info'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('usage_statistics',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_tokens', 'deactivate_tokens', 'extend_expiry', 'generate_new_token']
    
    def active_status(self, obj):
        """Display active status with color coding."""
        if obj.active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    active_status.short_description = 'Status'
    
    def validity_status(self, obj):
        """Display validity status."""
        if not obj.active:
            return format_html('<span style="color: gray;">Inactive</span>')
        
        if obj.expires_at:
            now = timezone.now()
            if obj.expires_at < now:
                return format_html('<span style="color: red;">Expired</span>')
            elif obj.expires_at < now + timedelta(hours=24):
                return format_html('<span style="color: orange;">Expiring Soon</span>')
            else:
                return format_html('<span style="color: green;">Valid</span>')
        else:
            return format_html('<span style="color: blue;">Never Expires</span>')
    validity_status.short_description = 'Validity'
    
    def usage_count(self, obj):
        """Display usage count."""
        count = ScanEvent.objects.filter(staff_token=obj).count()
        return f"{count} scans"
    usage_count.short_description = 'Usage'
    
    def last_used(self, obj):
        """Display last usage time."""
        last_scan = ScanEvent.objects.filter(staff_token=obj).order_by('-scanned_at').first()
        if last_scan:
            return last_scan.scanned_at.strftime('%Y-%m-%d %H:%M')
        return 'Never used'
    last_used.short_description = 'Last Used'
    
    def actions(self, obj):
        """Custom actions for each token."""
        actions_html = []
        
        if obj.active:
            # Generate scanner URL (without showing the full token)
            scanner_url = reverse('admin:generate_scanner_url', args=[obj.pk])
            actions_html.append(
                f'<a class="button" href="{scanner_url}" target="_blank">Get Scanner URL</a>'
            )
            
            # Deactivate button
            deactivate_url = reverse('admin:deactivate_token', args=[obj.pk])
            actions_html.append(
                f'<a class="button" href="{deactivate_url}" '
                f'onclick="return confirm(\'Are you sure you want to deactivate this token?\')">Deactivate</a>'
            )
        else:
            # Activate button
            activate_url = reverse('admin:activate_token', args=[obj.pk])
            actions_html.append(
                f'<a class="button" href="{activate_url}">Activate</a>'
            )
        
        return format_html(' '.join(actions_html))
    actions.short_description = 'Actions'
    
    def token_info(self, obj):
        """Display detailed token information."""
        info = f"""
        <table>
            <tr><td><strong>Token ID:</strong></td><td>{obj.id}</td></tr>
            <tr><td><strong>Hash (first 12 chars):</strong></td><td>{obj.token_hash[:12]}...</td></tr>
            <tr><td><strong>Created:</strong></td><td>{obj.issued_at}</td></tr>
            <tr><td><strong>Is Valid:</strong></td><td>{'Yes' if obj.is_valid else 'No'}</td></tr>
        </table>
        """
        return format_html(info)
    token_info.short_description = 'Token Details'
    
    def usage_statistics(self, obj):
        """Display usage statistics."""
        scans = ScanEvent.objects.filter(staff_token=obj)
        total_scans = scans.count()
        successful_scans = scans.filter(result=ScanEvent.Result.ALLOWED).count()
        
        today = timezone.now().date()
        today_scans = scans.filter(scanned_at__date=today).count()
        
        week_ago = timezone.now() - timedelta(days=7)
        week_scans = scans.filter(scanned_at__gte=week_ago).count()
        
        success_rate = (successful_scans / total_scans * 100) if total_scans > 0 else 0
        
        stats = f"""
        <table>
            <tr><td><strong>Total Scans:</strong></td><td>{total_scans}</td></tr>
            <tr><td><strong>Successful Scans:</strong></td><td>{successful_scans}</td></tr>
            <tr><td><strong>Success Rate:</strong></td><td>{success_rate:.1f}%</td></tr>
            <tr><td><strong>Today's Scans:</strong></td><td>{today_scans}</td></tr>
            <tr><td><strong>Last 7 Days:</strong></td><td>{week_scans}</td></tr>
        </table>
        """
        return format_html(stats)
    usage_statistics.short_description = 'Usage Statistics'
    
    # Admin actions
    def activate_tokens(self, request, queryset):
        """Activate selected tokens."""
        count = queryset.update(active=True)
        self.message_user(request, f'{count} tokens activated successfully.')
    activate_tokens.short_description = "Activate selected tokens"
    
    def deactivate_tokens(self, request, queryset):
        """Deactivate selected tokens."""
        count = queryset.update(active=False)
        self.message_user(request, f'{count} tokens deactivated successfully.')
    deactivate_tokens.short_description = "Deactivate selected tokens"
    
    def extend_expiry(self, request, queryset):
        """Extend expiry for selected tokens."""
        # This would typically open a form to specify extension period
        count = 0
        for token in queryset:
            if token.expires_at:
                token.expires_at += timedelta(days=7)  # Extend by 7 days
                token.save()
                count += 1
        
        self.message_user(request, f'Extended expiry for {count} tokens by 7 days.')
    extend_expiry.short_description = "Extend expiry by 7 days"
    
    def generate_new_token(self, request, queryset):
        """Generate new tokens for selected entries."""
        count = 0
        for token in queryset:
            # Generate new token hash
            raw_token = secrets.token_urlsafe(32)
            token.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            token.active = True
            token.issued_at = timezone.now()
            token.save()
            count += 1
        
        self.message_user(
            request, 
            f'Generated new tokens for {count} entries. '
            'Note: Old tokens are now invalid.',
            messages.WARNING
        )
    generate_new_token.short_description = "Generate new tokens (invalidates old ones)"
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).prefetch_related('scan_events')


# Custom admin views
@staff_member_required
def generate_scanner_url_view(request, token_id):
    """Generate scanner URL for a token."""
    token = get_object_or_404(StaffToken, id=token_id)
    
    if not token.active or not token.is_valid:
        return JsonResponse({'error': 'Token is not active or has expired'}, status=400)
    
    # For security, we don't store the raw token, so we can't regenerate the URL
    # Instead, we provide instructions
    context = {
        'token': token,
        'instructions': 'Raw token is not stored for security. Use the token generation form to create a new token.'
    }
    
    return render(request, 'admin/scanner_url_info.html', context)


@staff_member_required
def activate_token_view(request, token_id):
    """Activate a specific token."""
    token = get_object_or_404(StaffToken, id=token_id)
    token.active = True
    token.save()
    
    messages.success(request, f'Token "{token.label}" activated successfully.')
    return JsonResponse({'status': 'success', 'message': 'Token activated'})


@staff_member_required
def deactivate_token_view(request, token_id):
    """Deactivate a specific token."""
    token = get_object_or_404(StaffToken, id=token_id)
    token.active = False
    token.save()
    
    messages.success(request, f'Token "{token.label}" deactivated successfully.')
    return JsonResponse({'status': 'success', 'message': 'Token deactivated'})


@staff_member_required
def token_statistics_view(request):
    """Display token usage statistics."""
    from django.db.models import Count, Q
    
    # Calculate statistics
    total_tokens = StaffToken.objects.count()
    active_tokens = StaffToken.objects.filter(active=True).count()
    expired_tokens = StaffToken.objects.filter(
        expires_at__lt=timezone.now(),
        active=True
    ).count()
    
    # Usage statistics
    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)
    
    token_usage = StaffToken.objects.annotate(
        total_scans=Count('scan_events'),
        today_scans=Count('scan_events', filter=Q(scan_events__scanned_at__date=today)),
        week_scans=Count('scan_events', filter=Q(scan_events__scanned_at__gte=week_ago))
    ).order_by('-total_scans')
    
    context = {
        'title': 'Token Statistics',
        'total_tokens': total_tokens,
        'active_tokens': active_tokens,
        'expired_tokens': expired_tokens,
        'token_usage': token_usage[:10],  # Top 10 tokens by usage
    }
    
    return render(request, 'admin/token_statistics.html', context)


@staff_member_required
def bulk_token_management_view(request):
    """Bulk token management interface."""
    if request.method == 'POST':
        action = request.POST.get('action')
        token_ids = request.POST.getlist('token_ids')
        
        if not token_ids:
            messages.error(request, 'No tokens selected.')
            return JsonResponse({'error': 'No tokens selected'}, status=400)
        
        tokens = StaffToken.objects.filter(id__in=token_ids)
        
        if action == 'activate':
            count = tokens.update(active=True)
            messages.success(request, f'Activated {count} tokens.')
        
        elif action == 'deactivate':
            count = tokens.update(active=False)
            messages.success(request, f'Deactivated {count} tokens.')
        
        elif action == 'delete':
            count = tokens.count()
            tokens.delete()
            messages.success(request, f'Deleted {count} tokens.')
        
        elif action == 'extend':
            extend_days = int(request.POST.get('extend_days', 7))
            count = 0
            for token in tokens:
                if token.expires_at:
                    token.expires_at += timedelta(days=extend_days)
                    token.save()
                    count += 1
            messages.success(request, f'Extended expiry for {count} tokens by {extend_days} days.')
        
        return JsonResponse({'status': 'success'})
    
    # GET request - show the management interface
    tokens = StaffToken.objects.all().order_by('-issued_at')
    
    context = {
        'title': 'Bulk Token Management',
        'tokens': tokens,
    }
    
    return render(request, 'admin/bulk_token_management.html', context)


# Register custom URLs
def get_scanner_admin_urls():
    """Get custom admin URLs for scanner management."""
    urls = [
        path('stafftoken/<uuid:token_id>/scanner-url/', generate_scanner_url_view, name='generate_scanner_url'),
        path('stafftoken/<uuid:token_id>/activate/', activate_token_view, name='activate_token'),
        path('stafftoken/<uuid:token_id>/deactivate/', deactivate_token_view, name='deactivate_token'),
        path('token-statistics/', token_statistics_view, name='token_statistics'),
        path('bulk-token-management/', bulk_token_management_view, name='bulk_token_management'),
    ]
    return urls


# Add custom URLs to admin site
from django.contrib.admin import AdminSite

original_get_urls = AdminSite.get_urls

def custom_get_urls(self):
    urls = original_get_urls(self)
    custom_urls = get_scanner_admin_urls()
    return custom_urls + urls

AdminSite.get_urls = custom_get_urls


# Add custom dashboard items
def add_scanner_dashboard_items(request, extra_context=None):
    """Add scanner-related items to admin dashboard."""
    extra_context = extra_context or {}
    
    # Quick statistics
    scanner_stats = {
        'active_tokens': StaffToken.objects.filter(active=True).count(),
        'expired_tokens': StaffToken.objects.filter(
            expires_at__lt=timezone.now(),
            active=True
        ).count(),
        'today_scans': ScanEvent.objects.filter(
            scanned_at__date=timezone.now().date()
        ).count(),
        'successful_scans_today': ScanEvent.objects.filter(
            scanned_at__date=timezone.now().date(),
            result=ScanEvent.Result.ALLOWED
        ).count(),
    }
    
    extra_context['scanner_stats'] = scanner_stats
    
    return extra_context


# Customize admin site
admin.site.site_header = 'Mess Management System'
admin.site.site_title = 'Mess Admin'
admin.site.index_title = 'Administration Dashboard'

# Add scanner section to admin index
admin.site.index_template = 'admin/custom_index.html'