from rest_framework import viewsets
from .models import Item
from .serializers import ItemSerializer
from rest_framework.decorators import action
from rest_framework.response import Response



class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all().order_by('-id')
    serializer_class = ItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        category = self.request.query_params.get('category')
        group = self.request.query_params.get('group')
        sub_group = self.request.query_params.get('sub_group')

        if category:
            queryset = queryset.filter(category=category)
        if group:
            queryset = queryset.filter(group=group)
        if sub_group:
            queryset = queryset.filter(sub_group=sub_group)

        return queryset