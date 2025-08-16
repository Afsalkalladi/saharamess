import re
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from typing import Any


def validate_roll_number(value: str) -> None:
    """Validate roll number format."""
    if not value:
        raise ValidationError("Roll number is required.")
    
    # Convert to uppercase for validation
    value = value.upper().strip()
    
    # Check length
    if len(value) < 4 or len(value) > 20:
        raise ValidationError("Roll number must be between 4 and 20 characters.")
    
    # Check format: alphanumeric only
    if not re.match(r'^[A-Z0-9]+$', value):
        raise ValidationError("Roll number must contain only letters and numbers.")
    
    # Additional format checks based on common patterns
    patterns = [
        r'^[A-Z]{2,4}\d{4,8}$',  # Prefix + numbers (e.g., CS2021001)
        r'^\d{4}[A-Z]{2,4}\d{3,6}$',  # Year + dept + number
        r'^[A-Z0-9]{6,15}$'  # General alphanumeric
    ]
    
    if not any(re.match(pattern, value) for pattern in patterns):
        raise ValidationError("Roll number format is not recognized. Please check the format.")


def validate_indian_phone_number(value: str) -> None:
    """Validate Indian phone number."""
    if not value:
        raise ValidationError("Phone number is required.")
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d\+]', '', value)
    
    # Check various Indian phone number formats
    patterns = [
        r'^\+91[6-9]\d{9}$',  # +91XXXXXXXXXX
        r'^91[6-9]\d{9}$',    # 91XXXXXXXXXX
        r'^[6-9]\d{9}$'       # XXXXXXXXXX
    ]
    
    if not any(re.match(pattern, cleaned) for pattern in patterns):
        raise ValidationError(
            "Enter a valid Indian phone number. "
            "Format: +91XXXXXXXXXX or XXXXXXXXXX (10 digits starting with 6-9)"
        )


def validate_room_number(value: str) -> None:
    """Validate room number format."""
    if not value:
        raise ValidationError("Room number is required.")
    
    value = value.strip()
    
    if len(value) < 1 or len(value) > 10:
        raise ValidationError("Room number must be between 1 and 10 characters.")
    
    # Allow alphanumeric, hyphens, and forward slashes
    if not re.match(r'^[A-Za-z0-9\-/]+$', value):
        raise ValidationError("Room number can contain only letters, numbers, hyphens, and forward slashes.")


def validate_student_name(value: str) -> None:
    """Validate student name."""
    if not value:
        raise ValidationError("Name is required.")
    
    value = value.strip()
    
    if len(value) < 2:
        raise ValidationError("Name must be at least 2 characters long.")
    
    if len(value) > 100:
        raise ValidationError("Name cannot exceed 100 characters.")
    
    # Allow letters, spaces, hyphens, and dots
    if not re.match(r'^[A-Za-z\s\.\-]+$', value):
        raise ValidationError("Name can contain only letters, spaces, dots, and hyphens.")


def validate_payment_amount(value: float) -> None:
    """Validate payment amount."""
    if value is None:
        raise ValidationError("Payment amount is required.")
    
    if value <= 0:
        raise ValidationError("Payment amount must be positive.")
    
    if value > 50000:  # Maximum reasonable mess fee
        raise ValidationError("Payment amount seems too high. Maximum allowed is ₹50,000.")
    
    if value < 100:  # Minimum reasonable mess fee
        raise ValidationError("Payment amount seems too low. Minimum allowed is ₹100.")


def validate_payment_cycle_dates(start_date: datetime, end_date: datetime) -> None:
    """Validate payment cycle dates."""
    if not start_date or not end_date:
        raise ValidationError("Both start and end dates are required.")
    
    if start_date >= end_date:
        raise ValidationError("Start date must be before end date.")
    
    # Check if cycle is reasonable (between 15 days and 365 days)
    duration = (end_date - start_date).days
    
    if duration < 15:
        raise ValidationError("Payment cycle must be at least 15 days.")
    
    if duration > 365:
        raise ValidationError("Payment cycle cannot exceed 365 days.")
    
    # Check if start date is not too far in the past
    today = timezone.now().date()
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    if start_date < today - timedelta(days=30):
        raise ValidationError("Start date cannot be more than 30 days in the past.")
    
    if end_date > today + timedelta(days=365):
        raise ValidationError("End date cannot be more than 365 days in the future.")


def validate_mess_cut_dates(from_date: datetime, to_date: datetime) -> None:
    """Validate mess cut dates."""
    if not from_date or not to_date:
        raise ValidationError("Both from and to dates are required.")
    
    if isinstance(from_date, datetime):
        from_date = from_date.date()
    if isinstance(to_date, datetime):
        to_date = to_date.date()
    
    if from_date > to_date:
        raise ValidationError("From date must be before or equal to to date.")
    
    # Check cutoff rule - can only apply for tomorrow onwards
    today = timezone.now().date()
    now = timezone.now()
    
    # Check if cutoff time has passed
    cutoff_time = getattr(settings, 'MESS_CUTOFF_TIME', '23:00')
    cutoff_hour, cutoff_minute = map(int, cutoff_time.split(':'))
    cutoff_datetime = now.replace(hour=cutoff_hour, minute=cutoff_minute, second=0, microsecond=0)
    
    if now >= cutoff_datetime:
        # After cutoff, minimum date is day after tomorrow
        min_date = today + timedelta(days=2)
    else:
        # Before cutoff, minimum date is tomorrow
        min_date = today + timedelta(days=1)
    
    if from_date < min_date:
        raise ValidationError(
            f"Cannot apply mess cut for {from_date}. "
            f"Minimum allowed date is {min_date} due to cutoff rules."
        )
    
    # Check maximum duration (e.g., 30 days)
    duration = (to_date - from_date).days + 1
    if duration > 30:
        raise ValidationError("Mess cut cannot exceed 30 days.")


