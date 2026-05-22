"""
Django settings for PlacementReady project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# 1. FIXED PATHING: Added an extra .parent so it points to the outer 'backend' folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Load the invisible environment file
env_path = BASE_DIR / '.env'
load_dotenv(env_path)

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

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
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