from rest_framework import filters
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Contact
from .serializers import ContactSerializer


class ContactListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ("name", "phone", "email")

    def get_queryset(self):
        queryset = Contact.objects.all().order_by("-created_at", "-id")
        category = (self.request.query_params.get("category") or "").strip()
        if category:
            queryset = queryset.filter(category__iexact=category)
        return queryset


class ContactRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    queryset = Contact.objects.all().order_by("-created_at", "-id")

