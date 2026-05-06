from django.urls import path

from .auth_views import CsrfAPIView, LoginAPIView, LogoutAPIView, SessionAPIView


urlpatterns = [
    path("csrf/", CsrfAPIView.as_view(), name="auth-csrf"),
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("session/", SessionAPIView.as_view(), name="auth-session"),
    path("logout/", LogoutAPIView.as_view(), name="auth-logout"),
]
