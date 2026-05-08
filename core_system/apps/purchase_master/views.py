# Units - This file defines the API views for managing units in the purchase_master module of the MASTERS app, including a viewset for CRUD operations on UnitMaster model instances and path-based views for listing units with pagination and search functionality, creating new units, updating existing units, and toggling unit status. The UnitViewSet class provides methods for handling create, update, and delete operations, while the path-based views allow for more customized handling of unit-related API requests, including soft deletion by deactivating units instead of permanently removing them from the database.
from typing import Any, cast

from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.common_master.models import Company
from .models import (
    Category,
    ItemGroup,
    ItemMaster,
    ProductCreation,
    StandardBOM,
    StandardBOMItem,
    SubGroup,
    UnitMaster,
)
from .serializers import CreateBOMSerializer, StandardBOMSerializer, UnitSerializer

class UnitViewSet(viewsets.ModelViewSet):
    queryset = UnitMaster.objects.all().order_by('-id')
    serializer_class = UnitSerializer

    def create(self, request, *args, **kwargs):
        if UnitMaster.objects.filter(unit_name=request.data.get('unit_name')).exists():
            return Response({"error": "Unit already exists"}, status=400)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Soft delete (better for ERP)
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response({"message": "Unit deactivated"})


# Path-based views for units
@api_view(['GET'])
def unit_list(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search = request.GET.get('search[value]', '')

    queryset = UnitMaster.objects.all().order_by('-id')

    total = queryset.count()

    if search:
        queryset = queryset.filter(
            Q(unit_name__icontains=search) |
            Q(description__icontains=search)
        )

    filtered = queryset.count()
    queryset = queryset[start:start+length]

    serializer = UnitSerializer(queryset, many=True)

    data = []
    for i, item in enumerate(serializer.data, start=1):
        data.append({
            "sno": start + i,
            "unit_name": item["unit_name"],
            "decimal_points": item["decimal_points"],
            "description": item["description"] or "-",
            "status": "Active" if item["is_active"] else "Inactive",
            "id": item["id"]
        })

    return Response({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered,
        "data": data
    })


@api_view(['POST'])
def create_unit(request):
    # Check if unit already exists
    if UnitMaster.objects.filter(unit_name=request.data.get('unit_name')).exists():
        return Response({"error": "Unit already exists"}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = UnitSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
def update_unit(request, pk):
    try:
        obj = UnitMaster.objects.get(pk=pk)
    except UnitMaster.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UnitSerializer(obj, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "Updated successfully", "data": serializer.data})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
def toggle_unit(request, pk):
    try:
        obj = UnitMaster.objects.get(pk=pk)
    except UnitMaster.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    
    obj.is_active = not obj.is_active
    obj.save()

    return Response({"message": "Status toggled", "status": obj.is_active})

# Item_groups - This file defines the API views for managing item groups in the purchase_master module of the MASTERS app, including path-based views for listing item groups with pagination and search functionality, creating new item groups, updating existing item groups, and toggling item group status. The views handle HTTP requests and return appropriate responses based on the operations performed on the ItemGroup model, allowing for organized management of item group data within the system.
# LIST (with optional search)
@api_view(['GET'])
def item_group_list(request):
    search = request.GET.get('search', '')

    queryset = ItemGroup.objects.all()

    if search:
        queryset = queryset.filter(group_name__icontains=search)

    data = list(queryset.values())

    return Response({
        "status": True,
        "data": data
    })


# CREATE
@api_view(['POST'])
def create_item_group(request):
    group_name = request.data.get('group_name')
    code = request.data.get('code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    # VALIDATION
    if not group_name:
        return Response({"status": False, "message": "Group name is required"}, status=400)

    if not code:
        return Response({"status": False, "message": "Code is required"}, status=400)

    if ItemGroup.objects.filter(group_name=group_name).exists():
        return Response({"status": False, "message": "Group name already exists"}, status=400)

    if ItemGroup.objects.filter(code=code).exists():
        return Response({"status": False, "message": "Code already exists"}, status=400)

    # CREATE
    ItemGroup.objects.create(
        group_name=group_name,
        code=code,
        description=description,
        is_active=is_active
    )

    return Response({
        "status": True,
        "message": "Item Group created successfully"
    })


# UPDATE
@api_view(['PUT'])
def update_item_group(request, pk):
    try:
        obj = ItemGroup.objects.get(id=pk)
    except ItemGroup.DoesNotExist:
        return Response({"status": False, "message": "Item Group not found"}, status=404)

    group_name = request.data.get('group_name')
    code = request.data.get('code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    # VALIDATION
    if not group_name:
        return Response({"status": False, "message": "Group name is required"}, status=400)

    if not code:
        return Response({"status": False, "message": "Code is required"}, status=400)

    if ItemGroup.objects.exclude(id=pk).filter(group_name=group_name).exists():
        return Response({"status": False, "message": "Group name already exists"}, status=400)

    if ItemGroup.objects.exclude(id=pk).filter(code=code).exists():
        return Response({"status": False, "message": "Code already exists"}, status=400)

    # UPDATE
    obj.group_name = group_name
    obj.code = code
    obj.description = description
    obj.is_active = is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Item Group updated successfully"
    })


# TOGGLE ACTIVE STATUS
@api_view(['PATCH'])
def toggle_item_group(request, pk):
    try:
        obj = ItemGroup.objects.get(id=pk)
    except ItemGroup.DoesNotExist:
        return Response({"status": False, "message": "Item Group not found"}, status=404)

    obj.is_active = not obj.is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Status updated successfully",
        "is_active": obj.is_active
    })
