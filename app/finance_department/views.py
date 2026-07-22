from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from app.procurement_department.models import Quotation
from app.account.models import UserAccount, RoleAssignment
from .serializers import FinanceSupplierInvoiceSerializer


class FinanceSupplierInvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = FinanceSupplierInvoiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user

        if user.role == UserAccount.Role.SUPER_ADMIN:
            return Quotation.objects.select_related(
                'project', 'supplier__supplier', 'created_by'
            ).all()

        # Get company from user.company field directly (works for admin and finance_dept)
        company = user.company

        if not company:
            # Fall back to role assignment
            role_assignment = RoleAssignment.objects.filter(
                user=user, role=user.role
            ).first()
            if role_assignment:
                company = role_assignment.company

        if company:
            return Quotation.objects.select_related(
                'project', 'supplier__supplier', 'created_by'
            ).filter(project__company=company)

        return Quotation.objects.none()

    def perform_update(self, serializer):
        instance = self.get_object()
        paid = serializer.validated_data.get('paid', instance.paid)

        if paid and not instance.paid:
            serializer.save(paid_by=self.request.user, release_date=timezone.now().date())
        elif not paid and instance.paid:
            serializer.save(paid_by=None, release_date=None)
        else:
            serializer.save()
