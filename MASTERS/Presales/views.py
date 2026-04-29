from rest_framework.viewsets import ModelViewSet
from .models import PreSales
from .serializers import PreSalesSerializer

class PreSalesViewSet(ModelViewSet):
    queryset = PreSales.objects.all().order_by('-id')
    serializer_class = PreSalesSerializer