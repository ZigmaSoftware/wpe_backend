from django.urls import path
from .views import ItemViewSet

item_list = ItemViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

item_import = ItemViewSet.as_view({
    'post': 'import_excel',
})

item_stock_analysis = ItemViewSet.as_view({
    'get': 'stock_analysis',
})

item_inward_stock = ItemViewSet.as_view({
    'post': 'add_inward_stock',
})

item_outward_stock = ItemViewSet.as_view({
    'post': 'add_outward_stock',
})

item_detail_stock_analysis = ItemViewSet.as_view({
    'get': 'stock_analysis',
})

item_detail = ItemViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path('items', item_list, name='item-list'),
    path('items/', item_list, name='item-list-slash'),
    path('items/import/', item_import, name='item-import'),
    path('items/stock-analysis/', item_stock_analysis, name='item-stock-analysis'),
    path('items/<int:pk>/stock/inward/', item_inward_stock, name='item-stock-inward'),
    path('items/<int:pk>/stock/outward/', item_outward_stock, name='item-stock-outward'),
    path('items/<int:pk>/stock-analysis/', item_detail_stock_analysis, name='item-detail-stock-analysis'),
    path('items/<int:pk>/', item_detail, name='item-detail'),
    path('items/<int:pk>', item_detail, name='item-detail-no-slash'),
]