def validate_qr_code_data(value: str) -> None:
    """Validate QR code data format."""
    if not value:
        raise ValidationError("QR code data is required.")
    
    # QR data should have specific format: version|student_id|timestamp|nonce|signature
    parts = value.split('|')
    
    if len(parts) != 5:
        raise ValidationError("Invalid QR code format.")
    
    version, student_id, timestamp, nonce, signature = parts
    
    # Validate version
    try:
        version_num = int(version)
        if version_num < 1:
            raise ValidationError("Invalid QR code version.")
    except ValueError:
        raise ValidationError("Invalid QR code version format.")
    
    # Validate student ID (UUID format)
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', student_id):
        raise ValidationError("Invalid student ID in QR code.")
    
    # Validate timestamp
    try:
        timestamp_num = int(timestamp)
        if timestamp_num < 1000000000:  # Reasonable timestamp check
            raise ValidationError("Invalid timestamp in QR code.")
    except ValueError:
        raise ValidationError("Invalid timestamp format in QR code.")
    
    # Validate nonce (should be alphanumeric)
    if not re.match(r'^[A-Za-z0-9]+$', nonce):
        raise ValidationError("Invalid nonce in QR code.")
    
    # Validate signature (should be hex)
    if not re.match(r'^[0-9a-f]+$', signature):
        raise ValidationError("Invalid signature in QR code.")


def validate_staff_token_label(value: str) -> None:
    """Validate staff token label."""
    if not value:
        raise ValidationError("Token label is required.")
    
    value = value.strip()
    
    if len(value) < 3:
        raise ValidationError("Token label must be at least 3 characters long.")
    
    if len(value) > 100:
        raise ValidationError("Token label cannot exceed 100 characters.")
    
    # Allow letters, numbers, spaces, hyphens, and underscores
    if not re.match(r'^[A-Za-z0-9\s\-_]+$', value):
        raise ValidationError("Token label can contain only letters, numbers, spaces, hyphens, and underscores.")


def validate_meal_type(value: str) -> None:
    """Validate meal type."""
    valid_meals = ['BREAKFAST', 'LUNCH', 'DINNER']
    
    if value not in valid_meals:
        raise ValidationError(f"Invalid meal type. Must be one of: {', '.join(valid_meals)}")


def validate_image_file(value) -> None:
    """Validate uploaded image file."""
    if not value:
        raise ValidationError("Image file is required.")
    
    # Check file size (max 10MB)
    if value.size > 10 * 1024 * 1024:
        raise ValidationError("Image file size cannot exceed 10MB.")
    
    # Check file extension
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    file_extension = value.name.lower().split('.')[-1] if '.' in value.name else ''
    
    if f'.{file_extension}' not in allowed_extensions:
        raise ValidationError(
            f"Invalid file format. Allowed formats: {', '.join(allowed_extensions)}"
        )
    
    # Check MIME type
    allowed_mime_types = [
        'image/jpeg', 'image/png', 'image/gif', 
        'image/bmp', 'image/webp'
    ]
    
    if hasattr(value, 'content_type') and value.content_type not in allowed_mime_types:
        raise ValidationError("Invalid file type.")


def validate_telegram_user_id(value: int) -> None:
    """Validate Telegram user ID."""
    if not value:
        raise ValidationError("Telegram user ID is required.")
    
    # Telegram user IDs are positive integers
    if value <= 0:
        raise ValidationError("Invalid Telegram user ID.")
    
    # Reasonable range check (Telegram IDs are typically 9-10 digits)
    if value < 100000000 or value > 9999999999:
        raise ValidationError("Telegram user ID is out of expected range.")


def validate_admin_password(value: str) -> None:
    """Validate admin password strength."""
    if not value:
        raise ValidationError("Password is required.")
    
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    
    if len(value) > 128:
        raise ValidationError("Password cannot exceed 128 characters.")
    
    # Check for at least one letter and one number
    if not re.search(r'[A-Za-z]', value):
        raise ValidationError("Password must contain at least one letter.")
    
    if not re.search(r'\d', value):
        raise ValidationError("Password must contain at least one number.")


def validate_date_not_in_past(value: datetime) -> None:
    """Validate that date is not in the past."""
    if isinstance(value, datetime):
        value = value.date()
    
    today = timezone.now().date()
    
    if value < today:
        raise ValidationError("Date cannot be in the past.")


def validate_reasonable_future_date(value: datetime, max_days: int = 365) -> None:
    """Validate that date is not too far in the future."""
    if isinstance(value, datetime):
        value = value.date()
    
    today = timezone.now().date()
    max_date = today + timedelta(days=max_days)
    
    if value > max_date:
        raise ValidationError(f"Date cannot be more than {max_days} days in the future.")


class CombinedValidator:
    """Utility class for combining multiple validators."""
    
    def __init__(self, *validators):
        self.validators = validators
    
    def __call__(self, value):
        for validator in self.validators:
            validator(value)


# Common validator combinations
validate_full_name = CombinedValidator(validate_student_name)
validate_contact_phone = CombinedValidator(validate_indian_phone_number)
validate_student_roll = CombinedValidator(validate_roll_number)
validate_room_number_full = CombinedValidator(validate_room_number)