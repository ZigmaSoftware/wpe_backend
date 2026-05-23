from django.urls import path

from .views import ContactListCreateAPIView, ContactRetrieveUpdateDestroyAPIView


urlpatterns = [
    path("contacts/", ContactListCreateAPIView.as_view(), name="contact-list"),
    path("contacts", ContactListCreateAPIView.as_view(), name="contact-list-no-slash"),
    path("contacts/<int:pk>/", ContactRetrieveUpdateDestroyAPIView.as_view(), name="contact-detail"),
    path("contacts/<int:pk>", ContactRetrieveUpdateDestroyAPIView.as_view(), name="contact-detail-no-slash"),
]