#Item_sub_groups - This file defines the API views for managing item sub groups in the purchase_master module of the MASTERS app, including path-based views for listing item sub groups with pagination and search functionality, creating new item sub groups, updating existing item sub groups, and toggling item sub group status. The views handle HTTP requests and return appropriate responses based on the operations performed on the SubGroup model, allowing for organized management of item sub group data within the system.
# LIST
@api_view(['GET'])
def sub_group_list(request):
    search = request.GET.get('search', '')
    group_id = request.GET.get('group_id')

    queryset = SubGroup.objects.select_related('group').all()

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    if search:
        queryset = queryset.filter(sub_group_name__icontains=search)

    data = []
    for obj in queryset:
        data.append({
            "id": obj.pk,
            "sub_group_name": obj.sub_group_name,
            "sub_group_code": obj.sub_group_code,
            "group_name": obj.group.group_name,
            "group_code": obj.group.code,
            "group_id": obj.group.pk,
            "description": obj.description,
            "is_active": obj.is_active
        })

    return Response({
        "status": True,
        "data": data
    })


# CREATE
@api_view(['POST'])
def create_sub_group(request):
    group_id = request.data.get('group_id')
    name = request.data.get('sub_group_name')
    code = request.data.get('sub_group_code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    if not group_id:
        return Response({"status": False, "message": "Group is required"}, status=400)

    if not name:
        return Response({"status": False, "message": "Sub group name is required"}, status=400)

    if not code:
        return Response({"status": False, "message": "Sub group code is required"}, status=400)

    try:
        group = ItemGroup.objects.get(id=group_id)
    except ItemGroup.DoesNotExist:
        return Response({"status": False, "message": "Invalid group"}, status=400)

    if SubGroup.objects.filter(sub_group_name=name, group=group).exists():
        return Response({"status": False, "message": "Sub group already exists in this group"}, status=400)

    if SubGroup.objects.filter(sub_group_code=code).exists():
        return Response({"status": False, "message": "Sub group code already exists"}, status=400)

    SubGroup.objects.create(
        group=group,
        sub_group_name=name,
        sub_group_code=code,
        description=description,
        is_active=is_active
    )

    return Response({
        "status": True,
        "message": "Sub Group created successfully"
    })


# UPDATE
@api_view(['PUT'])
def update_sub_group(request, pk):
    try:
        obj = SubGroup.objects.get(id=pk)
    except SubGroup.DoesNotExist:
        return Response({"status": False, "message": "Sub group not found"}, status=404)

    group_id = request.data.get('group_id')
    name = request.data.get('sub_group_name')
    code = request.data.get('sub_group_code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    if not group_id:
        return Response({"status": False, "message": "Group is required"}, status=400)

    if not name:
        return Response({"status": False, "message": "Sub group name is required"}, status=400)

    if not code:
        return Response({"status": False, "message": "Sub group code is required"}, status=400)

    try:
        group = ItemGroup.objects.get(id=group_id)
    except ItemGroup.DoesNotExist:
        return Response({"status": False, "message": "Invalid group"}, status=400)

    if SubGroup.objects.exclude(id=pk).filter(sub_group_name=name, group=group).exists():
        return Response({"status": False, "message": "Sub group already exists in this group"}, status=400)

    if SubGroup.objects.exclude(id=pk).filter(sub_group_code=code).exists():
        return Response({"status": False, "message": "Sub group code already exists"}, status=400)

    obj.group = group
    obj.sub_group_name = name
    obj.sub_group_code = code
    obj.description = description
    obj.is_active = is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Sub Group updated successfully"
    })


