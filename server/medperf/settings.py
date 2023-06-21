"""
Django settings for medperf project.

Generated by 'django-admin startproject' using Django 3.2.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from pathlib import Path
import os
import io
import environ
import google.auth
from google.cloud import secretmanager

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/
env = environ.Env()
env_file = os.path.join(BASE_DIR, ".env")

if os.path.isfile(env_file):
    # Use a local secret file, if provided
    print("Loading env from .env file")
    env.read_env(env_file)
else:
    # Attempt to load the Project ID into the environment, safely failing on error.
    try:
        _, os.environ["GOOGLE_CLOUD_PROJECT"] = google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        raise Exception(
            "No local .env or GOOGLE_CLOUD_PROJECT detected. No secrets found."
        )

    # Pull secrets from Secret Manager
    print("Loading env from GCP secrets manager")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    client = secretmanager.SecretManagerServiceClient()
    settings_name = os.environ.get("SETTINGS_SECRETS_NAME", None)
    if settings_name is None:
        raise Exception("SETTINGS_SECRETS_NAME var is not set")
    settings_version = os.environ.get("SETTINGS_SECRETS_VERSION", "latest")
    name = f"projects/{project_id}/secrets/{settings_name}/versions/{settings_version}"
    payload = client.access_secret_version(name=name).payload.data.decode("UTF-8")

    env.read_env(io.StringIO(payload))


SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG", default=False)

SUPERUSER_USERNAME = env("SUPERUSER_USERNAME")

SUPERUSER_PASSWORD = env("SUPERUSER_PASSWORD")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# TODO Change later to list of allowed domains
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

GS_BUCKET_NAME = env("GS_BUCKET_NAME", default=None)

DEPLOY_ENV = env("DEPLOY_ENV")

# Possible deployment enviroments
if DEPLOY_ENV not in ["local", "local-tutorials", "gcp-ci", "gcp-prod"]:
    raise Exception("Invalid deployment enviroment")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "benchmark",
    "dataset",
    "benchmarkdataset",
    "mlcube",
    "benchmarkmodel",
    "user",
    "result",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "medperf.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "libraries": {
                "staticfiles": "django.templatetags.static",
            },
        },
    },
]

WSGI_APPLICATION = "medperf.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
DATABASES = {"default": env.db()}

# Deploy using python manage.py runserver_plus or via docker.
# Refer .github/workflows/local-ci.yml, .github/workflows/docker-ci.yml
if DEPLOY_ENV in ["local", "local-tutorials"]:
    print("Local Build environment")
    # Always run SSL server during local deployment
    INSTALLED_APPS += ["django_extensions"]
    # Serve static files using whitenoise middleware if google cloud storage is not used
    MIDDLEWARE += ["whitenoise.middleware.WhiteNoiseMiddleware"]
    # SECURE_SSL_REDIRECT to true for SSL redirect
    SECURE_SSL_REDIRECT = True
# Deploy using cloudbuild in GCP CI enviroment. Refer cloudbuild-ci.yaml
elif DEPLOY_ENV == "gcp-ci":
    print("GCP CI Build environment")
    # GCP_CI_DATABASE_URL is populated in cloudbuild trigger script
    DATABASES = {"default": env.db_url("GCP_CI_DATABASE_URL")}
# Deploy using cloudbuild in GCP Prod enviroment. Refer cloudbuild-prod.yaml
else:
    print("GCP Prod Build environment")
    # Always set DEBUG as False in production environments
    DEBUG = False

# If the flag as been set, configure to use proxy
if os.getenv("USE_CLOUD_SQL_AUTH_PROXY", None):
    DATABASES["default"]["HOST"] = "127.0.0.1"
    DATABASES["default"]["PORT"] = 5432


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    #    },
    #    },
    #    },
    #    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "static")

GS_DEFAULT_ACL = "publicRead"

if GS_BUCKET_NAME:
    # Serve static files from GCS bucket
    DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
    STATICFILES_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
else:
    # Serve static files from local file system
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Set this to supported api version.
# This will be the default version for unversioned apis picked by the swagger schema.
SERVER_API_VERSION = "v0"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "user.backends.JWTAuthenticateOrCreateUser",
    ],  # TokenAuthentication will only be used for the admin, and for test users in tutorials
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_VERSION": SERVER_API_VERSION,
    "PAGE_SIZE": 32,
}

SPECTACULAR_SETTINGS = {
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
        "filter": True,
        "syntaxHighlight.activate": True,
        "syntaxHighlight.theme": "monokai",
        # other swagger settings
    },
    "TITLE": "MedPerf API",
    "DESCRIPTION": "MedPerf API description",
    "VERSION": None,
    "SERVE_INCLUDE_SCHEMA": True,
    "PARSER_WHITELIST": [
        "rest_framework.parsers.JSONParser",
    ],
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "SWAGGER_UI_DIST": "SIDECAR",  # shorthand to use the sidecar instead
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # other spectacular settings
}

# Setup support for proxy headers
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "AUDIENCE": "https://api.medperf.org/",
    "ISSUER": "https://mlc-medperf.us.auth0.com/",
    "JWK_URL": "https://mlc-medperf.us.auth0.com/.well-known/jwks.json",
    "USER_ID_FIELD": "username",
    "USER_ID_CLAIM": "sub",
    "TOKEN_TYPE_CLAIM": None,
    "JTI_CLAIM": None,
    "AUTH_HEADER_TYPES": ("Token",),
}

if DEPLOY_ENV == "local-tutorials":
    SIMPLE_JWT["AUDIENCE"] = "https://localhost-tutorials/"

elif DEPLOY_ENV == "local":
    SIMPLE_JWT["ISSUER"] = "https://dev-5xl8y6uuc2hig2ly.us.auth0.com/"
    SIMPLE_JWT["AUDIENCE"] = "https://localhost-dev/"
    SIMPLE_JWT[
        "JWK_URL"
    ] = "https://dev-5xl8y6uuc2hig2ly.us.auth0.com/.well-known/jwks.json"
