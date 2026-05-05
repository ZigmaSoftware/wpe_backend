from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from .models import PreSales
from .serializers import PreSalesSerializer

class PreSalesViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PreSales.objects.all().order_by('-id')
    serializer_class = PreSalesSerializer