# TOGGLE
@api_view(['PATCH'])
def toggle_sub_group(request, pk):
    try:
        obj = SubGroup.objects.get(id=pk)
    except SubGroup.DoesNotExist:
        return Response({"status": False, "message": "Sub group not found"}, status=404)

    obj.is_active = not obj.is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Status updated",
        "is_active": obj.is_active
    })


# DROPDOWN (for create page)
@api_view(['GET'])
def sub_group_group_dropdown(request):
    groups = ItemGroup.objects.filter(is_active=True).values('id', 'group_name', 'code')

    return Response({
        "status": True,
        "data": list(groups)
    })
# Item_category's - This file defines the API views for managing item categories in the purchase_master module of the MASTERS app, including path-based views for listing item categories with pagination and search functionality, creating new item categories, updating existing item categories, and toggling item category status. The views handle HTTP requests and return appropriate responses based on the operations performed on the Category model, allowing for organized management of item category data within the system. Additionally, there are views for retrieving dropdown data for groups and sub groups to facilitate category creation and updates.
# LIST
@api_view(['GET'])
def category_list(request):
    search = request.GET.get('search', '')
    group_id = request.GET.get('group_id')
    sub_group_id = request.GET.get('sub_group_id')

    queryset = Category.objects.select_related('group', 'sub_group').all()

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    if sub_group_id:
        queryset = queryset.filter(sub_group_id=sub_group_id)

    if search:
        queryset = queryset.filter(category_name__icontains=search)

    data = []
    for obj in queryset:
        data.append({
            "id": obj.pk,
            "category_name": obj.category_name,
            "category_code": obj.category_code,
            "group_name": obj.group.group_name,
            "group_code": obj.group.code,
            "sub_group_name": obj.sub_group.sub_group_name,
            "sub_group_code": obj.sub_group.sub_group_code,
            "description": obj.description,
            "is_active": obj.is_active
        })

    return Response({
        "status": True,
        "data": data
    })


# CREATE
@api_view(['POST'])
def create_category(request):
    group_id = request.data.get('group_id')
    sub_group_id = request.data.get('sub_group_id')
    name = request.data.get('category_name')
    code = request.data.get('category_code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    if not group_id:
        return Response({"status": False, "message": "Group is required"}, status=400)

    if not sub_group_id:
        return Response({"status": False, "message": "Sub group is required"}, status=400)

    if not name:
        return Response({"status": False, "message": "Category name is required"}, status=400)

    if not code:
        return Response({"status": False, "message": "Category code is required"}, status=400)

    try:
        group = ItemGroup.objects.get(id=group_id)
    except ItemGroup.DoesNotExist:
        return Response({"status": False, "message": "Invalid group"}, status=400)

    try:
        sub_group = SubGroup.objects.get(id=sub_group_id, group=group)
    except SubGroup.DoesNotExist:
        return Response({"status": False, "message": "Invalid sub group for selected group"}, status=400)

    if Category.objects.filter(category_name=name, sub_group=sub_group).exists():
        return Response({"status": False, "message": "Category already exists in this sub group"}, status=400)

    if Category.objects.filter(category_code=code).exists():
        return Response({"status": False, "message": "Category code already exists"}, status=400)

    Category.objects.create(
        group=group,
        sub_group=sub_group,
        category_name=name,
        category_code=code,
        description=description,
        is_active=is_active
    )

    return Response({
        "status": True,
        "message": "Category created successfully"
    })


# UPDATE
@api_view(['PUT'])
def update_category(request, pk):
    try:
        obj = Category.objects.get(id=pk)
    except Category.DoesNotExist:
        return Response({"status": False, "message": "Category not found"}, status=404)

    group_id = request.data.get('group_id')
    sub_group_id = request.data.get('sub_group_id')
    name = request.data.get('category_name')
    code = request.data.get('category_code')
    description = request.data.get('description', '')
    is_active = request.data.get('is_active', True)

    if not group_id or not sub_group_id:
        return Response({"status": False, "message": "Group & Sub group required"}, status=400)

    try:
        group = ItemGroup.objects.get(id=group_id)
        sub_group = SubGroup.objects.get(id=sub_group_id, group=group)
    except (ItemGroup.DoesNotExist, SubGroup.DoesNotExist):
        return Response({"status": False, "message": "Invalid group/sub group"}, status=400)

    if Category.objects.exclude(id=pk).filter(category_name=name, sub_group=sub_group).exists():
        return Response({"status": False, "message": "Category already exists"}, status=400)

    if Category.objects.exclude(id=pk).filter(category_code=code).exists():
        return Response({"status": False, "message": "Category code already exists"}, status=400)

    obj.group = group
    obj.sub_group = sub_group
    obj.category_name = name
    obj.category_code = code
    obj.description = description
    obj.is_active = is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Category updated successfully"
    })


