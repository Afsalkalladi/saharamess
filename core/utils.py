import re
import hashlib
import secrets
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def validate_roll_number(roll_no: str) -> bool:
    """Validate roll number format."""
    if not roll_no:
        return False
    
    # Roll number should be alphanumeric, 4-20 characters
    pattern = r'^[A-Z0-9]{4,20}$'
    return bool(re.match(pattern, roll_no.upper()))


def validate_phone_number(phone: str) -> bool:
    """Validate phone number format."""
    if not phone:
        return False
    
    # International format: +91XXXXXXXXXX or XXXXXXXXXX
    pattern = r'^(\+91|91)?[6-9]\d{9}$'
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(pattern, cleaned_phone))


def clean_phone_number(phone: str) -> str:
    """Clean and format phone number."""
    if not phone:
        return phone
    
    # Remove all non-digits except +
    cleaned = re.sub(r'[^\d\+]', '', phone)
    
    # Add +91 if not present
    if not cleaned.startswith('+'):
        if cleaned.startswith('91') and len(cleaned) == 12:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+91' + cleaned
    
    return cleaned


def format_currency(amount: float, currency: str = 'INR') -> str:
    """Format currency amount."""
    if currency == 'INR':
        return f"₹{amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def calculate_date_range(days: int, from_date: datetime = None) -> tuple:
    """Calculate date range from given date."""
    if from_date is None:
        from_date = timezone.now().date()
    
    end_date = from_date + timedelta(days=days)
    return from_date, end_date


def is_cutoff_time_passed(cutoff_time: str = None) -> bool:
    """Check if cutoff time has passed for today."""
    if cutoff_time is None:
        cutoff_time = settings.MESS_CUTOFF_TIME
    
    now = timezone.now()
    cutoff_hour, cutoff_minute = map(int, cutoff_time.split(':'))
    cutoff_datetime = now.replace(hour=cutoff_hour, minute=cutoff_minute, second=0, microsecond=0)
    
    return now >= cutoff_datetime


def get_current_meal_window() -> Optional[str]:
    """Get current meal window based on time."""
    now = timezone.now().time()
    
    meal_windows = getattr(settings, 'DEFAULT_MEAL_WINDOWS', {
        'BREAKFAST': {'start': '07:00', 'end': '09:30'},
        'LUNCH': {'start': '12:00', 'end': '14:30'},
        'DINNER': {'start': '19:00', 'end': '21:30'},
    })
    
    for meal, window in meal_windows.items():
        start_time = datetime.strptime(window['start'], '%H:%M').time()
        end_time = datetime.strptime(window['end'], '%H:%M').time()
        
        if start_time <= now <= end_time:
            return meal
    
    return None


def get_next_meal_window() -> Optional[Dict[str, Any]]:
    """Get the next upcoming meal window."""
    now = timezone.now().time()
    
    meal_windows = getattr(settings, 'DEFAULT_MEAL_WINDOWS', {
        'BREAKFAST': {'start': '07:00', 'end': '09:30'},
        'LUNCH': {'start': '12:00', 'end': '14:30'},
        'DINNER': {'start': '19:00', 'end': '21:30'},
    })
    
    upcoming_meals = []
    
    for meal, window in meal_windows.items():
        start_time = datetime.strptime(window['start'], '%H:%M').time()
        end_time = datetime.strptime(window['end'], '%H:%M').time()
        
        if now < start_time:
            upcoming_meals.append({
                'meal': meal,
                'start_time': start_time,
                'end_time': end_time,
                'window': window
            })
    
    if upcoming_meals:
        # Return the earliest upcoming meal
        return min(upcoming_meals, key=lambda x: x['start_time'])
    
    # If no meals today, return tomorrow's breakfast
    return {
        'meal': 'BREAKFAST',
        'start_time': datetime.strptime('07:00', '%H:%M').time(),
        'end_time': datetime.strptime('09:30', '%H:%M').time(),
        'window': meal_windows['BREAKFAST'],
        'tomorrow': True
    }


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Limit length
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:95] + ('.' + ext if ext else '')
    
    return sanitized


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """Mask sensitive data like phone numbers or tokens."""
    if not data or len(data) <= visible_chars:
        return data
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)


def generate_qr_payload(student_id: str, version: int, nonce: str) -> str:
    """Generate QR code payload with HMAC."""
    from core.services import QRService
    return QRService.generate_qr_payload_static(student_id, version, nonce)


def verify_qr_payload(payload: str) -> Optional[str]:
    """Verify QR code payload and return student ID."""
    from core.services import QRService
    return QRService.verify_qr_code(payload)


def get_client_ip(request) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def get_user_agent(request) -> str:
    """Get user agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')[:200]  # Limit to 200 chars


def calculate_success_rate(successful: int, total: int) -> float:
    """Calculate success rate percentage."""
    if total == 0:
        return 0.0
    return round((successful / total) * 100, 2)


def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse date string in various formats."""
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def is_business_day(date_obj: datetime) -> bool:
    """Check if given date is a business day (Monday-Friday)."""
    return date_obj.weekday() < 5


def get_business_days_between(start_date: datetime, end_date: datetime) -> int:
    """Count business days between two dates."""
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if is_business_day(current_date):
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """Truncate string to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def generate_unique_filename(original_filename: str, prefix: str = '') -> str:
    """Generate unique filename with timestamp and random suffix."""
    import uuid
    from datetime import datetime
    
    # Get file extension
    name, ext = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, '')
    
    # Sanitize original name
    clean_name = re.sub(r'[^\w\-_]', '_', name)[:50]
    
    # Generate unique identifier
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    # Construct filename
    parts = [prefix, clean_name, timestamp, unique_id]
    filename = '_'.join(filter(None, parts))
    
    return f"{filename}.{ext}" if ext else filename


def log_activity(message: str, level: str = 'info', extra_data: Dict[str, Any] = None):
    """Log activity with structured format."""
    log_data = {
        'timestamp': timezone.now().isoformat(),
        'message': message,
        'extra': extra_data or {}
    }
    
    if level == 'debug':
        logger.debug(f"ACTIVITY: {message}", extra=log_data)
    elif level == 'warning':
        logger.warning(f"ACTIVITY: {message}", extra=log_data)
    elif level == 'error':
        logger.error(f"ACTIVITY: {message}", extra=log_data)
    else:
        logger.info(f"ACTIVITY: {message}", extra=log_data)


class ResponseHelper:
    """Helper class for standardized API responses."""
    
    @staticmethod
    def success(data: Any = None, message: str = 'Success', status_code: int = 200) -> Dict[str, Any]:
        """Create success response."""
        response = {
            'success': True,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if data is not None:
            response['data'] = data
        
        return response
    
    @staticmethod
    def error(message: str = 'Error occurred', errors: Dict[str, Any] = None, status_code: int = 400) -> Dict[str, Any]:
        """Create error response."""
        response = {
            'success': False,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if errors:
            response['errors'] = errors
        
        return response
    
    @staticmethod
    def paginated(data: List[Any], page: int, total_pages: int, total_count: int) -> Dict[str, Any]:
        """Create paginated response."""
        return {
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_next': page < total_pages,
                'has_previous': page > 1
            },
            'timestamp': timezone.now().isoformat()
        }