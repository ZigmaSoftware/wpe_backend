from django.urls import path

from .views import LatestWeightView, ListPortsView, ScaleBridgeDevicesView, ScaleBridgeReadingIngestView

urlpatterns = [
    path("weight/latest/", LatestWeightView.as_view(), name="scale-weight-latest"),
    path("ports/", ListPortsView.as_view(), name="scale-ports"),
    path("devices/", ScaleBridgeDevicesView.as_view(), name="scale-devices"),
    path("bridge/readings/", ScaleBridgeReadingIngestView.as_view(), name="scale-bridge-readings"),
]