# TOGGLE
@api_view(['PATCH'])
def toggle_category(request, pk):
    try:
        obj = Category.objects.get(id=pk)
    except Category.DoesNotExist:
        return Response({"status": False, "message": "Category not found"}, status=404)

    obj.is_active = not obj.is_active
    obj.save()

    return Response({
        "status": True,
        "message": "Status updated",
        "is_active": obj.is_active
    })


# GROUP DROPDOWN
@api_view(['GET'])
def category_group_dropdown(request):
    data = ItemGroup.objects.filter(is_active=True).values('id', 'group_name', 'code')
    return Response({"status": True, "data": list(data)})


# SUB GROUP DROPDOWN (based on group)
@api_view(['GET'])
def category_sub_group_dropdown(request):
    group_id = request.GET.get('group_id')

    queryset = SubGroup.objects.filter(is_active=True)

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    data = queryset.values('id', 'sub_group_name', 'sub_group_code')

    return Response({
        "status": True,
        "data": list(data)
    })
# Item_names/code - This file defines the API views for managing item names and codes in the purchase_master module of the MASTERS app, including path-based views for listing items with pagination and search functionality, creating new items, updating existing items, and toggling item status. The views handle HTTP requests and return appropriate responses based on the operations performed on the ItemMaster model, allowing for organized management of item data within the system. Additionally, there are views for retrieving dropdown data for groups, sub groups, and categories to facilitate item creation and updates.
# LIST
@api_view(['GET'])
def item_list_legacy(request):
    group_id = request.GET.get('group_id')
    sub_group_id = request.GET.get('sub_group_id')
    category_id = request.GET.get('category_id')
    search = request.GET.get('search', '')

    queryset = ItemMaster.objects.select_related(
        'group', 'sub_group', 'category', 'unit'
    ).all()

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    if sub_group_id:
        queryset = queryset.filter(sub_group_id=sub_group_id)

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if search:
        queryset = queryset.filter(item_name__icontains=search)

    data = []
    for obj in queryset:
        data.append({
            "id": obj.pk,
            "item_name": obj.item_name,
            "item_code": obj.item_code,
            "group_name": obj.group.group_name,
            "sub_group_name": obj.sub_group.sub_group_name,
            "category_name": obj.category.category_name,
            "unit_name": obj.unit.unit_name if obj.unit else None,
            "description": obj.description,
            "is_active": obj.is_active
        })

    return Response({"status": True, "data": data})


# CREATE
@api_view(['POST'])
def create_item_legacy(request):
    group_id = request.data.get('group_id')
    sub_group_id = request.data.get('sub_group_id')
    category_id = request.data.get('category_id')
    unit_id = request.data.get('unit_id')
    item_name = request.data.get('item_name')

    if not all([group_id, sub_group_id, category_id, item_name]):
        return Response({"status": False, "message": "Required fields missing"}, status=400)

    group = ItemGroup.objects.get(id=group_id)
    sub_group = SubGroup.objects.get(id=sub_group_id, group=group)
    category = Category.objects.get(id=category_id, sub_group=sub_group)
    unit = UnitMaster.objects.get(id=unit_id) if unit_id else None

    # 🔥 AUTO CODE
    item_code = generate_item_code(group, sub_group, category)

    ItemMaster.objects.create(
        group=group,
        sub_group=sub_group,
        category=category,
        unit=unit,
        item_name=item_name,
        item_code=item_code,
        reorder_level=request.data.get('reorder_level', 0),
        reorder_qty=request.data.get('reorder_qty', 0),
        purchase_lead_time=request.data.get('purchase_lead_time', 0),
        unit_price=request.data.get('unit_price', 0),
        hsn_code=request.data.get('hsn_code'),
        tolerance=request.data.get('tolerance', 0),
        tax=request.data.get('tax', 0),
        description=request.data.get('description'),
        is_active=request.data.get('is_active', True)
    )

    return Response({
        "status": True,
        "message": "Item created successfully",
        "item_code": item_code
    })


