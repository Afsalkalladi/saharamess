import json
import time
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings
from core.models import AuditLog

logger = logging.getLogger(__name__)


class APILoggingMiddleware(MiddlewareMixin):
    """Middleware to log all API requests and responses."""
    
    def process_request(self, request):
        # Only log API requests
        if request.path.startswith('/api/'):
            request._start_time = time.time()
            
            # Log request details
            log_data = {
                'method': request.method,
                'path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': self.get_client_ip(request),
                'query_params': dict(request.GET),
            }
            
            # Log request body for POST/PUT/PATCH
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    if request.content_type == 'application/json':
                        body = json.loads(request.body.decode('utf-8'))
                        # Remove sensitive data
                        if 'password' in body:
                            body['password'] = '***'
                        log_data['body'] = body
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data['body'] = 'Unable to parse body'
            
            logger.info(f"API Request: {json.dumps(log_data)}")
        
        return None
    
    def process_response(self, request, response):
        # Only log API responses
        if request.path.startswith('/api/') and hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            log_data = {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'response_size': len(response.content) if hasattr(response, 'content') else 0
            }
            
            # Log response for errors
            if response.status_code >= 400:
                try:
                    if hasattr(response, 'content'):
                        content = response.content.decode('utf-8')
                        if content:
                            log_data['response'] = json.loads(content)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data['response'] = 'Unable to parse response'
            
            logger.info(f"API Response: {json.dumps(log_data)}")
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RateLimitMiddleware(MiddlewareMixin):
    """Simple rate limiting middleware for API endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Only apply rate limiting to API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Skip rate limiting for staff scanner (they have tokens)
        if request.path.startswith('/api/v1/scanner/'):
            return None
        
        # Get client identifier
        client_id = self.get_client_identifier(request)
        
        # Different limits for different endpoints
        limit_key, max_requests, window_seconds = self.get_rate_limit_config(request)
        
        # Check rate limit
        cache_key = f"rate_limit:{limit_key}:{client_id}"
        current_requests = cache.get(cache_key, 0)
        
        if current_requests >= max_requests:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'detail': f'Maximum {max_requests} requests per {window_seconds} seconds'
            }, status=429)
        
        # Increment counter
        cache.set(cache_key, current_requests + 1, window_seconds)
        
        return None
    
    def get_client_identifier(self, request):
        """Get unique identifier for rate limiting."""
        # Use IP address as identifier
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Include user ID if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"{ip}:user_{request.user.id}"
        
        return ip
    
    def get_rate_limit_config(self, request):
        """Get rate limit configuration for different endpoints."""
        path = request.path
        method = request.method
        
        # Telegram webhook - higher limit
        if path == '/telegram/webhook':
            return 'telegram_webhook', 1000, 60  # 1000 per minute
        
        # Registration endpoint - moderate limit
        if path == '/api/v1/telegram/register':
            return 'registration', 10, 300  # 10 per 5 minutes
        
        # Payment upload - moderate limit
        if path == '/api/v1/telegram/upload-payment':
            return 'payment_upload', 20, 300  # 20 per 5 minutes
        
        # Admin endpoints - higher limit
        if '/admin/' in path:
            return 'admin_api', 200, 60  # 200 per minute
        
        # General API - standard limit
        return 'general_api', 100, 60  # 100 per minute


class CORSMiddleware(MiddlewareMixin):
    """Custom CORS middleware for API endpoints."""
    
    def process_response(self, request, response):
        # Only apply CORS headers to API endpoints
        if request.path.startswith('/api/') or request.path.startswith('/scanner/'):
            # Allow origins
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            origin = request.META.get('HTTP_ORIGIN')
            
            if origin in allowed_origins or settings.DEBUG:
                response['Access-Control-Allow-Origin'] = origin or '*'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Requested-With'
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Max-Age'] = '86400'
        
        return response
    
    def process_request(self, request):
        # Handle preflight OPTIONS requests
        if request.method == 'OPTIONS' and (request.path.startswith('/api/') or request.path.startswith('/scanner/')):
            response = JsonResponse({})
            
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            origin = request.META.get('HTTP_ORIGIN')
            
            if origin in allowed_origins or settings.DEBUG:
                response['Access-Control-Allow-Origin'] = origin or '*'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-Requested-With'
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Max-Age'] = '86400'
            
            return response
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to API responses."""
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy for API endpoints
        if request.path.startswith('/api/'):
            response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none';"
        
        # Scanner pages need more permissive CSP
        elif request.path.startswith('/scanner/'):
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                "connect-src 'self';"
            )
        
        return response


class RequestValidationMiddleware(MiddlewareMixin):
    """Validate API requests for common security issues."""
    
    def process_request(self, request):
        # Only validate API requests
        if not request.path.startswith('/api/'):
            return None
        
        # Check content length
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                content_length = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB
                
                if content_length > max_size:
                    return JsonResponse({
                        'error': 'Request too large',
                        'detail': f'Maximum request size is {max_size} bytes'
                    }, status=413)
            except ValueError:
                pass
        
        # Validate Content-Type for POST/PUT/PATCH
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.content_type
            
            allowed_types = [
                'application/json',
                'application/x-www-form-urlencoded',
                'multipart/form-data'
            ]
            
            if content_type and not any(ct in content_type for ct in allowed_types):
                return JsonResponse({
                    'error': 'Unsupported content type',
                    'detail': f'Content-Type {content_type} is not supported'
                }, status=415)
        
        return None


class AuditMiddleware(MiddlewareMixin):
    """Audit critical API operations."""
    
    def process_response(self, request, response):
        # Only audit specific endpoints
        audit_paths = [
            '/api/v1/students/',
            '/api/v1/payments/',
            '/api/v1/admin/',
            '/api/v1/scanner/scan'
        ]
        
        should_audit = any(request.path.startswith(path) for path in audit_paths)
        
        if should_audit and request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            try:
                # Determine actor
                actor_type = 'SYSTEM'
                actor_id = None
                
                if hasattr(request, 'user') and request.user.is_authenticated:
                    if hasattr(request.user, 'staff_token'):
                        actor_type = 'STAFF'
                        actor_id = str(request.user.staff_token.id)
                    elif hasattr(request.user, 'telegram_id'):
                        actor_type = 'ADMIN'
                        actor_id = str(request.user.telegram_id)
                
                # Create audit log
                AuditLog.objects.create(
                    actor_type=actor_type,
                    actor_id=actor_id,
                    event_type=f"{request.method}_{request.path.replace('/api/v1/', '').replace('/', '_')}",
                    payload={
                        'path': request.path,
                        'method': request.method,
                        'status_code': response.status_code,
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
                    }
                )
            except Exception as e:
                logger.error(f"Failed to create audit log: {str(e)}")
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip