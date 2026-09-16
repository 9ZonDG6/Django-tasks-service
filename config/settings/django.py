from config.settings.env import env

DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
USE_TZ = True
LANGUAGE_CODE = "ru"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
