from rest_framework import serializers
from .models import PreSales

class PreSalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreSales
        fields = '__all__'

