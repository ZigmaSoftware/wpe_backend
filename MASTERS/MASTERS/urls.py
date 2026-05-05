from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/',include("Items.urls")),
    path('api/',include("Purchases_Inwards.urls")),
    path('api/',include("Presales.urls")),
    path("api/auth/", include("MASTERS.auth_urls")),
]
