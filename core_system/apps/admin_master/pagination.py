"""Pagination helpers with DataTables-compatible fallback responses."""

from __future__ import annotations

from common.drf import DataTablesPageNumberPagination


class AdminMasterPagination(DataTablesPageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200
