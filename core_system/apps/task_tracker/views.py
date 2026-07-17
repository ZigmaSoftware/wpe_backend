from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated

from common.drf import success_response

from .serializers import (
    TaskTrackerAddRowSerializer,
    TaskTrackerDeleteRowSerializer,
    TaskTrackerUpdateRowSerializer,
)
from .sheets import TaskTrackerSheetError, add_row, delete_row, list_rows, update_row


def _sheet_api_exception(exc: Exception) -> APIException:
    api_exception = APIException(str(exc))
    api_exception.status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    return api_exception


@method_decorator(ensure_csrf_cookie, name="dispatch")
class TaskTrackerListAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            data = list_rows()
        except (ImproperlyConfigured, TaskTrackerSheetError) as exc:
            raise _sheet_api_exception(exc) from exc

        response = success_response(
            message="Task tracker rows fetched successfully.",
            data=data,
        )
        response["X-CSRFToken"] = get_token(request)
        return response


class TaskTrackerAddRowAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskTrackerAddRowSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            add_row(serializer.validated_data["cells"])
        except (ImproperlyConfigured, TaskTrackerSheetError) as exc:
            raise _sheet_api_exception(exc) from exc

        return success_response(
            message="Task tracker row added successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class TaskTrackerUpdateRowAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskTrackerUpdateRowSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            update_row(serializer.validated_data["row"], serializer.validated_data["cells"])
        except (ImproperlyConfigured, TaskTrackerSheetError) as exc:
            raise _sheet_api_exception(exc) from exc

        return success_response(message="Task tracker row updated successfully.")


class TaskTrackerDeleteRowAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskTrackerDeleteRowSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delete_row(serializer.validated_data["row"])
        except (ImproperlyConfigured, TaskTrackerSheetError) as exc:
            raise _sheet_api_exception(exc) from exc

        return success_response(message="Task tracker row deleted successfully.")
