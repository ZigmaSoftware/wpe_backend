from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.http import FileResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated

from common.drf import success_response

from .google_drive import DriveServiceError, delete_file, download_file, list_files, upload_file
from .serializers import DriveDeleteSerializer, DriveUploadSerializer


def _drive_api_exception(exc: Exception) -> APIException:
    api_exception = APIException(str(exc))
    api_exception.status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    if isinstance(exc, DriveServiceError) and exc.data:
        api_exception.detail = {"detail": str(exc), **exc.data}
    return api_exception


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DriveListAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            data = list_files()
        except (ImproperlyConfigured, DriveServiceError) as exc:
            raise _drive_api_exception(exc) from exc

        response = success_response(message="Drive files fetched successfully.", data=data)
        response["X-CSRFToken"] = get_token(request)
        return response


class DriveUploadAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriveUploadSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            file = upload_file(serializer.validated_data["file"])
        except (ImproperlyConfigured, DriveServiceError) as exc:
            raise _drive_api_exception(exc) from exc

        return success_response(
            message="Drive file uploaded successfully.",
            data={"file": file},
            status_code=status.HTTP_201_CREATED,
        )


class DriveDeleteAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriveDeleteSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delete_file(
                serializer.validated_data["id"],
                permanent=serializer.validated_data.get("permanent", True),
            )
        except (ImproperlyConfigured, DriveServiceError) as exc:
            raise _drive_api_exception(exc) from exc

        return success_response(message="Drive file deleted successfully.")


class DriveDownloadAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        file_id = (request.query_params.get("id") or "").strip()
        if not file_id:
            api_exception = APIException("File id is required.")
            api_exception.status_code = status.HTTP_400_BAD_REQUEST
            raise api_exception

        try:
            file, output = download_file(file_id)
        except (ImproperlyConfigured, DriveServiceError) as exc:
            raise _drive_api_exception(exc) from exc

        return FileResponse(
            output,
            as_attachment=True,
            filename=file.get("name") or "download",
            content_type=file.get("mimeType") or "application/octet-stream",
        )
