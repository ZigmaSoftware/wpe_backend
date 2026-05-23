from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from typing import Any

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@dataclass
class HeaderAuthenticationResult:
    auth_type: str | None = None
    user: Any = None
    auth: Any = None
    error: str | None = None
    attempted: bool = False

    @property
    def is_authenticated(self) -> bool:
        return self.auth_type is not None


class ServiceAPIUser:
    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False
    pk = None
    id = None
    username = "service-api"
    email = ""

    def __str__(self) -> str:
        return self.username


def _service_api_key() -> str:
    return (getattr(settings, "INTERNAL_API_KEY", "") or "").strip()


def _request_object(request):
    return getattr(request, "_request", request)


def extract_api_key(request) -> str | None:
    django_request = _request_object(request)

    authorization = (django_request.META.get("HTTP_AUTHORIZATION") or "").strip()
    if authorization.lower().startswith("api-key "):
        api_key = authorization[8:].strip()
        return api_key or None

    x_api_key = (django_request.META.get("HTTP_X_API_KEY") or "").strip()
    return x_api_key or None


def authenticate_jwt_request(request) -> HeaderAuthenticationResult:
    django_request = _request_object(request)
    jwt_authentication = JWTAuthentication()

    header = jwt_authentication.get_header(django_request)
    if header is None:
        return HeaderAuthenticationResult()

    header_text = header.decode() if isinstance(header, bytes) else str(header)
    if not header_text.lower().startswith("bearer"):
        return HeaderAuthenticationResult()

    try:
        raw_token = jwt_authentication.get_raw_token(header)
        if raw_token is None:
            return HeaderAuthenticationResult(
                error="Invalid Authorization header. Expected 'Bearer <token>'.",
                attempted=True,
            )

        validated_token = jwt_authentication.get_validated_token(raw_token)
        user = jwt_authentication.get_user(validated_token)
    except (InvalidToken, TokenError, exceptions.AuthenticationFailed) as exc:
        return HeaderAuthenticationResult(error=str(exc), attempted=True)

    return HeaderAuthenticationResult(
        auth_type="jwt",
        user=user,
        auth=validated_token,
        attempted=True,
    )


def authenticate_api_key_request(request) -> HeaderAuthenticationResult:
    candidate = extract_api_key(request)
    if candidate is None:
        return HeaderAuthenticationResult()

    expected = _service_api_key()
    if not expected or not compare_digest(candidate, expected):
        return HeaderAuthenticationResult(error="Invalid API key.", attempted=True)

    return HeaderAuthenticationResult(
        auth_type="api_key",
        user=ServiceAPIUser(),
        auth={"type": "api_key"},
        attempted=True,
    )


def authenticate_api_request(request) -> HeaderAuthenticationResult:
    django_request = _request_object(request)
    cached_result = getattr(django_request, "_api_header_auth_result", None)
    if cached_result is not None:
        return cached_result

    jwt_result = authenticate_jwt_request(django_request)
    if jwt_result.is_authenticated:
        django_request._api_header_auth_result = jwt_result
        return jwt_result

    api_key_result = authenticate_api_key_request(django_request)
    if api_key_result.is_authenticated:
        django_request._api_header_auth_result = api_key_result
        return api_key_result

    if jwt_result.attempted:
        result = HeaderAuthenticationResult(
            error=jwt_result.error or "Invalid JWT token.",
            attempted=True,
        )
    elif api_key_result.attempted:
        result = api_key_result
    else:
        result = HeaderAuthenticationResult(
            error="Authentication credentials were not provided.",
            attempted=False,
        )

    django_request._api_header_auth_result = result
    return result


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        django_request = _request_object(request)
        cached_result = getattr(django_request, "_api_header_auth_result", None)

        if cached_result and cached_result.auth_type == "api_key":
            return cached_result.user, cached_result.auth

        result = authenticate_api_key_request(django_request)
        if result.is_authenticated:
            django_request._api_header_auth_result = result
            return result.user, result.auth

        if result.attempted:
            raise exceptions.AuthenticationFailed(result.error or "Invalid API key.")

        return None

    def authenticate_header(self, request) -> str:
        return "Bearer"

