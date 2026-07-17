from django.conf import settings
from django.urls import path

from .views import DriveDeleteAPIView, DriveDownloadAPIView, DriveListAPIView, DriveUploadAPIView


urlpatterns = [
    path("", DriveListAPIView.as_view(), name="drive-list"),
    path("upload/", DriveUploadAPIView.as_view(), name="drive-upload"),
    path("delete/", DriveDeleteAPIView.as_view(), name="drive-delete"),
    path("download/", DriveDownloadAPIView.as_view(), name="drive-download"),
]

legacy_urlpatterns = [
    path("upload", DriveUploadAPIView.as_view(), name="drive-upload-no-slash"),
    path("delete", DriveDeleteAPIView.as_view(), name="drive-delete-no-slash"),
    path("download", DriveDownloadAPIView.as_view(), name="drive-download-no-slash"),
]

if settings.ENABLE_LEGACY_ROUTE_ALIASES:
    urlpatterns += legacy_urlpatterns
