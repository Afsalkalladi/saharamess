from .base import *
import os
import dj_database_url
from decouple import config

# Production settings
DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

# Security settings
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3'),
        conn_max_age=600,
    )
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Production environment variables
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
ADMIN_TG_IDS = [int(x.strip()) for x in config('ADMIN_TG_IDS', default='').split(',') if x.strip()]
QR_SECRET = config('QR_SECRET', default='change-this-secret-key')
STAFF_SCANNER_PASSWORD = config('STAFF_SCANNER_PASSWORD', default='admin123')

# Cloudinary settings
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='')
CLOUDINARY_API_KEY = config('CLOUDINARY_API_KEY', default='')
CLOUDINARY_API_SECRET = config('CLOUDINARY_API_SECRET', default='')

# Google Sheets settings
SHEETS_CREDENTIALS_JSON = config('SHEETS_CREDENTIALS_JSON', default='{}')
SHEETS_SPREADSHEET_ID = config('SHEETS_SPREADSHEET_ID', default='')

# Redis/Celery settings
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Email settings (if needed)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')