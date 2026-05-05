from django.urls import path
from .views import CsrfAPIView, LoginAPIView, LogoutAPIView, SessionAPIView

urlpatterns = [
    path("csrf/", CsrfAPIView.as_view()),
    path("login/", LoginAPIView.as_view()),
    path("session/", SessionAPIView.as_view()),
    path("logout/", LogoutAPIView.as_view()),
]