# TOGGLE
@api_view(['PATCH'])
def toggle_item_legacy(request, pk):
    obj = ItemMaster.objects.get(id=pk)
    obj.is_active = not obj.is_active
    obj.save()

    return Response({"status": True})

def generate_item_code(group, sub_group, category):
    prefix = f"{group.code}-{sub_group.sub_group_code}-{category.category_code}"

    last_item = ItemMaster.objects.filter(
        group=group,
        sub_group=sub_group,
        category=category
    ).order_by('-id').first()

    if last_item:
        last_number = int(last_item.item_code.split('-')[-1])
        new_number = last_number + 1
    else:
        new_number = 1

    return f"{prefix}-{str(new_number).zfill(5)}"

# LIST
@api_view(['GET'])
def item_list(request):
    group_id = request.GET.get('group_id')
    sub_group_id = request.GET.get('sub_group_id')
    category_id = request.GET.get('category_id')
    search = request.GET.get('search', '')

    queryset = ItemMaster.objects.select_related(
        'group', 'sub_group', 'category', 'unit'
    ).all()

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    if sub_group_id:
        queryset = queryset.filter(sub_group_id=sub_group_id)

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    if search:
        queryset = queryset.filter(item_name__icontains=search)

    data = []
    for obj in queryset:
        data.append({
            "id": obj.pk,
            "item_name": obj.item_name,
            "item_code": obj.item_code,
            "group_name": obj.group.group_name,
            "sub_group_name": obj.sub_group.sub_group_name,
            "category_name": obj.category.category_name,
            "description": obj.description,
            "is_active": obj.is_active
        })

    return Response({"status": True, "data": data})


# CREATE
@api_view(['POST'])
def create_item(request):
    group_id = request.data.get('group_id')
    sub_group_id = request.data.get('sub_group_id')
    category_id = request.data.get('category_id')
    unit_id = request.data.get('unit_id')
    item_name = request.data.get('item_name')

    if not all([group_id, sub_group_id, category_id, item_name]):
        return Response({"status": False, "message": "Required fields missing"}, status=400)

    group = ItemGroup.objects.get(id=group_id)
    sub_group = SubGroup.objects.get(id=sub_group_id, group=group)
    category = Category.objects.get(id=category_id, sub_group=sub_group)
    unit = UnitMaster.objects.get(id=unit_id) if unit_id else None

    # 🔥 AUTO CODE
    item_code = generate_item_code(group, sub_group, category)

    ItemMaster.objects.create(
        group=group,
        sub_group=sub_group,
        category=category,
        unit=unit,
        item_name=item_name,
        item_code=item_code,
        reorder_level=request.data.get('reorder_level', 0),
        reorder_qty=request.data.get('reorder_qty', 0),
        purchase_lead_time=request.data.get('purchase_lead_time', 0),
        unit_price=request.data.get('unit_price', 0),
        hsn_code=request.data.get('hsn_code'),
        tolerance=request.data.get('tolerance', 0),
        tax=request.data.get('tax', 0),
        description=request.data.get('description'),
        is_active=request.data.get('is_active', True)
    )

    return Response({
        "status": True,
        "message": "Item created successfully",
        "item_code": item_code
    })


# TOGGLE
@api_view(['PATCH'])
def toggle_item(request, pk):
    obj = ItemMaster.objects.get(id=pk)
    obj.is_active = not obj.is_active
    obj.save()

    return Response({"status": True})
