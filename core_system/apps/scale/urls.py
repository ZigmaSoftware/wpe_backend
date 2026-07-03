from django.urls import path

from .views import (
    ScaleBridgeDemandActivationView,
    LatestWeightView,
    ListPortsView,
    ScaleBridgeDemandStatusView,
    ScaleBridgeDevicesView,
    ScaleBridgeReadingIngestView,
)

# Some scale endpoints are not called directly by the React frontend. They may
# be used by local bridge clients, hardware diagnostics, workstation/device
# discovery, and deployment clients. Do not remove without checking bridge.py
# and external scale integrations.
urlpatterns = [
    path("weight/latest/", LatestWeightView.as_view(), name="scale-weight-latest"),
    path("ports/", ListPortsView.as_view(), name="scale-ports"),
    path("devices/", ScaleBridgeDevicesView.as_view(), name="scale-devices"),
    path("bridge/demand/", ScaleBridgeDemandStatusView.as_view(), name="scale-bridge-demand"),
    path("bridge/demand/activate/", ScaleBridgeDemandActivationView.as_view(), name="scale-bridge-demand-activate"),
    path("bridge/readings/", ScaleBridgeReadingIngestView.as_view(), name="scale-bridge-readings"),
]
