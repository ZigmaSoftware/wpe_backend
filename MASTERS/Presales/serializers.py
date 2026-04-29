from rest_framework import serializers
from .models import PreSales

class PreSalesSerializer(serializers.ModelSerializer):
    class Meta:
        db_table = "PreSales"

