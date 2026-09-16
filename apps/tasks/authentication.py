from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.request import Request


class IdentityServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Не удалось получить ключи сервиса авторизации."
    default_code = "identity_unavailable"


@dataclass(frozen=True)
class Principal:
    id: UUID
    is_authenticated: bool = True


@lru_cache(maxsize=8)
def jwks_client(url: str) -> jwt.PyJWKClient:
    # Cache the set for five minutes, not individual keys indefinitely.
    return jwt.PyJWKClient(url, lifespan=300, timeout=5)


class RemoteJWTAuthentication(BaseAuthentication):
    def authenticate_header(self, request: Request) -> str:
        return "Bearer"

    def authenticate(self, request: Request) -> tuple[Principal, dict[str, Any]] | None:
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b"bearer":
            raise AuthenticationFailed("Ожидается Authorization: Bearer <access>.")
        token = header[1]
        try:
            unverified = jwt.get_unverified_header(token)
            if unverified.get("alg") != "RS256" or not isinstance(unverified.get("kid"), str) or not unverified["kid"]:
                raise AuthenticationFailed("Недопустимый заголовок токена.")
            # URL comes only from service settings, never from token headers.
            key = jwks_client(settings.AUTH_JWKS_URL).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=settings.AUTH_JWT_ISSUER,
                audience=settings.AUTH_JWT_AUDIENCE,
                options={"require": ["exp", "iat", "iss", "user_id", "token_type", "jti"]},
            )
            if claims["token_type"] != "access" or not isinstance(claims["user_id"], str):
                raise AuthenticationFailed("Требуется access-токен.")
            user_id = UUID(claims["user_id"])
        except jwt.PyJWKClientConnectionError as exc:
            raise IdentityServiceUnavailable() from exc
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AuthenticationFailed("Токен недействителен или истёк.") from exc
        return Principal(user_id), claims
