####
# Default settings for MOOC Grader project.
# You should create local_settings.py and override any settings there.
# You can copy local_settings.example.py and start from there.
##
from os import environ
from os.path import abspath, dirname, join
from typing import Any, Dict
BASE_DIR = dirname(dirname(abspath(__file__)))


# Base options, commonly overridden in local_settings.py
##########################################################################
DEBUG = False
SECRET_KEY = None
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)
#SERVER_EMAIL = 'root@'
ALLOWED_HOSTS = ["*"]
SSH_KEY_PATH=join(environ['HOME'], ".ssh/id_ecdsa")

# scheme and host for automatic updates
FRONTEND_URL = None # e.g. "https://<aplus_host>"
# default grader URL used for configuring
DEFAULT_GRADER_URL = None # e.g. "https://<grader_host>/configure"

# Local messaging library settings
APLUS_AUTH_LOCAL = {
    "PRIVATE_KEY": None,
    "PUBLIC_KEY": None,
    "REMOTE_AUTHENTICATOR_KEY": None,
    "REMOTE_AUTHENTICATOR_URL": None, # e.g. "https://<aplus_host>/api/v2/get-token/"
    #"DISABLE_JWT_SIGNING": False,
    #"DISABLE_LOGIN_CHECKS": False,
}

# course builder settings
DEFAULT_IMAGE="apluslms/compile-rst:1.6"
# default command passed to container. set to None to use the image default
DEFAULT_CMD="legacy_build"
BUILD_MODULE = join(BASE_DIR, "scripts/docker_build.py")
TMP_DIR = "/tmp/gitmanager"
# See the BUILD_MODULE script for details
BUILD_MODULE_SETTINGS = {
  "HOST_TMP_DIR": TMP_DIR,
}

# Build task scheduling redis options. These are ignored by huey if DEBUG=True
# and immediate mode is not turned off in HUEY settings.
redis_host = environ.get("REDIS_HOST", "localhost")
redis_port = environ.get("REDIS_PORT", 6379)
##########################################################################

APLUS_AUTH: Dict[str, Any] = {
    "AUTH_CLASS": "access.auth.Authentication",
}

INSTALLED_APPS = (
    # 'django.contrib.admin',
    # 'django.contrib.auth',
    # 'django.contrib.contenttypes',
    # 'django.contrib.sessions',
    # 'django.contrib.messages',
    'staticfileserver', # override for runserver command, thus this needs to be before django contrib one
    'django.contrib.staticfiles',
    'access',
    'gitmanager.apps.Config',
    'huey.contrib.djhuey',
    'aplus_auth',
)

MIDDLEWARE = [
    # 'django.middleware.security.SecurityMiddleware',
    # 'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'aplus_auth.auth.django.AuthenticationMiddleware'
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            join(BASE_DIR, 'local_templates'),
            join(BASE_DIR, 'templates'),
            join(BASE_DIR, 'courses'),
            join(BASE_DIR, 'exercises'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                #"django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                #'django.template.context_processors.request',
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                #"django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

#FILE_UPLOAD_HANDLERS = (
#    "django.core.files.uploadhandler.MemoryFileUploadHandler",
#    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
#)

ROOT_URLCONF = 'grader.urls'
# LOGIN_REDIRECT_URL = "/"
# LOGIN_ERROR_URL = "/login/"
WSGI_APPLICATION = 'grader.wsgi.application'

# Database (override in local_settings.py)
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases
##########################################################################
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': join(BASE_DIR, 'db.sqlite3'),
        # NOTE: Above setting can't be changed if girmanager is used.
        # cron.sh expects database to be in that file.
    }
}
##########################################################################

# Cache (override in local_settings.py)
# https://docs.djangoproject.com/en/1.10/topics/cache
##########################################################################
#CACHES = {
#    'default': {
#        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#        'TIMEOUT': None,
#    }
#}
#SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
##########################################################################

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True
LOCALE_PATHS = (
    join(BASE_DIR, 'locale'),
)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/
STATICFILES_DIRS = (
    join(BASE_DIR, 'assets'),
)
STATIC_URL = '/static/'
STATIC_ROOT = join(BASE_DIR, 'static')

#MEDIA_URL = '/media/'
#MEDIA_ROOT = join(BASE_DIR, 'media')


# HTTP
DEFAULT_EXPIRY_MINUTES = 15


# Course configuration path:
# Every directory under this directory is expected to be a course configuration
# FIXME: access/config.py contains hardcoded version of this value.
COURSES_PATH = join(BASE_DIR, 'courses')

# Exercise files submission path:
# Django process requires write access to this directory.
SUBMISSION_PATH = join(BASE_DIR, 'uploads')

# Logging
# https://docs.djangoproject.com/en/1.7/topics/logging/
##########################################################################
LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'formatters': {
    'verbose': {
      'format': '[%(asctime)s: %(levelname)s/%(module)s] %(message)s'
    },
  },
  'handlers': {
    'console': {
      'level': 'DEBUG',
      'class': 'logging.StreamHandler',
      'stream': 'ext://sys.stdout',
      'formatter': 'verbose',
    },
    'email': {
      'level': 'ERROR',
      'class': 'django.utils.log.AdminEmailHandler',
    },
  },
  'loggers': {
    '': {
      'level': 'DEBUG',
      'handlers': ['console']
    },
    'main': {
      'level': 'DEBUG',
      'handlers': ['email'],
      'propagate': True
    },
    'gitmanager.build': {
      'level': 'ERROR',
      'handlers': [],
      'propagate': False,
    },
  },
}

from redis import ConnectionPool
pool = ConnectionPool(host=redis_host, port=redis_port, max_connections=50, db=0)

HUEY = {
    'huey_class': 'huey.RedisHuey',
    'results': False,  # Whether to store return values of tasks
    # see redis.Connection in https://redis-py.readthedocs.io/en/stable/ for possible settings
    'connection': {
      'connection_pool': pool,
    },
    'consumer': {
        'workers': 1, # at the moment the build process blocks all other builds, so no need for more
        'worker_type': 'process',
        'initial_delay': 1,  # Smallest polling interval, same as -d.
        'backoff': 1.15,  # Exponential backoff using this rate, -b.
        'max_delay': 10.0,  # Max possible polling interval, -m.
        'scheduler_interval': 1,  # Check schedule every second, -s.
        'periodic': False,  # Disable crontab feature.
        'check_worker_health': True,  # Enable worker health checks.
        'health_check_interval': 1,  # Check worker health every second.
        'flush_locks': True, # this might cause problems if there are multiple workers and one restarts
    },
}



###############################################################################
from r_django_essentials.conf import *

# get settings values from other sources
update_settings_with_file(__name__,
                          environ.get('GRADER_LOCAL_SETTINGS', 'local_settings'),
                          quiet='GRADER_LOCAL_SETTINGS' in environ)
update_settings_from_module(__name__, 'settings_local', quiet=True) # Compatibility with older releases

# Load settings from environment variables starting with ENV_SETTINGS_PREFIX (default GRADER_)
ENV_SETTINGS_PREFIX = environ.get('ENV_SETTINGS_PREFIX', 'GRADER_')
update_settings_from_environment(__name__, ENV_SETTINGS_PREFIX)

update_secret_from_file(__name__, environ.get('GRADER_SECRET_KEY_FILE', 'secret_key'))

APLUS_AUTH.update(APLUS_AUTH_LOCAL)

# Drop x-frame policy when debugging
if DEBUG:
    MIDDLEWARE = [c for c in MIDDLEWARE if "XFrameOptionsMiddleware" not in c]

# update template loaders for production
use_cache_template_loader_in_production(__name__)
