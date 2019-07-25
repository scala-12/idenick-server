from corsheaders.defaults import default_headers
from django.conf.global_settings import CACHES

from .settings import *

DEBUG = True

INSTALLED_APPS += [
    'corsheaders.middleware.CorsMiddleware',
    'corsheaders',
]

MIDDLEWARE += [
    'corsheaders.middleware.CorsMiddleware',
]

MIDDLEWARE.remove('django.middleware.cache.UpdateCacheMiddleware')
MIDDLEWARE.remove('django.middleware.cache.FetchFromCacheMiddleware')
del CACHES

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_METHODS = (
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
)
CORS_ALLOW_HEADERS = default_headers + (
    'access-control-expose-headers',
)
CORS_EXPOSE_HEADERS = (
    'content-disposition',
)
