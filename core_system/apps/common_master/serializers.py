"""Serializers for shared geography, tax, company, and project masters."""

from rest_framework import serializers

from .models import City, Continent, Country, State, Tax, Company, Project


class ContinentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = "__all__"


class CountrySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent.name", read_only=True)

    class Meta:
        model = Country
        fields = "__all__"


class StateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = State
        fields = ["id", "name", "country", "country_name", "is_active", "created_at"]
        read_only_fields = ["created_at"]


class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_type_name = serializers.CharField(source="city_type.name", read_only=True)

    class Meta:
        model = City
        fields = [
            "id",
            "country",
            "country_name",
            "state",
            "state_name",
            "name",
            "pincode",
            "city_type",
            "city_type_name",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        if not attrs.get("name"):
            raise serializers.ValidationError("City name required")
        if not attrs.get("state"):
            raise serializers.ValidationError("State required")
        return attrs


class TaxSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)

    class Meta:
        model = Tax
        fields = [
            "id",
            "country",
            "country_name",
            "name",
            "value",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        if not attrs.get("name"):
            raise serializers.ValidationError("Tax name required")
        if attrs.get("value") is None:
            raise serializers.ValidationError("Tax value required")
        if float(attrs["value"]) < 0:
            raise serializers.ValidationError("Tax cannot be negative")
        return attrs



# Company creation
class CompanySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = Company
        fields = "__all__"

# Project Creation
class ProjectSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    application_type_name = serializers.CharField(source="application_type.name", read_only=True)

    class Meta:
        model = Project
        fields = "__all__"
