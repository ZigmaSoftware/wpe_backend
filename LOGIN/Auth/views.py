from django.contrib.auth import authenticate, login, logout
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer


class LoginAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return Response({"message": "Login successful"}, status=200)
        else:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request)
        return Response({"message": "Logged out"}, status=200)