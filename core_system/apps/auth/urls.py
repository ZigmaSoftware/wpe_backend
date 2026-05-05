from django.urls import path

from .views import CurrentUserAPIView, LoginAPIView, LogoutAPIView


urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("login", LoginAPIView.as_view(), name="auth-login-no-slash"),
    path("logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("logout", LogoutAPIView.as_view(), name="auth-logout-no-slash"),
    path("me/", CurrentUserAPIView.as_view(), name="auth-me"),
    path("me", CurrentUserAPIView.as_view(), name="auth-me-no-slash"),
]
