from django.urls import path
from .views import GRNCreateAPIView

urlpatterns = [
    path('grn/', GRNCreateAPIView.as_view(), name='grn-create'),
]