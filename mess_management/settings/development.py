from .base import *
import os

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS += [
    'django_extensions',
]

# Development database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Override settings for testing without external services
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'test-token')
ADMIN_TG_IDS = [123456789, 987654321]  # Test admin IDs
QR_SECRET = os.getenv('QR_SECRET', 'test-qr-secret')
STAFF_SCANNER_PASSWORD = os.getenv('STAFF_SCANNER_PASSWORD', 'test-password')

# Disable external services for testing
CLOUDINARY_CLOUD_NAME = 'test'
CLOUDINARY_API_KEY = 'test'
CLOUDINARY_API_SECRET = 'test'

# Mock Google Sheets credentials
SHEETS_CREDENTIALS_JSON = {
    "type": "service_account",
    "project_id": "test",
    "private_key_id": "test",
    "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
    "client_email": "test@test.iam.gserviceaccount.com",
    "client_id": "test",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40test.iam.gserviceaccount.com"
}
SHEETS_SPREADSHEET_ID = 'test-spreadsheet-id'

# Disable Celery for testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
