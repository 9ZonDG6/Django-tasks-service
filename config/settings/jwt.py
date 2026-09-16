from config.settings.env import env

AUTH_JWKS_URL = env("AUTH_JWKS_URL", default="http://localhost:8000/.well-known/jwks.json")
AUTH_JWT_ISSUER = env("AUTH_JWT_ISSUER", default="django-template-auth")
AUTH_JWT_AUDIENCE = env("AUTH_JWT_AUDIENCE", default="") or None
