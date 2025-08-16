from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, BaseThrottle
from django.core.cache import cache
from django.conf import settings
import time
import hashlib
import logging

logger = logging.getLogger(__name__)


class AdminRateThrottle(UserRateThrottle):
    """Rate limiting for admin users."""
    scope = 'admin'
    rate = '500/hour'  # High limit for admins
    
    def allow_request(self, request, view):
        """Override to check admin status."""
        # Check if user is admin
        if hasattr(request, 'user') and hasattr(request.user, 'telegram_id'):
            admin_ids = getattr(settings, 'ADMIN_TG_IDS', [])
            if request.user.telegram_id in admin_ids:
                return super().allow_request(request, view)
        
        # If not admin, deny
        return False


class StaffRateThrottle(BaseThrottle):
    """Rate limiting for staff scanner tokens."""
    scope = 'staff'
    rate = '1000/hour'  # High limit for scanner operations
    
    def allow_request(self, request, view):
        """Check rate limit for staff tokens."""
        if not hasattr(request, 'user') or not hasattr(request.user, 'staff_token'):
            return False
        
        # Get staff token
        staff_token = request.user.staff_token
        
        # Create throttle key
        ident = f"staff_token_{staff_token.id}"
        
        # Check rate limit
        return self._check_rate_limit(ident, self.rate)
    
    def _check_rate_limit(self, ident, rate):
        """Check if request should be throttled."""
        # Parse rate (e.g., '1000/hour')
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        
        # Convert period to seconds
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        # Create cache key
        cache_key = f"throttle:{ident}:{int(time.time() // period_seconds)}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        # Increment count
        cache.set(cache_key, current_count + 1, period_seconds)
        return True
    
    def wait(self):
        """Return time to wait before next request."""
        return 60  # 1 minute default


class StudentRateThrottle(BaseThrottle):
    """Rate limiting for student operations."""
    scope = 'student'
    
    def allow_request(self, request, view):
        """Check rate limit for students."""
        # Get client identifier
        ident = self._get_ident(request)
        
        # Different rates for different operations
        if request.path.startswith('/api/v1/telegram/register'):
            return self._check_rate_limit(ident, '5/hour')  # Registration limit
        elif request.path.startswith('/api/v1/telegram/upload-payment'):
            return self._check_rate_limit(ident, '10/hour')  # Payment upload limit
        else:
            return self._check_rate_limit(ident, '100/hour')  # General limit
    
    def _get_ident(self, request):
        """Get client identifier."""
        # Use Telegram user ID if available
        if hasattr(request, 'user') and hasattr(request.user, 'telegram_id'):
            return f"telegram_{request.user.telegram_id}"
        
        # Use IP address as fallback
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        return f"ip_{ip}"
    
    def _check_rate_limit(self, ident, rate):
        """Check if request should be throttled."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        cache_key = f"throttle:{ident}:{int(time.time() // period_seconds)}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        cache.set(cache_key, current_count + 1, period_seconds)
        return True


class ScannerRateThrottle(BaseThrottle):
    """Special rate limiting for QR scanner operations."""
    scope = 'scanner'
    
    def allow_request(self, request, view):
        """Allow high rate for scanner operations."""
        if not request.path.startswith('/api/v1/scanner/'):
            return True
        
        # Get staff token
        if not hasattr(request, 'user') or not hasattr(request.user, 'staff_token'):
            return False
        
        staff_token = request.user.staff_token
        ident = f"scanner_{staff_token.id}"
        
        # High limit for scanner operations (60 scans per minute)
        return self._check_rate_limit(ident, '60/minute')
    
    def _check_rate_limit(self, ident, rate):
        """Check rate limit with sliding window."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600
        }.get(period, 60)
        
        # Use sliding window approach
        now = time.time()
        cache_key = f"scanner_throttle:{ident}"
        
        # Get request timestamps
        timestamps = cache.get(cache_key, [])
        
        # Remove old timestamps
        cutoff = now - period_seconds
        timestamps = [ts for ts in timestamps if ts > cutoff]
        
        # Check if limit exceeded
        if len(timestamps) >= num_requests:
            return False
        
        # Add current timestamp
        timestamps.append(now)
        cache.set(cache_key, timestamps, period_seconds * 2)
        
        return True


