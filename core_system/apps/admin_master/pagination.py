"""Pagination helpers with DataTables-compatible fallback responses."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class AdminMasterPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

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

        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
