"""Common master APIs for geography, tax, company, and project lookups."""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import City, CommonMaster, Continent, Country, State, Tax, Company, Project
from .serializers import (
    CitySerializer,
    ContinentSerializer,
    CountrySerializer,
    StateSerializer,
    TaxSerializer,
    CompanySerializer,
    ProjectSerializer
)


class ContinentViewSet(viewsets.ModelViewSet):
    queryset = Continent.objects.filter(status=True).order_by("name")
    serializer_class = ContinentSerializer


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.select_related("continent").all().order_by("id")
    serializer_class = CountrySerializer

    def list(self, request, *args, **kwargs):
        search = request.GET.get("search[value]", "")
        start = int(request.GET.get("start", 0))
        length = int(request.GET.get("length", 10))

        queryset = self.queryset
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(continent__name__icontains=search)
            )

        total = self.queryset.count()
        filtered = queryset.count()
        queryset = queryset[start : start + length]

        data = []
        for index, obj in enumerate(queryset, start=1):
            data.append(
                {
                    "id": obj.pk,
                    "sno": start + index,
                    "country_name": obj.name,
                    "continent_name": obj.continent.name,
                    "country_code": obj.code,
                    "currency": obj.currency or "-",
                    "status": obj.status,
                }
            )

        return Response(
            {
                "draw": int(request.GET.get("draw", 1)),
                "recordsTotal": total,
                "recordsFiltered": filtered,
                "data": data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = request.data.get("status", instance.status)
        instance.save(update_fields=["status"])
        return Response({"message": "Status updated"})


@api_view(["GET"])
def country_list(request):
    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    search = request.GET.get("search[value]", "")

    queryset = Country.objects.select_related("continent").all()
    total = queryset.count()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(continent__name__icontains=search)
        )

    filtered = queryset.count()
    serializer = CountrySerializer(queryset[start : start + length], many=True)

    data = []
    for index, item in enumerate(serializer.data, start=1):
        data.append(
            {
                "sno": start + index,
                "country_name": item["name"],
                "country_code": item["code"],
                "continent": item.get("continent_name") or item["continent"],
                "currency": item["currency"] or "-",
                "status": "Active" if item["status"] else "Inactive",
                "id": item["id"],
            }
        )

    return Response(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered,
            "data": data,
        }
    )


@api_view(["POST"])
def create_country(request):
    serializer = CountrySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
def update_country(request, pk):
    try:
        obj = Country.objects.get(pk=pk)
    except Country.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = CountrySerializer(obj, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Updated successfully", "data": serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
def toggle_country(request, pk):
    try:
        obj = Country.objects.get(pk=pk)
    except Country.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    obj.status = not obj.status
    obj.save(update_fields=["status"])
    return Response({"message": "Status toggled", "status": obj.status})


@api_view(["GET"])
def continent_list(request):
    queryset = Continent.objects.filter(status=True).order_by("name")
    serializer = ContinentSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def create_continent(request):
    serializer = ContinentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
def update_continent(request, pk):
    try:
        obj = Continent.objects.get(pk=pk)
    except Continent.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = ContinentSerializer(obj, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Updated successfully", "data": serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
def toggle_continent(request, pk):
    try:
        obj = Continent.objects.get(pk=pk)
    except Continent.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    obj.status = not obj.status
    obj.save(update_fields=["status"])
    return Response({"message": "Status toggled", "status": obj.status})


@api_view(["GET"])
def get_countries(request):
    countries = Country.objects.filter(status=True).order_by("name")
    serializer = CountrySerializer(countries, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def create_state(request):
    serializer = StateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "State created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def list_states(request):
    states = State.objects.select_related("country").all().order_by("id")

    data = []
    for index, state_obj in enumerate(states, start=1):
        data.append(
            {
                "id": state_obj.pk,
                "sno": index,
                "country": state_obj.country.name,
                "state_name": state_obj.name,
                "is_active": state_obj.is_active,
            }
        )

    return Response({"data": data})


@api_view(["POST"])
def toggle_state(request, pk):
    try:
        state_obj = State.objects.get(id=pk)
    except State.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    state_obj.is_active = not state_obj.is_active
    state_obj.save(update_fields=["is_active"])
    return Response({"message": "Status updated"})


@api_view(["GET"])
def get_city_types(request):
    data = CommonMaster.objects.filter(type="CITY_TYPE", is_active=True).values("id", "name")
    return Response(list(data))


@api_view(["GET"])
def get_states_by_country(request, country_id):
    states = State.objects.filter(country_id=country_id, is_active=True).values("id", "name")
    return Response(list(states))


@api_view(["POST"])
def create_city(request):
    serializer = CitySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "City created"}, status=status.HTTP_201_CREATED)
    return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def list_city(request):
    search = request.GET.get("search[value]", "")
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    draw = int(request.GET.get("draw", 1))

    base_queryset = City.objects.select_related("country", "state", "city_type")
    queryset = base_queryset

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(pincode__icontains=search)
            | Q(state__name__icontains=search)
            | Q(country__name__icontains=search)
        )

    total = base_queryset.count()
    filtered = queryset.count()
    cities = queryset[start : start + length]

    data = []
    for index, city in enumerate(cities, start=1):
        data.append(
            {
                "sno": start + index,
                "city": city.name,
                "state": city.state.name,
                "country": city.country.name,
                "pincode": city.pincode,
                "status": city.is_active,
                "id": city.pk,
            }
        )

    return Response(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered,
            "data": data,
        }
    )


