from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GRN
from .serializers import GRNReadSerializer, GRNSerializer


class GRNAPIViewMixin:
    def get_grn_response(self, request):
        try:
            queryset = GRN.objects.all().order_by("-id")

            grn_id = request.query_params.get("id")
            grn_no = request.query_params.get("grn_no")

            if grn_id:
                queryset = queryset.filter(id=grn_id)
            if grn_no:
                queryset = queryset.filter(grn_no=grn_no)

            if (grn_id or grn_no) and not queryset.exists():
                return Response(
                    {
                        "status": "error",
                        "message": "GRN not found",
                        "count": 0,
                        "data": [],
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = GRNReadSerializer(queryset, many=True)

            return Response(
                {
                    "status": "success",
                    "message": "GRN data fetched successfully",
                    "count": queryset.count(),
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "message": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create_grn_response(self, request):
        try:
            data = request.data

            document_details = data.get("document_details", {})
            document_requirement_details = data.get("document_requirement_details", {})
            supplier_details = data.get("supplier_details", {})
            items = data.get("items", [])
            value_details = data.get("value_details", {})

            # Same table → first item only
            first_item = items[0] if items else {}

            grn_no = document_details.get("grn_no")

            # =====================================
            # 1. DUPLICATE RESPONSE
            # =====================================
            if GRN.objects.filter(grn_no=grn_no).exists():
                return Response({
                    "status": "duplicate",
                    "message": "GRN already exists",
                    "grn_no": grn_no
                }, status=status.HTTP_200_OK)

            # =====================================
            # Payload Mapping
            # =====================================
            payload = {
                
                # document_details
                "po_no": document_details.get("po_no"),
                "po_date": document_details.get("po_date"),
                "grn_no": grn_no,
                "grn_date": document_details.get("grn_date"),
                "supplier_invoice_no": document_details.get("supplier_invoice_no"),
                "supplier_invoice_date": document_details.get("supplier_invoice_date"),
                "gateentry_bookno": document_details.get("gateentry_bookno"),
                "gateentry_bookdate": document_details.get("gateentry_bookdate"),
                "tolerance": document_details.get("tolerance"),

                # document_requirement_details
                "req_date": document_requirement_details.get("req_date"),
                "req_person_name": document_requirement_details.get("req_person_name"),
                "req_person_id": document_requirement_details.get("req_person_id"),
                "req_department": document_requirement_details.get("req_department"),
                "req_reason": document_requirement_details.get("req_reason"),

                # supplier_details
                "supplier_id": supplier_details.get("supplier_id"),
                "gstin": supplier_details.get("gstin"),
                "contact_name": supplier_details.get("contact_name"),
                "trade_name": supplier_details.get("trade_name"),
                "contact_type": supplier_details.get("contact_type"),
                "address1": supplier_details.get("address1"),
                "address2": supplier_details.get("address2"),
                "location": supplier_details.get("location"),
                "pincode": supplier_details.get("pincode"),
                "state_name": supplier_details.get("state_name"),
                "state_code": supplier_details.get("state_code"),
                "country": supplier_details.get("country"),
                "person_name": supplier_details.get("person_name"),
                "phone_number": supplier_details.get("phone_number"),
                "email": supplier_details.get("email"),
                "category": supplier_details.get("category"),
                "segment": supplier_details.get("segment"),
                "sub_segment": supplier_details.get("sub_segment"),
                "sales_contact_id": supplier_details.get("sales_contact_id"),
                "currency": supplier_details.get("currency"),

                # first item
                "item_id": first_item.get("item_id"),
                "item_serial_number": first_item.get("item_serial_number"),
                "product_description": first_item.get("product_description"),
                "hsn_code": first_item.get("hsn_code"),
                "total_quantity": first_item.get("total_quantity"),
                "quantity": first_item.get("quantity"),
                "free_quantity": first_item.get("free_quantity"),
                "accepted_qty": first_item.get("accepted_qty"),
                "rejected_qty": first_item.get("rejected_qty"),
                "unit": first_item.get("unit"),
                "unit_price": first_item.get("unit_price"),
                "total_amount": first_item.get("total_amount"),
                "discount": first_item.get("discount"),
                "assessable_value": first_item.get("assessable_value"),
                "gst_rate": first_item.get("gst_rate"),
                "igst_amount": first_item.get("igst_amount"),
                "cgst_amount": first_item.get("cgst_amount"),
                "sgst_amount": first_item.get("sgst_amount"),
                "total_item_value": first_item.get("total_item_value"),

                # value_details
                "freight_charge": value_details.get("freight_charge"),
                "loading_unloading_charge": value_details.get("loading_unloading_charge"),
                "total_before_tax": value_details.get("total_before_tax"),
                "total_tax_amount": value_details.get("total_tax_amount"),
                "total_after_tax": value_details.get("total_after_tax"),
            }

            serializer = GRNSerializer(data=payload)

            # =====================================
            # 2. SUCCESS RESPONSE
            # =====================================
            if serializer.is_valid():
                saved_grn = serializer.save()

                return Response({
                    "status": "success",
                    "message": "GRN stored successfully",
                    "grn_no": saved_grn.grn_no,
                    "grn_id": saved_grn.id
                }, status=status.HTTP_201_CREATED)

            # =====================================
            # 3. ERROR RESPONSE (Validation)
            # =====================================
            return Response({
                "status": "error",
                "message": "Validation failed",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # =====================================
            # 3. ERROR RESPONSE (System Exception)
            # =====================================
            return Response({
                "status": "error",
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GRNCreateAPIView(GRNAPIViewMixin, APIView):
    def get(self, request):
        return self.get_grn_response(request)

    def post(self, request):
        return self.create_grn_response(request)


class GRNViewSet(GRNAPIViewMixin, viewsets.ViewSet):
    def list(self, request):
        return self.get_grn_response(request)

    def create(self, request):
        return self.create_grn_response(request)
