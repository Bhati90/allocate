"""
Django settings for allocate project.
"""

from pathlib import Path
import os
# settings.py
# ============================================
# CORS & CSRF CONFIGURATION
# ============================================
import os
import dj_database_url

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-l6c$=vdsv7n-ng7cd_^6fvi7lig^+_a2!dzg5oy1^a6qklw'

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True
DEBUG = "False"
# settings.py
GOOGLE_SHEET_WEBHOOK_URL    = "https://script.google.com/macros/s/AKfycby5zxwRN0vvJjHs6ikjfY_nGLOu1hTTdjZAWi49aYwcsazITVT3ya1unf30X7BK1FPJ/exec"
GOOGLE_SHEET_WEBHOOK_SECRET = "django-insecure-l6c$=vdsv7n-ng7cd_^6fvi7lig^+_a2!dzg5oy1^a6qklw"
ALLOWED_HOSTS = ['*']
# settings.py
FARMER_BILLING_SHEET_ID = "1FgsuOFTqmzWAZ04L1-5KwRiSByj2crp1zbReVGRFQpc"  # from the URL
GOOGLE_CREDENTIALS_PATH = BASE_DIR / "google.json"
# ============================================
# CORS & CSRF CONFIGURATION
# ============================================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://allocate-1.onrender.com",
    "https://tender.bharatintelligence.ai",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://furtive-chrissy-reparably.ngrok-free.dev",
    "http://127.0.0.1:3000",
    "http://localhost:5174",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "https://supply.bharatintelligence.ai",
    "https://demand.bharatintelligence.ai",
    "https://payment.bharatintelligence.ai",
    "https://ops.bharatintelligence.ai",
    "https://allocation.bharatintelligence.ai",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    # ── Sheet sync headers ──────────────────────────────────────────────────
    'x-sheet-secret',            # secret auth used by MukkadamSheet.gs
    'ngrok-skip-browser-warning', # needed when tunnelling via ngrok locally
]

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    "https://allocate-1.onrender.com",
    "https://tender.bharatintelligence.ai",
    "https://supply.bharatintelligence.ai",
    "https://demand.bharatintelligence.ai",
    "https://payment.bharatintelligence.ai",
    "https://ops.bharatintelligence.ai",
    "https://allocation.bharatintelligence.ai",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://localhost:5174",
    "http://127.0.0.1:8001",
]

CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False

# Application definition
INSTALLED_APPS = [
    "corsheaders",
    'tender.apps.TenderConfig',  
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',


    'storages',
    'rest_framework',
    'rest_framework.authtoken',
]

BASE_DIR = Path(__file__).resolve().parent.parent
# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
   
}

# Presign API Configuration
PRESIGN_API_URL = 'https://demand.bharatintelligence.ai/chat/presign_obj_api/'
PRESIGN_API_TOKEN = 'Token c432208626a204d2d8de3d00b29f948eae61ebdb'  # ✅ Replace with real token


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # ✅ MUST BE FIRST
    'django.middleware.security.SecurityMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'allocate.urls'

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [f"{BASE_DIR}/allocate/static"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'allocate.wsgi.application'

# ===== GEMINI API KEYS (Add 5 keys) =====
# Get free keys from: https://aistudio.google.com/apikey

GEMINI_API_KEY_1 = os.environ.get('GEMINI_API_KEY_1', 'AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs')
GEMINI_API_KEY_2 = os.environ.get('GEMINI_API_KEY_2', 'AIzaSyDGCAaYBIoySFkgom_KHm6wtk2m12wVLBw')
# Backward compatibility
GEMINI_API_KEY = GEMINI_API_KEY_1

# ==============================================
# AWS S3 SETTINGS (PRESIGNED URL MODE)
# ==============================================

# AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
# AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
# AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-1')


# --- 2. ENABLE SIGNING ---
AWS_QUERYSTRING_AUTH = True  # <--- This generates the '?Signature=...'
AWS_QUERYSTRING_EXPIRE = 3600  # Link expires in 1 hour (adjust as needed)
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_URL_PROTOCOL = 'https:'

# --- 3. SECURITY ---
AWS_DEFAULT_ACL = None  # Use Bucket Owner Enforced (Private)
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# --- 4. STORAGE ENGINE ---
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

#     # Media files
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# # https://docs.djangoproject.com/en/5.2/ref/settings/#databases


# # allocate/settings.py
SUPPLY_API_URL = 'http://localhost:8000'
ALLOCATION_API_URL = 'http://localhost:8001'

# allocate/settings.py
# SUPPLY_API_URL = 'https://supply.bharatintelligence.ai'
# ALLOCATION_API_URL = 'https://allocation.bharatintelligence.ai'
# Tell Celery to use Redis, not RabbitMQ
# CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
# CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'


# # Redis Cache Configuration
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',  # Use your Redis server
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         },
#         'KEY_PREFIX': 'allocation_app',
#         'TIMEOUT': 3600,  # 1 hour default
#     }
# }



