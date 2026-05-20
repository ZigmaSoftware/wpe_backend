from __future__ import annotations

from django.db.models import ProtectedError, Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


def success_response(*, message: str, data=None, status_code: int = 200, success: bool = True) -> Response:
    return Response(
        {
            "success": success,
            "message": message,
            "data": {} if data is None else data,
        },
        status=status_code,
    )


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_data(self, data):
        return {
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        }

    def get_paginated_response(self, data):
        return Response(self.get_paginated_data(data))


class DataTablesPageNumberPagination(StandardResultsSetPagination):
    datatables_mode = False
    datatables_draw = 1
    datatables_start = 0
    datatables_length = 20

    def paginate_queryset(self, queryset, request, view=None):
        if any(param in request.query_params for param in ("draw", "start", "length")):
            self.datatables_mode = True
            self.request = request
            self.count = queryset.count()
            self.datatables_draw = int(request.query_params.get("draw", 1))
            self.datatables_start = max(int(request.query_params.get("start", 0)), 0)
            self.datatables_length = max(int(request.query_params.get("length", self.page_size)), 1)
            self.datatables_length = min(self.datatables_length, self.max_page_size)
            return list(queryset[self.datatables_start : self.datatables_start + self.datatables_length])

        self.datatables_mode = False
        return super().paginate_queryset(queryset, request, view=view)

    def get_paginated_response(self, data):
        if self.datatables_mode:
            return Response(
                {
                    "draw": self.datatables_draw,
                    "recordsTotal": self.count,
                    "recordsFiltered": self.count,
                    "data": data,
                }
            )

        return super().get_paginated_response(data)


def _coerce_filter_value(value: str):
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return value


class QueryParamFilterMixin:
    filterset_map: dict[str, str] = {}

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        search_value = (
            self.request.query_params.get("search[value]")
            if not self.request.query_params.get("search")
            else None
        )
        if search_value:
            query = Q()
            for field_name in getattr(self, "search_fields", ()):
                if field_name.startswith(("^", "=", "@", "$")):
                    field_name = field_name[1:]
                query |= Q(**{f"{field_name}__icontains": search_value})
            queryset = queryset.filter(query)
        for param, lookup in self.filterset_map.items():
            value = self.request.query_params.get(param)
            if value in (None, ""):
                continue
            queryset = queryset.filter(**{lookup: _coerce_filter_value(value)})
        return queryset


class ResponseSerializerMixin:
    response_serializer_class = None

    def get_response_serializer_class(self):
        return self.response_serializer_class or self.get_serializer_class()

    def serialize_instance(self, instance):
        serializer_class = self.get_response_serializer_class()
        serializer = serializer_class(instance, context=self.get_serializer_context())
        return serializer.data


class StandardizedListMixin(ResponseSerializerMixin):
    def list(self, request, *args, **kwargs):
        base_queryset = self.get_queryset()
        total_count = base_queryset.count()
        filtered_queryset = self.filter_queryset(base_queryset)
        filtered_count = filtered_queryset.count()

        page = self.paginate_queryset(filtered_queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if getattr(self.paginator, "datatables_mode", False):
                response.data["recordsTotal"] = total_count
                response.data["recordsFiltered"] = filtered_count
            return response

        serializer = self.get_serializer(filtered_queryset, many=True)
        return Response(serializer.data)


class EnvelopedMutationMixin(ResponseSerializerMixin):
    resource_name = "Record"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data if isinstance(serializer.data, dict) else {})
        return Response(
            {
                "message": f"{self.resource_name} created successfully.",
                "data": self.serialize_instance(serializer.instance),
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            {
                "message": f"{self.resource_name} updated successfully.",
                "data": self.serialize_instance(serializer.instance),
            }
        )


class RawMutationMixin(ResponseSerializerMixin):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        headers = self.get_success_headers(serializer.data if isinstance(serializer.data, dict) else {})
        return Response(
            self.serialize_instance(instance),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(self.serialize_instance(instance))


class ProtectedDestroyMixin:
    resource_name = "Record"
    destroy_success_message = None
    destroy_success_status = status.HTTP_200_OK
    protected_error_message = "Cannot delete: this record is referenced by other data."
    protected_error_as_validation_error = False

    def build_destroy_success_response(self):
        if self.destroy_success_message:
            return Response({"message": self.destroy_success_message}, status=self.destroy_success_status)
        return Response(status=self.destroy_success_status)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            if self.protected_error_as_validation_error:
                raise ValidationError({"detail": self.protected_error_message})
            return Response({"detail": self.protected_error_message}, status=status.HTTP_400_BAD_REQUEST)
        return self.build_destroy_success_response()


class ToggleStatusMixin:
    resource_name = "Record"
    status_field = "is_active"

    def perform_toggle_status(
        self,
        *,
        update_fields: list[str] | tuple[str, ...] | None = None,
        response_mode: str = "message",
    ) -> Response:
        instance = self.get_object()
        field_name = self.status_field
        new_value = not bool(getattr(instance, field_name))
        setattr(instance, field_name, new_value)

        fields_to_update = list(update_fields) if update_fields else [field_name]
        instance.save(update_fields=fields_to_update)

        if response_mode == "serializer":
            return Response(self.serialize_instance(instance))

        return Response({"message": f"{self.resource_name} status updated.", "status": new_value})


class LookupQuerysetMixin:
    status_field = "is_active"
    lookup_status_field = None

    def get_lookup_queryset(self):
        queryset = self.filter_queryset(self.get_queryset())
        status_field = self.lookup_status_field if self.lookup_status_field is not None else self.status_field
        if status_field:
            queryset = queryset.filter(**{status_field: True})
        return queryset

    def build_lookup_response(self, *values):
        return Response(list(self.get_lookup_queryset().values(*values)))
