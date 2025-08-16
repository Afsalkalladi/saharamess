import hashlib
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

from .models import StaffToken


class StaffUser:
    """Simple user class for staff token authentication."""
    
    def __init__(self, staff_token):
        self.staff_token = staff_token
        self.is_authenticated = True
        self.is_staff = True
        self.id = f"staff_{staff_token.id}"
    
    @property
    def is_anonymous(self):
        return False


class StaffTokenAuthentication(BaseAuthentication):
    """
    Staff token authentication for QR scanner access.
    
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Bearer ".  For example:
    
        Authorization: Bearer 401f7ac837da42b97f613d789819ff93537bee6a
    """
    keyword = 'Bearer'
    model = StaffToken

    def authenticate(self, request):
        auth = self.get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = 'Invalid token header. No credentials provided.'
            raise AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            raise AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise AuthenticationFailed(msg)

        return self.authenticate_credentials(token)

    def authenticate_credentials(self, key):
        # Hash the provided token
        token_hash = hashlib.sha256(key.encode()).hexdigest()
        
        try:
            staff_token = self.model.objects.get(token_hash=token_hash, active=True)
        except self.model.DoesNotExist:
            raise AuthenticationFailed('Invalid token.')

        if not staff_token.is_valid:
            raise AuthenticationFailed('Token expired or inactive.')

        # Create a staff user object
        user = StaffUser(staff_token)
        
        # Store the staff token in the request for later use
        return (user, staff_token)

    def get_authorization_header(self, request):
        """
        Return request's 'Authorization:' header, as a bytestring.
        """
        auth = request.META.get('HTTP_AUTHORIZATION', b'')
        if isinstance(auth, str):
            auth = auth.encode('iso-8859-1')
        return auth


class TelegramBotAuthentication(BaseAuthentication):
    """
    Authentication for Telegram bot webhook.
    Validates webhook requests using bot token.
    """
    
    def authenticate(self, request):
        # For webhook endpoint, validate the request comes from Telegram
        if request.path == '/telegram/webhook':
            # In production, you should validate the webhook secret
            # For now, we'll use a simple header check
            bot_token = request.META.get('HTTP_X_TELEGRAM_BOT_TOKEN')
            if bot_token == settings.TELEGRAM_BOT_TOKEN:
                return (AnonymousUser(), None)
        
        return None


class AdminTokenAuthentication(BaseAuthentication):
    """
    Simple authentication for admin users based on Telegram ID.
    """
    
    def authenticate(self, request):
        # Check if the request has admin telegram ID
        admin_tg_id = request.META.get('HTTP_X_ADMIN_TG_ID')
        
        if admin_tg_id:
            try:
                admin_id = int(admin_tg_id)
                if admin_id in settings.ADMIN_TG_IDS:
                    # Create admin user
                    user = AdminUser(admin_id)
                    return (user, None)
            except (ValueError, TypeError):
                pass
        
        return None


class AdminUser:
    """Simple admin user class."""
    
    def __init__(self, telegram_id):
        self.telegram_id = telegram_id
        self.is_authenticated = True
        self.is_staff = True
        self.is_superuser = True
        self.id = f"admin_{telegram_id}"
    
    @property
    def is_anonymous(self):
        return False