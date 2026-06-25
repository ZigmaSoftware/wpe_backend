from django.urls import path
from .views import ConnectView, DisconnectView, PortsView

urlpatterns = [
    path("ports/", PortsView.as_view(), name="weighscale-ports"),
    path("connect/", ConnectView.as_view(), name="weighscale-connect"),
    path("disconnect/", DisconnectView.as_view(), name="weighscale-disconnect"),
]
