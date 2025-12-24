
from pathlib import Path
import os


from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-l6c$=vdsv7n-ng7cd_^6fvi7lig^+_a2!dzg5oy1^a6qklw$9t'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
ALLOWED_HOSTS = ['*']


# Add this for Render
CORS_ALLOW_ALL_ORIGINS = True
# 5. DRF Config

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',
    
    'core',
  
    'storages',
    'rest_framework',
    'rest_framework.authtoken',
    

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this for static files
    'corsheaders.middleware.CorsMiddleware',  # Move CORS up
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'allocate.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# settings.py

# ===== GEMINI API KEYS (Add 5 keys) =====
# Get free keys from: https://aistudio.google.com/apikey
# ==============================================
# AWS S3 SETTINGS (PRESIGNED URL MODE)
# ==============================================

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-1')


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

# AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

#     # Media files
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# # https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',  # use this for normal Postgres
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
# DATABASES = {
#      'default': {
#          'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
#         'NAME': config('DB_NAME'),
#          'USER': config('DB_USER'),
#          'PASSWORD': config('DB_PASSWORD'),
#          'HOST': config('DB_HOST'),
#          'PORT': config('DB_PORT', default='5432'),
#          'OPTIONS': {
#              'connect_timeout': 10,
#          }
#      }
# }
# DATABASES = {
#     'default': dj_database_url.config(
#         default='postgresql://postgress:nxJpZNoU4tirJexUiaPFTLvSPjiWwqyT@dpg-d3u7mhbe5dus739f6mjg-a.oregon-postgres.render.com/registerdb_od8n',
#         # default='postgresql://postgress:nxJpZNoU4tirJexUiaPFTLvSPjiWwqyT@dpg-d3u7mhbe5dus739f6mjg-a/registerdb_od8n',
#         conn_max_age=600,
#         conn_health_checks=True,
#     )
# }
# At the end of settings.py
APPEND_SLASH = False  # Prevent automatic slash redirects


# In settings.py - MUCH SIMPLER!
MUKADAM_WEBHOOK_URLS = {
    'default': 'http://localhost:5000/api/webhooks/job-notification'
}

BASE_URL = 'https://workcrop.onrender.com'
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://workcrop.onrender.com,http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:8000,https://workcrop-dc8o.vercel.app,http://localhost:5173,http://65.0.238.67',
    cast=Csv()
)




CORS_ALLOW_CREDENTIALS = True
# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = []
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "https://workcrop-dc8o.vercel.app/",
    "https://workcrop.onrender.com",
    "https://workw-mu.vercel.app/",
    "https://workw-mu.vercel.app",
    "http://localhost:5000",
]

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


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']