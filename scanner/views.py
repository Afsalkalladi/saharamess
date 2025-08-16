import hashlib
import secrets
from datetime import timedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
import logging

from core.models import StaffToken

logger = logging.getLogger(__name__)


def scanner_page(request):
    """
    QR Scanner web interface with token-based access.
    No login required - access via URL with token parameter.
    """
    # Get token from URL parameter
    token = request.GET.get('token')
    
    if not token:
        return render(request, 'scanner/access_denied.html', {
            'error': 'Access token required',
            'message': 'Please use the scanner link provided by your admin.'
        })
    
    # Validate token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    try:
        staff_token = StaffToken.objects.get(token_hash=token_hash, active=True)
        
        # Check if token is expired
        if not staff_token.is_valid:
            return render(request, 'scanner/access_denied.html', {
                'error': 'Token expired',
                'message': 'This scanner link has expired. Please contact admin for a new link.'
            })
            
    except StaffToken.DoesNotExist:
        return render(request, 'scanner/access_denied.html', {
            'error': 'Invalid token',
            'message': 'This scanner link is invalid. Please contact admin for the correct link.'
        })
    
    # Token is valid - show scanner interface
    context = {
        'token': token,
        'staff_token': staff_token,
        'api_base_url': request.build_absolute_uri('/api/v1/'),
        'scanner_info': {
            'label': staff_token.label,
            'expires_at': staff_token.expires_at,
            'valid_until': staff_token.expires_at.strftime('%Y-%m-%d %H:%M') if staff_token.expires_at else 'No expiry'
        }
    }
    
    logger.info(f"Scanner accessed with token: {staff_token.label}")
    return render(request, 'scanner/scanner.html', context)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def staff_access_generator(request):
    """
    Staff access generator for creating scanner tokens.
    Simple password-based access for admins.
    """
    if request.method == 'GET':
        return render(request, 'scanner/access_generator.html')
    
    # POST request - validate credentials and generate token
    password = request.POST.get('password', '')
    label = request.POST.get('label', 'Scanner Device')
    expires_hours = int(request.POST.get('expires_hours', 24))
    
    # Simple password check
    admin_password = getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123')
    
    if password != admin_password:
        return render(request, 'scanner/access_generator.html', {
            'error': 'Invalid password. Contact admin for access.'
        })
    
    try:
        # Generate new staff token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        expires_at = timezone.now() + timedelta(hours=expires_hours)
        
        staff_token = StaffToken.objects.create(
            label=label,
            token_hash=token_hash,
            expires_at=expires_at
        )
        
        # Generate scanner URL
        scanner_url = request.build_absolute_uri(f'/scanner/?token={raw_token}')
        
        context = {
            'success': True,
            'scanner_url': scanner_url,
            'token_info': {
                'label': staff_token.label,
                'expires_at': staff_token.expires_at,
                'raw_token': raw_token,  # Show only once
                'expires_in_hours': expires_hours
            }
        }
        
        logger.info(f"New scanner token generated: {label}")
        return render(request, 'scanner/access_generator.html', context)
        
    except Exception as e:
        logger.error(f"Failed to generate scanner token: {str(e)}")
        return render(request, 'scanner/access_generator.html', {
            'error': f'Failed to generate token: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def revoke_token(request):
    """Revoke a staff token."""
    token_id = request.POST.get('token_id')
    admin_password = request.POST.get('password')
    
    # Validate admin password
    if admin_password != getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123'):
        return JsonResponse({'error': 'Invalid password'}, status=403)
    
    try:
        staff_token = StaffToken.objects.get(id=token_id)
        staff_token.active = False
        staff_token.save()
        
        logger.info(f"Scanner token revoked: {staff_token.label}")
        return JsonResponse({
            'success': True, 
            'message': f'Token "{staff_token.label}" revoked successfully'
        })
        
    except StaffToken.DoesNotExist:
        return JsonResponse({'error': 'Token not found'}, status=404)
    except Exception as e:
        logger.error(f"Failed to revoke token: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def list_tokens(request):
    """List all active staff tokens (admin only)."""
    password = request.GET.get('password')
    
    if password != getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123'):
        return JsonResponse({'error': 'Invalid password'}, status=403)
    
    tokens = StaffToken.objects.filter(active=True).order_by('-created_at')
    
    token_list = []
    for token in tokens:
        token_list.append({
            'id': str(token.id),
            'label': token.label,
            'created_at': token.issued_at.isoformat(),
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'is_valid': token.is_valid,
            'is_expired': token.expires_at and token.expires_at < timezone.now() if token.expires_at else False
        })
    
    return JsonResponse({'tokens': token_list})


def scanner_status(request):
    """Get scanner system status."""
    token = request.GET.get('token')
    
    if not token:
        return JsonResponse({'error': 'Token required'}, status=400)
    
    # Validate token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    try:
        staff_token = StaffToken.objects.get(token_hash=token_hash, active=True)
        
        if not staff_token.is_valid:
            return JsonResponse({
                'valid': False,
                'error': 'Token expired or invalid'
            }, status=401)
        
        # Get system status
        from core.models import Student, Payment, ScanEvent
        
        status_data = {
            'valid': True,
            'token_info': {
                'label': staff_token.label,
                'expires_at': staff_token.expires_at.isoformat() if staff_token.expires_at else None,
                'is_expired': staff_token.expires_at and staff_token.expires_at < timezone.now() if staff_token.expires_at else False
            },
            'system_stats': {
                'total_students': Student.objects.filter(status=Student.Status.APPROVED).count(),
                'valid_payments': Payment.objects.filter(status=Payment.Status.VERIFIED).count(),
                'todays_scans': ScanEvent.objects.filter(scanned_at__date=timezone.now().date()).count(),
                'successful_scans_today': ScanEvent.objects.filter(
                    scanned_at__date=timezone.now().date(),
                    result=ScanEvent.Result.ALLOWED
                ).count()
            },
            'meal_windows': settings.DEFAULT_MEAL_WINDOWS,
            'current_time': timezone.now().isoformat(),
            'server_status': 'operational'
        }
        
        return JsonResponse(status_data)
        
    except StaffToken.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'error': 'Invalid token'
        }, status=401)
    except Exception as e:
        logger.error(f"Scanner status error: {str(e)}")
        return JsonResponse({
            'valid': False,
            'error': 'System error'
        }, status=500)


def offline_page(request):
    """Offline page for PWA support."""
    return render(request, 'scanner/offline.html')


# Service Worker for PWA support
def service_worker(request):
    """Serve service worker for offline functionality."""
    sw_content = '''
const CACHE_NAME = 'mess-scanner-v1';
const urlsToCache = [
    '/scanner/offline/',
    '/static/scanner/css/scanner.css',
    '/static/scanner/js/scanner.js',
    'https://cdnjs.cloudflare.com/ajax/libs/qr-scanner/1.4.2/qr-scanner.umd.min.js'
];

// Install event
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch event
self.addEventListener('fetch', function(event) {
    // Only handle GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    // Handle scanner page requests
    if (event.request.url.includes('/scanner/')) {
        event.respondWith(
            caches.match(event.request)
                .then(function(response) {
                    // Return cached version or fetch from network
                    if (response) {
                        return response;
                    }
                    
                    return fetch(event.request).catch(function() {
                        // If network fails, return offline page
                        return caches.match('/scanner/offline/');
                    });
                }
            )
        );
    }
    
    // Handle API requests with network-first strategy
    else if (event.request.url.includes('/api/')) {
        event.respondWith(
            fetch(event.request)
                .then(function(response) {
                    // If successful, cache the response
                    if (response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME)
                            .then(function(cache) {
                                cache.put(event.request, responseClone);
                            });
                    }
                    return response;
                })
                .catch(function() {
                    // If network fails, try cache
                    return caches.match(event.request);
                })
        );
    }
});

// Background sync for offline scans
self.addEventListener('sync', function(event) {
    if (event.tag === 'background-sync-scans') {
        event.waitUntil(syncOfflineScans());
    }
});

function syncOfflineScans() {
    // Get offline scans from IndexedDB and sync with server
    return new Promise((resolve) => {
        // This would integrate with IndexedDB to sync offline scans
        console.log('Syncing offline scans...');
        resolve();
    });
}

// Push notifications (future feature)
self.addEventListener('push', function(event) {
    const options = {
        body: event.data ? event.data.text() : 'New notification',
        icon: '/static/scanner/img/icon-192x192.png',
        badge: '/static/scanner/img/badge-72x72.png'
    };
    
    event.waitUntil(
        self.registration.showNotification('Mess Scanner', options)
    );
});
    '''
    
    response = HttpResponse(sw_content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


def manifest_json(request):
    """Serve PWA manifest."""
    manifest = {
        "name": "Mess QR Scanner",
        "short_name": "MessScanner",
        "description": "QR code scanner for mess management system",
        "start_url": "/scanner/",
        "display": "standalone",
        "background_color": "#667eea",
        "theme_color": "#667eea",
        "orientation": "portrait",
        "icons": [
            {
                "src": "/static/scanner/img/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/scanner/img/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ],
        "categories": ["food", "utilities"],
        "lang": "en",
        "scope": "/scanner/"
    }
    
    return JsonResponse(manifest)


def scanner_help(request):
    """Scanner help and instructions page."""
    context = {
        'page_title': 'Scanner Help',
        'meal_windows': settings.DEFAULT_MEAL_WINDOWS
    }
    return render(request, 'scanner/help.html', context)


def access_denied(request):
    """Access denied page for invalid tokens."""
    error = request.GET.get('error', 'Access denied')
    message = request.GET.get('message', 'Please contact admin for access.')
    
    context = {
        'error': error,
        'message': message,
        'page_title': 'Access Denied'
    }
    return render(request, 'scanner/access_denied.html', context)