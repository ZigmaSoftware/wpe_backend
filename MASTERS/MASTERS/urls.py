from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('api/auth/', include("Auth.urls")),
    path('api/', include("Items.urls")),
    path('api/', include("Purchases_Inwards.urls")),
    path('api/', include("Presales.urls")),
]
