from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.auth.views import LoginAPIView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", LoginAPIView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/", include("apps.auth.urls")),
    path("api/blending/", include("apps.blending.urls")),
    path("api/store/", include("apps.store.urls")),
    path("api/presales/", include("apps.presales.urls")),
    path("api/presales", include("apps.presales.urls")),
    path("api/contacts/", include("apps.contacts.urls")),
    path("api/users/", include("apps.admin_master.urls")),
    path("api/masters/", include("apps.common_master.urls")),
    path("api/production/", include("apps.production.urls")),
    path("api/wpe-masters/", include("apps.wpe_masters.urls")),
    path("api/", include("grn_app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
