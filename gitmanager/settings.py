####
# Default settings for Git Manager project.
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
# The scheme and hostname of where the static files can be accessed. Passed to build containers
STATIC_CONTENT_HOST = None
SSH_KEY_PATH=join(environ['HOME'], ".ssh/id_ecdsa")

# scheme and host for automatic updates
FRONTEND_URL = None # e.g. "https://<aplus_host>"
# default grader URL used for configuring
DEFAULT_GRADER_URL = None # e.g. "https://<grader_host>/configure"

# Authentication and authorization library settings
# see https://pypi.org/project/aplus-auth/ for explanations
APLUS_AUTH_LOCAL = {
    #"UID": "...", # set to "gitmanager" below, can be changed
    "PRIVATE_KEY": None,
    "PUBLIC_KEY": None,
    "REMOTE_AUTHENTICATOR_UID": None, # The UID of the remote authenticator, e.g. "aplus"
    "REMOTE_AUTHENTICATOR_KEY": None, # The public key of the remote authenticator
    "REMOTE_AUTHENTICATOR_URL": None, # probably "https://<A+ domain>/api/v2/get-token/"
    #"UID_TO_KEY": {...}
    #"TRUSTED_UIDS": [...],
    #"TRUSTING_REMOTES": [...],
    #"DISABLE_JWT_SIGNING": False,
    #"DISABLE_LOGIN_CHECKS": False,
}

# course builder settings
DEFAULT_IMAGE="apluslms/compile-rst:1.6"
# default command passed to container. set to None to use the image default
DEFAULT_CMD="legacy_build"
BUILD_MODULE = join(BASE_DIR, "scripts/docker_build.py")

# Course configuration path:
# Every directory under this directory is expected to be a course configuration
COURSES_PATH = join(BASE_DIR, 'courses')
BUILD_PATH = "/tmp/gitmanager"
# this MUST be on the same device as COURSES_PATH
STORE_PATH = join(BASE_DIR, "course_store")
# See the BUILD_MODULE script for details
BUILD_MODULE_SETTINGS = {
  "HOST_BUILD_PATH": BUILD_PATH,
  "CONTAINER_BUILD_PATH": BUILD_PATH,
  "HOST_PUBLISH_PATH": COURSES_PATH,
  "CONTAINER_PUBLISH_PATH": COURSES_PATH,
}
# local course source directory for testing the build without cloning anything from git
LOCAL_COURSE_SOURCE_PATH = None

# Whether to use the X-SendFile
USE_X_SENDFILE = False

# Build task scheduling redis options. These are ignored by huey if DEBUG=True
# and immediate mode is not turned off in HUEY settings.
redis_host = environ.get("REDIS_HOST", "localhost")
redis_port = environ.get("REDIS_PORT", 6379)
##########################################################################

BUILD_RETRY_DELAY = 30

APLUS_AUTH: Dict[str, Any] = {
    "UID": "gitmanager",
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
    'builder',
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
                "django.template.context_processors.request",
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

# default model primary key field
DEFAULT_AUTO_FIELD='django.db.models.AutoField'

ROOT_URLCONF = 'gitmanager.urls'
# LOGIN_REDIRECT_URL = "/"
# LOGIN_ERROR_URL = "/login/"
WSGI_APPLICATION = 'gitmanager.wsgi.application'

# Database (override in local_settings.py)
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases
##########################################################################
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': join(BASE_DIR, 'db.sqlite3'),
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


# How long (in seconds) to wait for a lock to the course store directory when trying to
# store built course. Makes sure that the build process doesn't get stuck on
# some strange issue
BUILD_FILELOCK_TIMEOUT = 30

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
    'builder.build': {
      'level': 'DEBUG',
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
        'workers': 5, # maximum number of concurrent builds
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
huey_immediate = environ.get('HUEY_IMMEDIATE', None)
if huey_immediate is not None:
    HUEY.update({
        'immediate': huey_immediate in ('true', 'True', 'yes', 'on'),
    })


###############################################################################
from r_django_essentials.conf import *

# get settings values from other sources
update_settings_with_file(__name__,
                          environ.get('GITMANAGER_LOCAL_SETTINGS', 'local_settings'),
                          quiet='GITMANAGER_LOCAL_SETTINGS' in environ)

# Load settings from environment variables starting with ENV_SETTINGS_PREFIX (default GITMANAGER_)
ENV_SETTINGS_PREFIX = environ.get('ENV_SETTINGS_PREFIX', 'GITMANAGER_')
update_settings_from_environment(__name__, ENV_SETTINGS_PREFIX)

update_secret_from_file(__name__, environ.get('GITMANAGER_SECRET_KEY_FILE', 'secret_key'))

APLUS_AUTH.update(APLUS_AUTH_LOCAL)

from pathlib import Path
Path(BUILD_PATH).mkdir(parents=True, exist_ok=True)
Path(STORE_PATH).mkdir(parents=True, exist_ok=True)
Path(COURSES_PATH).mkdir(parents=True, exist_ok=True)

# Drop x-frame policy when debugging
if DEBUG:
    MIDDLEWARE = [c for c in MIDDLEWARE if "XFrameOptionsMiddleware" not in c]

# update template loaders for production
use_cache_template_loader_in_production(__name__)