@api_view(["POST"])
def toggle_city(request, pk):
    try:
        city = City.objects.get(id=pk)
    except City.DoesNotExist:
        return Response(
            {"status": False, "message": "City not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    city.is_active = not city.is_active
    city.save(update_fields=["is_active"])
    return Response({"status": True})


@api_view(["GET"])
def get_city(request, pk):
    try:
        city = City.objects.get(id=pk)
    except City.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = CitySerializer(city)
    return Response(serializer.data)


@api_view(["POST"])
def create_tax(request):
    serializer = TaxSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Tax created"}, status=status.HTTP_201_CREATED)
    return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def list_tax(request):
    search = request.GET.get("search[value]", "")
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    draw = int(request.GET.get("draw", 1))

    base_queryset = Tax.objects.select_related("country")
    queryset = base_queryset

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(country__name__icontains=search)
            | Q(value__icontains=search)
        )

    total = base_queryset.count()
    filtered = queryset.count()
    taxes = queryset[start : start + length]

    data = []
    for index, tax in enumerate(taxes, start=1):
        data.append(
            {
                "sno": start + index,
                "tax_name": tax.name,
                "tax_value": float(tax.value),
                "country": tax.country.name if tax.country else "-",
                "status": tax.is_active,
                "id": tax.pk,
            }
        )

    return Response(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered,
            "data": data,
        }
    )


@api_view(["POST"])
def toggle_tax(request, pk):
    try:
        tax = Tax.objects.get(id=pk)
    except Tax.DoesNotExist:
        return Response({"status": False, "message": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    tax.is_active = not tax.is_active
    tax.save(update_fields=["is_active"])
    return Response({"status": True})


@api_view(["GET"])
def get_tax(request, pk):
    try:
        tax = Tax.objects.get(id=pk)
    except Tax.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = TaxSerializer(tax)
    return Response(serializer.data)


# Company Creation
@api_view(["GET"])
def list_company(request):
    search = request.GET.get("search[value]", "")
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    draw = int(request.GET.get("draw", 1))

    base_queryset = Company.objects.select_related("country", "state", "city")
    queryset = base_queryset

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(city__name__icontains=search)
        )

    total = base_queryset.count()
    filtered = queryset.count()

    companies = queryset[start:start+length]

    data = []
    for i, obj in enumerate(companies, start=1):
        data.append({
            "sno": start + i,
            "company_name": obj.name,
            "company_code": obj.code,
            "state": obj.state.name if obj.state else "",
            "city": obj.city.name if obj.city else "",
            "pincode": obj.pincode,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "logo": obj.logo.url if obj.logo else "",
            "document": obj.document.url if obj.document else "",
            "status": "Active" if obj.is_active else "Inactive",
            "id": obj.pk
        })

    return Response({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered,
        "data": data
    })

@api_view(["POST"])
def create_company(request):
    serializer = CompanySerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Created"})
    return Response({"status": False, "errors": serializer.errors})


@api_view(["PATCH"])
def toggle_company(request, pk):
    obj = Company.objects.get(pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    return Response({"status": True})

# Project Creation
@api_view(["GET"])
def list_project(request):
    search = request.GET.get("search[value]", "")
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    draw = int(request.GET.get("draw", 1))

    base_queryset = Project.objects.select_related(
        "company", "state", "city", "application_type"
    )

    queryset = base_queryset

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search) |
            Q(company__name__icontains=search)
        )

    total = base_queryset.count()
    filtered = queryset.count()

    projects = queryset[start:start+length]

    data = []
    for i, obj in enumerate(projects, start=1):
        data.append({
            "sno": start + i,
            "company_name": obj.company.name,
            "project_name": obj.name,
            "project_code": obj.code,
            "client_name": obj.client_name,
            "application_type": obj.application_type.name if obj.application_type else "",
            "capacity": obj.capacity,
            "state": obj.state.name if obj.state else "",
            "city": obj.city.name if obj.city else "",
            "contact_person": obj.contact_person,
            "contact_number": obj.contact_number,
            "status": "Active" if obj.is_active else "Inactive",
            "id": obj.pk
        })

    return Response({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered,
        "data": data
    })

@api_view(["POST"])
def create_project(request):
    serializer = ProjectSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Project created"})
    return Response({"status": False, "errors": serializer.errors})


@api_view(["PATCH"])
def toggle_project(request, pk):
    obj = Project.objects.get(pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    return Response({"status": True})

@api_view(["GET"])
def get_companies(request):
    data = Company.objects.filter(is_active=True).values("id", "name")
    return Response(list(data))


@api_view(["GET"])
def get_application_types(request):
    data = CommonMaster.objects.filter(type="APPLICATION_TYPE", is_active=True).values("id", "name")
    return Response(list(data))
