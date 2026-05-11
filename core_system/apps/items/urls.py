from django.urls import path

from .views import ItemViewSet

item_list = ItemViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)

item_import = ItemViewSet.as_view(
    {
        "post": "import_excel",
    }
)

item_detail = ItemViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("", item_list, name="item-list"),
    path("import/", item_import, name="item-import"),
    path("<int:pk>/", item_detail, name="item-detail"),
    path("<int:pk>", item_detail, name="item-detail-no-slash"),
]
