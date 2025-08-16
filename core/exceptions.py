"""
Custom exceptions for the mess management system.
"""
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class MessManagementException(Exception):
    """Base exception for mess management system."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or 'GENERAL_ERROR'
        self.details = details or {}
        super().__init__(self.message)


class StudentRegistrationError(MessManagementException):
    """Exception raised for student registration errors."""
    
    def __init__(self, message: str, student_data: dict = None):
        super().__init__(message, 'STUDENT_REGISTRATION_ERROR', student_data)


class DuplicateRegistrationError(StudentRegistrationError):
    """Exception raised when student tries to register multiple times."""
    
    def __init__(self, message: str = "Student is already registered", existing_student: dict = None):
        super().__init__(message, existing_student)
        self.code = 'DUPLICATE_REGISTRATION'


class InvalidStudentStatusError(MessManagementException):
    """Exception raised when student status is invalid for operation."""
    
    def __init__(self, message: str, current_status: str = None, required_status: str = None):
        details = {
            'current_status': current_status,
            'required_status': required_status
        }
        super().__init__(message, 'INVALID_STUDENT_STATUS', details)


class PaymentError(MessManagementException):
    """Base exception for payment-related errors."""
    
    def __init__(self, message: str, payment_data: dict = None):
        super().__init__(message, 'PAYMENT_ERROR', payment_data)


class DuplicatePaymentError(PaymentError):
    """Exception raised when payment already exists for cycle."""
    
    def __init__(self, message: str = "Payment already exists for this cycle", existing_payment: dict = None):
        super().__init__(message, existing_payment)
        self.code = 'DUPLICATE_PAYMENT'


class InvalidPaymentStatusError(PaymentError):
    """Exception raised when payment status is invalid for operation."""
    
    def __init__(self, message: str, current_status: str = None, required_status: str = None):
        details = {
            'current_status': current_status,
            'required_status': required_status
        }
        super().__init__(message, details)
        self.code = 'INVALID_PAYMENT_STATUS'


class PaymentExpiredError(PaymentError):
    """Exception raised when payment has expired."""
    
    def __init__(self, message: str = "Payment has expired", expiry_date: str = None):
        details = {'expiry_date': expiry_date}
        super().__init__(message, details)
        self.code = 'PAYMENT_EXPIRED'


class MessCutError(MessManagementException):
    """Base exception for mess cut errors."""
    
    def __init__(self, message: str, mess_cut_data: dict = None):
        super().__init__(message, 'MESS_CUT_ERROR', mess_cut_data)


class CutoffViolationError(MessCutError):
    """Exception raised when mess cut violates cutoff rules."""
    
    def __init__(self, message: str = "Mess cut violates cutoff time rules", cutoff_time: str = None, attempted_date: str = None):
        details = {
            'cutoff_time': cutoff_time,
            'attempted_date': attempted_date
        }
        super().__init__(message, details)
        self.code = 'CUTOFF_VIOLATION'


class OverlappingMessCutError(MessCutError):
    """Exception raised when mess cut overlaps with existing cut."""
    
    def __init__(self, message: str = "Mess cut overlaps with existing cut", existing_cuts: list = None):
        details = {'existing_cuts': existing_cuts or []}
        super().__init__(message, details)
        self.code = 'OVERLAPPING_MESS_CUT'


class QRCodeError(MessManagementException):
    """Base exception for QR code errors."""
    
    def __init__(self, message: str, qr_data: dict = None):
        super().__init__(message, 'QR_CODE_ERROR', qr_data)


class InvalidQRCodeError(QRCodeError):
    """Exception raised when QR code is invalid."""
    
    def __init__(self, message: str = "Invalid QR code", qr_payload: str = None):
        details = {'qr_payload': qr_payload}
        super().__init__(message, details)
        self.code = 'INVALID_QR_CODE'


class ExpiredQRCodeError(QRCodeError):
    """Exception raised when QR code has expired."""
    
    def __init__(self, message: str = "QR code has expired", version: int = None):
        details = {'version': version}
        super().__init__(message, details)
        self.code = 'EXPIRED_QR_CODE'


class QRVerificationError(QRCodeError):
    """Exception raised when QR code verification fails."""
    
    def __init__(self, message: str = "QR code verification failed", verification_details: dict = None):
        super().__init__(message, verification_details)
        self.code = 'QR_VERIFICATION_ERROR'


class AccessDeniedError(MessManagementException):
    """Exception raised when access is denied."""
    
    def __init__(self, message: str, reason: str = None, access_details: dict = None):
        details = access_details or {}
        details['reason'] = reason
        super().__init__(message, 'ACCESS_DENIED', details)


class MealAccessDeniedError(AccessDeniedError):
    """Exception raised when meal access is denied."""
    
    def __init__(self, message: str, reason: str = None, student_id: str = None, meal: str = None):
        details = {
            'student_id': student_id,
            'meal': meal,
            'reason': reason
        }
        super().__init__(message, reason, details)
        self.code = 'MEAL_ACCESS_DENIED'


class StaffTokenError(MessManagementException):
    """Base exception for staff token errors."""
    
    def __init__(self, message: str, token_data: dict = None):
        super().__init__(message, 'STAFF_TOKEN_ERROR', token_data)


class InvalidStaffTokenError(StaffTokenError):
    """Exception raised when staff token is invalid."""
    
    def __init__(self, message: str = "Invalid staff token", token_hash: str = None):
        details = {'token_hash': token_hash}
        super().__init__(message, details)
        self.code = 'INVALID_STAFF_TOKEN'


class ExpiredStaffTokenError(StaffTokenError):
    """Exception raised when staff token has expired."""
    
    def __init__(self, message: str = "Staff token has expired", expiry_date: str = None):
        details = {'expiry_date': expiry_date}
        super().__init__(message, details)
        self.code = 'EXPIRED_STAFF_TOKEN'


class IntegrationError(MessManagementException):
    """Base exception for external integration errors."""
    
    def __init__(self, message: str, service: str = None, error_details: dict = None):
        details = error_details or {}
        details['service'] = service
        super().__init__(message, 'INTEGRATION_ERROR', details)


class CloudinaryError(IntegrationError):
    """Exception raised for Cloudinary integration errors."""
    
    def __init__(self, message: str, operation: str = None, error_details: dict = None):
        details = error_details or {}
        details['operation'] = operation
        super().__init__(message, 'cloudinary', details)
        self.code = 'CLOUDINARY_ERROR'


class GoogleSheetsError(IntegrationError):
    """Exception raised for Google Sheets integration errors."""
    
    def __init__(self, message: str, operation: str = None, sheet_name: str = None, error_details: dict = None):
        details = error_details or {}
        details.update({
            'operation': operation,
            'sheet_name': sheet_name
        })
        super().__init__(message, 'google_sheets', details)
        self.code = 'GOOGLE_SHEETS_ERROR'


class TelegramError(IntegrationError):
    """Exception raised for Telegram integration errors."""
    
    def __init__(self, message: str, chat_id: int = None, error_details: dict = None):
        details = error_details or {}
        details['chat_id'] = chat_id
        super().__init__(message, 'telegram', details)
        self.code = 'TELEGRAM_ERROR'


class ValidationError(MessManagementException):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: str = None, value: str = None):
        details = {
            'field': field,
            'value': value
        }
        super().__init__(message, 'VALIDATION_ERROR', details)


class BusinessRuleViolationError(MessManagementException):
    """Exception raised when business rules are violated."""
    
    def __init__(self, message: str, rule: str = None, violation_details: dict = None):
        details = violation_details or {}
        details['rule'] = rule
        super().__init__(message, 'BUSINESS_RULE_VIOLATION', details)


class ConcurrencyError(MessManagementException):
    """Exception raised for concurrency-related errors."""
    
    def __init__(self, message: str = "Concurrent modification detected", resource: str = None):
        details = {'resource': resource}
        super().__init__(message, 'CONCURRENCY_ERROR', details)


class DataIntegrityError(MessManagementException):
    """Exception raised for data integrity violations."""
    
    def __init__(self, message: str, constraint: str = None, details: dict = None):
        error_details = details or {}
        error_details['constraint'] = constraint
        super().__init__(message, 'DATA_INTEGRITY_ERROR', error_details)


class ConfigurationError(MessManagementException):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, setting: str = None, expected_value: str = None):
        details = {
            'setting': setting,
            'expected_value': expected_value
        }
        super().__init__(message, 'CONFIGURATION_ERROR', details)


class ExternalServiceError(MessManagementException):
    """Exception raised when external services are unavailable."""
    
    def __init__(self, message: str, service: str = None, status_code: int = None):
        details = {
            'service': service,
            'status_code': status_code
        }
        super().__init__(message, 'EXTERNAL_SERVICE_ERROR', details)


# Custom exception handler for DRF
def custom_exception_handler(exc, context):
    """Custom exception handler for Django REST Framework."""
    
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Handle our custom exceptions
    if isinstance(exc, MessManagementException):
        custom_response_data = {
            'error': {
                'code': exc.code,
                'message': exc.message,
                'details': exc.details
            },
            'success': False,
            'timestamp': str(timezone.now().isoformat())
        }
        
        # Determine HTTP status code based on exception type
        if isinstance(exc, (InvalidStudentStatusError, InvalidPaymentStatusError, 
                          CutoffViolationError, ValidationError)):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, (AccessDeniedError, MealAccessDeniedError, 
                            InvalidStaffTokenError, ExpiredStaffTokenError)):
            status_code = status.HTTP_403_FORBIDDEN
        elif isinstance(exc, (DuplicateRegistrationError, DuplicatePaymentError)):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, (IntegrationError, ExternalServiceError)):
            status_code = status.HTTP_502_BAD_GATEWAY
        elif isinstance(exc, ConfigurationError):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        
        response = Response(custom_response_data, status=status_code)
        
        # Log the exception
        logger.error(
            f"Custom exception: {exc.__class__.__name__}: {exc.message}",
            extra={
                'exception_code': exc.code,
                'exception_details': exc.details,
                'request_path': context.get('request', {}).get('path', 'unknown')
            }
        )
    
    # Add custom fields to standard DRF error responses
    elif response is not None:
        custom_response_data = {
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Validation failed',
                'details': response.data
            },
            'success': False,
            'timestamp': str(timezone.now().isoformat())
        }
        response.data = custom_response_data
    
    return response


# Utility functions for raising common exceptions
def raise_invalid_student_status(current_status: str, required_status: str, operation: str = None):
    """Utility function to raise InvalidStudentStatusError."""
    message = f"Student status is '{current_status}' but '{required_status}' is required"
    if operation:
        message += f" for {operation}"
    raise InvalidStudentStatusError(message, current_status, required_status)


def raise_payment_expired(payment, current_date=None):
    """Utility function to raise PaymentExpiredError."""
    from django.utils import timezone
    current_date = current_date or timezone.now().date()
    
    message = f"Payment expired on {payment.cycle_end}, current date is {current_date}"
    raise PaymentExpiredError(message, str(payment.cycle_end))


def raise_access_denied(reason: str, student_id: str = None, meal: str = None):
    """Utility function to raise MealAccessDeniedError."""
    message = f"Meal access denied: {reason}"
    raise MealAccessDeniedError(message, reason, student_id, meal)


def raise_cutoff_violation(attempted_date, cutoff_time: str = None):
    """Utility function to raise CutoffViolationError."""
    message = f"Cannot apply mess cut for {attempted_date} due to cutoff time rules"
    raise CutoffViolationError(message, cutoff_time, str(attempted_date))


def raise_invalid_qr_code(qr_payload: str = None, reason: str = None):
    """Utility function to raise InvalidQRCodeError."""
    message = "Invalid QR code"
    if reason:
        message += f": {reason}"
    raise InvalidQRCodeError(message, qr_payload)


# Context managers for exception handling
class suppress_integration_errors:
    """Context manager to suppress integration errors and log them."""
    
    def __init__(self, service_name: str, operation: str = None):
        self.service_name = service_name
        self.operation = operation
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, IntegrationError):
            logger.warning(
                f"Integration error suppressed for {self.service_name}: {exc_val}",
                extra={
                    'service': self.service_name,
                    'operation': self.operation,
                    'error': str(exc_val)
                }
            )
            return True  # Suppress the exception
        return False