# -*- coding: utf-8 -*-
# DAM - need to configure this
"""Production environment specific settings for FinSL-signbank."""
from __future__ import unicode_literals

from signbank.settings.base import *

# settings.base imports settings_secret
# The following settings are defined in settings_secret:
# SECRET_KEY, ADMINS, DATABASES, EMAIL_HOST, EMAIL_PORT, DEFAULT_FROM_EMAIL

# This setting defines the additional locations the staticfiles app will traverse if the FileSystemFinder finder
# is enabled, e.g. if you use the collectstatic or findstatic management command or use the static file serving view.
# STATICFILES_DIRS = (
#    os.path.join(PROJECT_DIR, "signbank", "static"),
# )

#: Use Local-memory caching for specific views (if you have bigger needs, use something else).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'nzsl-signbank-localmemcache',
    }
}

#: Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'media')
# URL that handles the media served from MEDIA_ROOT, used for managing stored files.
# It must end in a slash if set to a non-empty value.
MEDIA_URL = '/media/'

#: Location and URL for uploaded files.
UPLOAD_ROOT = MEDIA_ROOT + "upload/"
UPLOAD_URL = MEDIA_URL + "upload/"


#: A sample logging configuration. The only tangible logging
#: performed by this configuration is to send an email to
#: the site admins on every HTTP 500 error when DEBUG=False.
#: See http://docs.djangoproject.com/en/stable/topics/logging for
#: more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

#: Turn off lots of logging.
DO_LOGGING = True
# DAM LOG_FILENAME = "debug.log"
# note that the above has been superceded to stream to stderr


# REQUIRE SSL in production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
