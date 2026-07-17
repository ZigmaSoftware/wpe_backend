from django.conf import settings
from django.urls import path

from .views import (
    TaskTrackerAddRowAPIView,
    TaskTrackerDeleteRowAPIView,
    TaskTrackerListAPIView,
    TaskTrackerUpdateRowAPIView,
)


urlpatterns = [
    path("", TaskTrackerListAPIView.as_view(), name="task-tracker-list"),
    path("add/", TaskTrackerAddRowAPIView.as_view(), name="task-tracker-add"),
    path("update/", TaskTrackerUpdateRowAPIView.as_view(), name="task-tracker-update"),
    path("delete/", TaskTrackerDeleteRowAPIView.as_view(), name="task-tracker-delete"),
]

legacy_urlpatterns = [
    path("add", TaskTrackerAddRowAPIView.as_view(), name="task-tracker-add-no-slash"),
    path("update", TaskTrackerUpdateRowAPIView.as_view(), name="task-tracker-update-no-slash"),
    path("delete", TaskTrackerDeleteRowAPIView.as_view(), name="task-tracker-delete-no-slash"),
]

if settings.ENABLE_LEGACY_ROUTE_ALIASES:
    urlpatterns += legacy_urlpatterns
