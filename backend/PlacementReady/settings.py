"""
Django settings for PlacementReady project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# 2. We don't even need to force load_dotenv anymore because Docker handles it natively!
load_dotenv()

# ==========================================
# DYNAMIC ENVIRONMENT CONFIGURATION
# ==========================================

# Pulls the secret key, crashes if it doesn't exist
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'fallback-dev-key-do-not-use-in-prod')

# FIXED: Now it dynamically reads the string from .env and converts to a boolean
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# FIXED: Now it dynamically splits your .env string into a Python list
allowed_hosts_str = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = allowed_hosts_str.split(',')

print(os.environ.get('DATABASE_URL'))
# ==========================================
# APPLICATION DEFINITION
# ==========================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # FIXED: Added the missing 3rd Party Apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Local Apps
    'users',
    'companies',
    'base',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PlacementReady.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'PlacementReady.wsgi.application'

AUTH_USER_MODEL = 'users.User'

# ==========================================
# DATABASE
# ==========================================
db_url = os.environ.get('DATABASE_URL')

if not db_url:
    raise ValueError("CRITICAL ERROR: DATABASE_URL is missing! Docker is not passing the .env file.")

DATABASES = {
    'default': dj_database_url.parse(
        db_url,
        conn_max_age=600,   # Persistent connection
        ssl_require=True    # Supabase requires SSL
    )
}

# ==========================================
# REST FRAMEWORK & CORS
# ==========================================

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'EXCEPTION_HANDLER': 'base.exceptions.custom_exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'PlacementReady API',
    'DESCRIPTION': 'API endpoints for the Placement Planner, RAG Bot, and Bookmarks.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Allows React to talk to your API. 
# Pro-tip trick: If DEBUG is True (Local), allow everything. If False (AWS), restrict it.
CORS_ALLOW_ALL_ORIGINS = DEBUG 



# ==========================================
# STANDARD DJANGO SETTINGS
# ==========================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'


# Create a logs directory in your backend folder if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} | Module: {module} | Process: {process:d} | Thread: {thread:d} | {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{asctime}] {levelname} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'WARNING', # Only log Warnings and Critical errors to the file to save disk space
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'placement_ready.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB per file
            'backupCount': 5,             # Keep the last 5 files
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Django's internal system logs
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': True,
        },
        # Your custom app logs
        'base': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'companies': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}