# Cache timeouts (in seconds)
CACHE_MUKKADAM_TIMEOUT = 3600  # 1 hour
CACHE_FARMER_TIMEOUT = 3600    # 1 hour
CACHE_TRANSPORT_TIMEOUT = 21600  # 6 hours
CACHE_JOB_TIMEOUT = 1800  # 30 minutes
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'registration_db',
        'USER': 'postgres',
        'PASSWORD': 'new_password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'client_encoding': 'UTF8',
        },
    }
}
SALES_WEBHOOK_URL        = "https://a801-157-20-14-50.ngrok-free.app/ops/activity-status-webhook/"
SALES_CANCEL_WEBHOOK_URL = "https://a801-157-20-14-50.ngrok-free.app/ops/activity-status-webhook/"  # 👈
SHEETS_WEBHOOK_SECRET = "django-insecure-l6c$=vdsv7n-ng7cd_^6fvi7lig^+_a2!dzg5oy1^a6qklw$9t"
SALES_WEBHOOK_TOKEN      = "89b9fd0698faed6c12c1a8e714fca12c86ee2000"
# DATABASES = {
#     'default': dj_database_url.config(
#         default=os.environ.get("DATABASE_URL")
#     )
# }
# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# AWS S3
# AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
# AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
# AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-1')
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_URL_PROTOCOL = 'https:'
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Celery
# CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
# CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
GOOGLE_SHEETS_CREDENTIALS = BASE_DIR / "google.json"
GOOGLE_SHEET_ID = "1dT9aM83YvhsaHj60_YMMuktYM5aKS7l5VPfFD-1Tp3g"  # from the sheet URL
# Cache
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
#         'KEY_PREFIX': 'allocation_app',
#         'TIMEOUT': 3600,
#     }
# }
SHEET_API_TOKEN = "hfwhfewufg6423784632^%^&%^&%HGFGFGHFTYFTYF$%^&$%$"
CACHE_MUKKADAM_TIMEOUT = 3600
CACHE_FARMER_TIMEOUT = 3600
CACHE_TRANSPORT_TIMEOUT = 21600
CACHE_JOB_TIMEOUT = 1800

# Other settings
GEMINI_API_KEY_1 = os.environ.get('GEMINI_API_KEY_1', 'AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs')
GEMINI_API_KEY_2 = os.environ.get('GEMINI_API_KEY_2', 'AIzaSyDGCAaYBIoySFkgom_KHm6wtk2m12wVLBw')
GEMINI_API_KEY = GEMINI_API_KEY_1

PRESIGN_API_URL = 'https://demand.bharatintelligence.ai/chat/presign_obj_api/'
PRESIGN_API_TOKEN = 'Token c432208626a204d2d8de3d00b29f948eae61ebdb'

EXOTEL_TOKEN_URL = "https://call.bharatintelligence.ai/oauth/token"
EXOTEL_CLIENT_ID = "kishan_localhost"
EXOTEL_CLIENT_SECRET = "bi_M-n87nBu4a1QAs6ve7-o4FMrvm9hOMZ5npqVB-lhS-Q"
EXOTEL_SERVICE_BASE_URL = "https://call.bharatintelligence.ai"
EXOTEL_CALLER_ID = "+91-804-7361465"

MUKADAM_WEBHOOK_URLS = {'default': 'http://localhost:5000/api/webhooks/job-notification'}
BASE_URL = 'https://workcrop.onrender.com'
APPEND_SLASH = False



# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
CORS_ALLOW_ALL_ORIGINS = True   # permissive for local/ngrok dev; restrict to CORS_ALLOWED_ORIGINS in prod
# NOTE: even with ALLOW_ALL_ORIGINS, CORS_ALLOW_HEADERS above is still enforced — keep x-sheet-secret in it

CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']