# Product creations - This file defines the API views for managing product creation in the purchase_master module of the MASTERS app, including path-based views for listing products with pagination and search functionality, creating new products, updating existing products, and toggling product status. The views handle HTTP requests and return appropriate responses based on the operations performed on the ProductCreation model, allowing for organized management of product data within the system. Additionally, there are views for retrieving dropdown data for companies, groups, and sub groups to facilitate product creation and updates.
# LIST
@api_view(['GET'])
def product_list(request):
    group_id = request.GET.get('group_id')
    sub_group_id = request.GET.get('sub_group_id')
    company_id = request.GET.get('company_id')
    search = request.GET.get('search', '')

    queryset = ProductCreation.objects.select_related(
        'company', 'group', 'sub_group'
    ).all()

    if group_id:
        queryset = queryset.filter(group_id=group_id)

    if sub_group_id:
        queryset = queryset.filter(sub_group_id=sub_group_id)

    if company_id:
        queryset = queryset.filter(company_id=company_id)

    if search:
        queryset = queryset.filter(product_name__icontains=search)

    data = []
    for obj in queryset:
        data.append({
            "id": obj.pk,
            "company_name": obj.company.name if obj.company else None,
            "group_name": obj.group.group_name if obj.group else None,
            "sub_group_name": obj.sub_group.sub_group_name if obj.sub_group else None,
            "product_name": obj.product_name,
            "description": obj.description,
            "is_active": obj.is_active
        })

    return Response({"status": True, "data": data})


# CREATE
@api_view(['POST'])
def create_product(request):
    company_id = request.data.get('company_id')
    group_id = request.data.get('group_id')
    sub_group_id = request.data.get('sub_group_id')
    product_name = request.data.get('product_name')

    if not company_id:
        return Response({"status": False, "message": "Company required"}, status=400)

    if not product_name:
        return Response({"status": False, "message": "Product name required"}, status=400)

    company = Company.objects.get(id=company_id)
    group = ItemGroup.objects.get(id=group_id) if group_id else None
    sub_group = SubGroup.objects.get(id=sub_group_id) if sub_group_id else None

    if ProductCreation.objects.filter(product_name=product_name, company=company).exists():
        return Response({"status": False, "message": "Product already exists"}, status=400)

    ProductCreation.objects.create(
        company=company,
        group=group,
        sub_group=sub_group,
        product_name=product_name,
        description=request.data.get('description'),
        is_active=request.data.get('is_active', True)
    )

    return Response({"status": True, "message": "Product created successfully"})


# UPDATE
@api_view(['PUT'])
def update_product(request, pk):
    obj = ProductCreation.objects.get(id=pk)

    obj.product_name = request.data.get('product_name')
    obj.description = request.data.get('description')
    obj.is_active = request.data.get('is_active', True)

    obj.save()

    return Response({"status": True, "message": "Updated successfully"})


# TOGGLE
@api_view(['PATCH'])
def toggle_product(request, pk):
    obj = ProductCreation.objects.get(id=pk)
    obj.is_active = not obj.is_active
    obj.save()

    return Response({"status": True})


# DROPDOWNS

@api_view(['GET'])
def company_dropdown(request):
    data = [{"id": obj.pk, "company_name": obj.name} for obj in Company.objects.all()]
    return Response({"status": True, "data": data})


@api_view(['GET'])
def group_dropdown(request):
    data = ItemGroup.objects.filter(is_active=True).values('id', 'group_name', 'code')
    return Response({"status": True, "data": list(data)})


@api_view(['GET'])
def sub_group_dropdown(request):
    group_id = request.GET.get('group_id')

    queryset = SubGroup.objects.filter(is_active=True)
    if group_id:
        queryset = queryset.filter(group_id=group_id)

    data = queryset.values('id', 'sub_group_name', 'sub_group_code')

    return Response({"status": True, "data": list(data)})
