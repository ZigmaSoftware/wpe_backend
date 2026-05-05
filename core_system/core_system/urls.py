from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.auth.views import LoginAPIView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", LoginAPIView.as_view(), name="token_obtain_pair"),
    path("api/token", LoginAPIView.as_view(), name="token_obtain_pair_no_slash"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/refresh", TokenRefreshView.as_view(), name="token_refresh_no_slash"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/token/verify", TokenVerifyView.as_view(), name="token_verify_no_slash"),
    path("api/auth/", include("apps.auth.urls")),
    path("api/blending/", include("apps.blending.urls")),
    path("api/items/", include("apps.items.urls")),
    path("api/presales/", include("apps.presales.urls")),
    path("api/contacts/", include("apps.contacts.urls")),
]
