from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse

from .authentication import authenticate_api_request


def _path_matches(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        normalized = pattern.rstrip("/")
        if not normalized:
            continue
        if path == normalized or path.startswith(f"{normalized}/"):
            return True
    return False


class DisableAPICSRFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_prefix = getattr(settings, "API_PATH_PREFIX", "/api/")

    def __call__(self, request):
        if request.path.startswith(self.api_prefix):
            request._dont_enforce_csrf_checks = True

        return self.get_response(request)


class APIAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_prefix = getattr(settings, "API_PATH_PREFIX", "/api/")

    def __call__(self, request):
        if request.method == "OPTIONS":
            return self.get_response(request)

        if not request.path.startswith(self.api_prefix):
            return self.get_response(request)

        exempt_paths = list(getattr(settings, "API_AUTH_EXEMPT_PATHS", []))
        if _path_matches(request.path, exempt_paths):
            return self.get_response(request)

        auth_result = authenticate_api_request(request)
        if not auth_result.is_authenticated:
            response = JsonResponse(
                {
                    "detail": auth_result.error or "Authentication credentials were not provided.",
                    "code": "not_authenticated",
                },
                status=401,
            )
            response["WWW-Authenticate"] = "Bearer"
            return response

        request.user = auth_result.user
        request.auth = auth_result.auth
        request.api_auth_type = auth_result.auth_type

        if auth_result.auth_type == "api_key":
            request.api_key_authenticated = True

        return self.get_response(request)

