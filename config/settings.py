from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
env.read_env(BASE_DIR / ".env")
DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = ["django.contrib.contenttypes", "rest_framework", "tasks"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
USE_TZ = True
LANGUAGE_CODE = "ru"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_JWKS_URL = env("AUTH_JWKS_URL", default="http://127.0.0.1:8000/auth/jwks.json")
AUTH_JWT_ISSUER = env("AUTH_JWT_ISSUER", default="django-template-auth")
AUTH_JWT_AUDIENCE = env("AUTH_JWT_AUDIENCE", default="") or None
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["tasks.authentication.RemoteJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
