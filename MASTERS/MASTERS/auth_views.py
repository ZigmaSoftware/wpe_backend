import logging

from django.contrib.auth import authenticate, login, logout
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({"message": "CSRF cookie set"}, status=status.HTTP_200_OK)


class LoginAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = authenticate(
                request,
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
        except DatabaseError:
            logger.exception("Authentication failed because the database is unavailable.")
            return Response(
                {"error": "Authentication service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if user is None:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            login(request, user)
        except DatabaseError:
            logger.exception("Login failed because the session store is unavailable.")
            return Response(
                {"error": "Login service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"message": "Login successful"}, status=status.HTTP_200_OK)


class SessionAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        try:
            is_authenticated = request.user.is_authenticated
        except DatabaseError:
            logger.exception("Session lookup failed because the database is unavailable.")
            return Response(
                {"error": "Session service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not is_authenticated:
            return Response({"authenticated": False}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(
            {
                "authenticated": True,
                "username": request.user.get_username(),
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    def post(self, request):
        try:
            logout(request)
        except DatabaseError:
            logger.exception("Logout failed because the session store is unavailable.")
            return Response(
                {"error": "Logout service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"message": "Logged out"}, status=status.HTTP_200_OK)
