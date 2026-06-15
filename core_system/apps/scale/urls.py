from django.urls import path

from .views import LatestWeightView, ListPortsView

urlpatterns = [
    path("weight/latest/", LatestWeightView.as_view(), name="scale-weight-latest"),
    path("ports/",          ListPortsView.as_view(),    name="scale-ports"),
]
