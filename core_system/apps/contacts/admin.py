from django.contrib import admin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "category", "is_active")
    list_filter = ("category", "is_active", "state")
    search_fields = ("ref_code", "name", "phone", "email", "company_name")