class BurstRateThrottle(BaseThrottle):
    """Handle burst traffic with different limits."""
    
    def allow_request(self, request, view):
        """Allow burst traffic with degrading limits."""
        ident = self._get_ident(request)
        
        # Check multiple time windows
        limits = [
            ('5/minute', 'burst'),      # 5 per minute for burst
            ('50/hour', 'sustained'),   # 50 per hour sustained
            ('500/day', 'daily')        # 500 per day total
        ]
        
        for rate, window_type in limits:
            if not self._check_rate_limit(ident, rate, window_type):
                # Log the throttling
                logger.warning(
                    f"Rate limit exceeded: {ident}, window: {window_type}, rate: {rate}",
                    extra={
                        'client_id': ident,
                        'window_type': window_type,
                        'rate': rate,
                        'path': request.path
                    }
                )
                return False
        
        return True
    
    def _get_ident(self, request):
        """Get client identifier."""
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        return hashlib.md5(ip.encode()).hexdigest()[:12]
    
    def _check_rate_limit(self, ident, rate, window_type):
        """Check rate limit for specific window."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        cache_key = f"burst_throttle:{window_type}:{ident}:{int(time.time() // period_seconds)}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        cache.set(cache_key, current_count + 1, period_seconds)
        return True


class TelegramWebhookThrottle(BaseThrottle):
    """Special throttling for Telegram webhook."""
    
    def allow_request(self, request, view):
        """Allow high rate for Telegram webhooks."""
        if request.path != '/telegram/webhook':
            return True
        
        # Very high limit for webhook (1000 per minute)
        ident = 'telegram_webhook'
        return self._check_rate_limit(ident, '1000/minute')
    
    def _check_rate_limit(self, ident, rate):
        """Simple rate checking for webhook."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        period_seconds = 60 if period == 'minute' else 3600
        
        cache_key = f"webhook_throttle:{ident}:{int(time.time() // period_seconds)}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        cache.set(cache_key, current_count + 1, period_seconds)
        return True


class AdaptiveRateThrottle(BaseThrottle):
    """Adaptive rate limiting based on system load."""
    
    def allow_request(self, request, view):
        """Adjust rate limits based on system performance."""
        # Get system load metrics
        load_factor = self._get_system_load()
        
        # Adjust base rate based on load
        base_rate = 100  # requests per hour
        adjusted_rate = max(10, int(base_rate * (1 - load_factor)))
        
        ident = self._get_ident(request)
        return self._check_rate_limit(ident, f'{adjusted_rate}/hour')
    
    def _get_system_load(self):
        """Get system load factor (0.0 to 1.0)."""
        try:
            # Simple cache-based load indicator
            cache_key = 'system_load_factor'
            load_factor = cache.get(cache_key)
            
            if load_factor is None:
                # Calculate load based on active connections, etc.
                # For now, use a simple metric
                load_factor = 0.2  # 20% default load
                cache.set(cache_key, load_factor, 60)  # Cache for 1 minute
            
            return min(1.0, max(0.0, load_factor))
        except:
            return 0.0  # Default to no throttling if calculation fails
    
    def _get_ident(self, request):
        """Get client identifier."""
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def _check_rate_limit(self, ident, rate):
        """Standard rate limit check."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        period_seconds = 3600 if period == 'hour' else 60
        
        cache_key = f"adaptive_throttle:{ident}:{int(time.time() // period_seconds)}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        cache.set(cache_key, current_count + 1, period_seconds)
        return True


class IPBasedRateThrottle(AnonRateThrottle):
    """IP-based rate limiting for anonymous users."""
    scope = 'anon'
    rate = '60/hour'
    
    def get_cache_key(self, request, view):
        """Create cache key based on IP."""
        if self.ident is None:
            return None
        
        return f"throttle_anon_{self.scope}_{self.ident}"


class EndpointSpecificThrottle(BaseThrottle):
    """Different rate limits for different endpoints."""
    
    ENDPOINT_RATES = {
        '/api/v1/scanner/scan': '300/hour',           # High for scanning
        '/api/v1/telegram/register': '5/hour',        # Low for registration
        '/api/v1/telegram/upload-payment': '20/hour', # Medium for payments
        '/api/v1/admin/': '200/hour',                 # High for admin
        '/api/v1/students/': '100/hour',              # Medium for general API
        'default': '50/hour'                          # Default rate
    }
    
    def allow_request(self, request, view):
        """Apply endpoint-specific rate limits."""
        # Find matching endpoint rate
        endpoint_rate = self._get_endpoint_rate(request.path)
        
        # Get client identifier
        ident = self._get_ident(request)
        
        return self._check_rate_limit(ident, endpoint_rate)
    
    def _get_endpoint_rate(self, path):
        """Get rate limit for specific endpoint."""
        for endpoint, rate in self.ENDPOINT_RATES.items():
            if endpoint != 'default' and path.startswith(endpoint):
                return rate
        return self.ENDPOINT_RATES['default']
    
    def _get_ident(self, request):
        """Get client identifier."""
        # Use user ID if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'telegram_id'):
                return f"user_tg_{request.user.telegram_id}"
            elif hasattr(request.user, 'staff_token'):
                return f"staff_{request.user.staff_token.id}"
        
        # Use IP for anonymous
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        
        return f"ip_{ip}"
    
    def _check_rate_limit(self, ident, rate):
        """Standard rate limit check."""
        num_requests, period = rate.split('/')
        num_requests = int(num_requests)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        cache_key = f"endpoint_throttle:{ident}:{int(time.time() // period_seconds)}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= num_requests:
            return False
        
        cache.set(cache_key, current_count + 1, period_seconds)
        return True


# Throttle classes mapping
THROTTLE_CLASSES = {
    'admin': AdminRateThrottle,
    'staff': StaffRateThrottle,
    'student': StudentRateThrottle,