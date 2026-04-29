from django.urls import path
from .views import ItemViewSet

item_list = ItemViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

item_import = ItemViewSet.as_view({
    'post': 'import_excel',
})

item_detail = ItemViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('items/', item_list, name='item-list'),
    path('items/import/', item_import, name='item-import'),
    path('items/<int:pk>/', item_detail, name='item-detail'),
]
