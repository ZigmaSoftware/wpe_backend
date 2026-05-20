from common.drf import StandardResultsSetPagination


class WpeMasterPagination(StandardResultsSetPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 500