# Standard BOM - This file defines the API views for managing standard bills of materials (BOM) in the production module of the MASTERS app, including path-based views for listing BOMs with pagination and search functionality, creating new BOMs with multiple items, viewing BOM details, and updating existing BOMs. The views handle HTTP requests and return appropriate responses based on the operations performed on the StandardBOM and StandardBOMItem models, allowing for organized management of BOM data within the system. Additionally, there are validations in place to ensure data integrity during BOM creation and updates.
# LIST ALL BOMS
@api_view(['GET'])
def bom_list(request):
    """Get all BOM records with product details"""
    try:
        queryset = StandardBOM.objects.select_related('product').all()
        serializer = StandardBOMSerializer(queryset, many=True)
        return Response({
            "status": True,
            "message": "BOMs fetched successfully",
            "data": serializer.data,
            "count": queryset.count()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# CREATE BOM WITH VALIDATION
@api_view(['POST'])
def create_bom(request):
    """Create a new BOM with multiple items
    
    Expected JSON:
    {
        "product_id": 1,
        "items": [
            {
                "item_id": 1,
                "qty": 5,
                "unit": "PCS",
                "remarks": "Optional remarks",
                "is_active": true
            }
        ]
    }
    """
    try:
        # Validate input data
        serializer = CreateBOMSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "status": False,
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated_data = cast(dict[str, Any], serializer.validated_data)
        product_id = cast(int, validated_data.get('product_id'))
        items = cast(list[dict[str, Any]], validated_data.get('items', []))

        # Get product
        try:
            product = ProductCreation.objects.get(id=product_id)
        except ProductCreation.DoesNotExist:
            return Response({
                "status": False,
                "message": f"Product with ID {product_id} not found"
            }, status=status.HTTP_404_NOT_FOUND)

        # Create BOM header
        bom = StandardBOM.objects.create(product=product)

        # Create BOM items
        for row in items:
            try:
                item = ItemMaster.objects.get(id=row.get('item_id'))
                StandardBOMItem.objects.create(
                    bom=bom,
                    item=item,
                    qty=row.get('qty'),
                    unit=row.get('unit'),
                    remarks=row.get('remarks', ''),
                    is_active=row.get('is_active', True)
                )
            except ItemMaster.DoesNotExist:
                bom.delete()  # Rollback if item not found
                return Response({
                    "status": False,
                    "message": f"Item with ID {row.get('item_id')} not found"
                }, status=status.HTTP_404_NOT_FOUND)

        # Return created BOM with details
        bom_serializer = StandardBOMSerializer(bom)
        return Response({
            "status": True,
            "message": "BOM created successfully",
            "data": bom_serializer.data
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# VIEW BOM DETAILS
@api_view(['GET'])
def view_bom(request, pk):
    """Get BOM details by ID"""
    try:
        bom = StandardBOM.objects.get(id=pk)
        serializer = StandardBOMSerializer(bom)
        return Response({
            "status": True,
            "message": "BOM details fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except StandardBOM.DoesNotExist:
        return Response({
            "status": False,
            "message": f"BOM with ID {pk} not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# UPDATE BOM ITEMS
@api_view(['PUT'])
def update_bom(request, pk):
    """Update BOM items"""
    try:
        bom = StandardBOM.objects.get(id=pk)
        items = cast(list[dict[str, Any]], request.data.get('items', []))

        if not items:
            return Response({
                "status": False,
                "message": "Items are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Delete existing items
        StandardBOMItem.objects.filter(bom=bom).delete()

        # Create new items
        for row in items:
            try:
                item = ItemMaster.objects.get(id=row.get('item_id'))
                StandardBOMItem.objects.create(
                    bom=bom,
                    item=item,
                    qty=row.get('qty'),
                    unit=row.get('unit'),
                    remarks=row.get('remarks', ''),
                    is_active=row.get('is_active', True)
                )
            except ItemMaster.DoesNotExist:
                return Response({
                    "status": False,
                    "message": f"Item with ID {row.get('item_id')} not found"
                }, status=status.HTTP_404_NOT_FOUND)

        bom_serializer = StandardBOMSerializer(bom)
        return Response({
            "status": True,
            "message": "BOM updated successfully",
            "data": bom_serializer.data
        }, status=status.HTTP_200_OK)

    except StandardBOM.DoesNotExist:
        return Response({
            "status": False,
            "message": f"BOM with ID {pk} not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# DELETE BOM
@api_view(['DELETE'])
def delete_bom(request, pk):
    """Delete BOM by ID"""
    try:
        bom = StandardBOM.objects.get(id=pk)
        bom_name = f"{bom.product.product_name}"
        bom.delete()
        return Response({
            "status": True,
            "message": f"BOM '{bom_name}' deleted successfully"
        }, status=status.HTTP_200_OK)
    except StandardBOM.DoesNotExist:
        return Response({
            "status": False,
            "message": f"BOM with ID {pk} not found"
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PRODUCT DROPDOWN
@api_view(['GET'])
def product_dropdown(request):
    """Get all active products for dropdown"""
    try:
        data = ProductCreation.objects.filter(is_active=True).values('id', 'product_name')
        return Response({
            "status": True,
            "message": "Products fetched successfully",
            "data": list(data)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ITEM DROPDOWN
@api_view(['GET'])
def item_dropdown(request):
    """Get all active items for dropdown"""
    try:
        data = ItemMaster.objects.filter(is_active=True).values('id', 'item_name', 'item_code')
        return Response({
            "status": True,
            "message": "Items fetched successfully",
            "data": list(data)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
