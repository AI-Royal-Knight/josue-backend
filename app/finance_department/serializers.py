from rest_framework import serializers
from django.db.models import Sum
from app.procurement_department.models import Quotation


class FinanceSupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.project_name', read_only=True)
    user_name = serializers.SerializerMethodField()
    paid_by_name = serializers.SerializerMethodField()
    sort_code = serializers.SerializerMethodField()
    account_number = serializers.SerializerMethodField()

    credit_limit = serializers.SerializerMethodField()
    eom_payment_terms = serializers.SerializerMethodField()
    month_credit_used = serializers.SerializerMethodField()
    available_credit = serializers.SerializerMethodField()
    previous_month = serializers.SerializerMethodField()
    invoice_due_this_month = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = (
            'id', 'quote_ref', 'date_of_quote', 'project_name', 'user_name',
            'sort_code', 'account_number', 'quote_total', 'paid', 'paid_by_name',
            'date_scheduled', 'release_date', 'finance_comments', 'procurement_comments',
            'commercial_comments', 'supplier_name', 'credit_limit', 'eom_payment_terms',
            'month_credit_used', 'available_credit', 'previous_month', 'invoice_due_this_month',
        )

    def get_supplier_name(self, obj):
        if obj.supplier and obj.supplier.supplier:
            return obj.supplier.supplier.company_name
        return None

    def get_user_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name or obj.created_by.email
        return None

    def get_paid_by_name(self, obj):
        if obj.paid_by:
            return obj.paid_by.full_name or obj.paid_by.email
        return None

    def get_sort_code(self, obj):
        if obj.supplier and obj.supplier.supplier:
            return obj.supplier.supplier.sort_code
        return None

    def get_account_number(self, obj):
        if obj.supplier and obj.supplier.supplier:
            return obj.supplier.supplier.account_number
        return None

    def get_credit_limit(self, obj):
        if obj.supplier:
            return float(obj.supplier.credit_limit or 0)
        return 0

    def get_eom_payment_terms(self, obj):
        if obj.supplier:
            return obj.supplier.eom_payment_terms
        return 30

    def get_month_credit_used(self, obj):
        if not obj.supplier:
            return 0
        total = Quotation.objects.filter(
            supplier=obj.supplier,
            paid=False
        ).aggregate(total=Sum('quote_total'))['total']
        return float(total or 0)

    def get_available_credit(self, obj):
        credit_limit = self.get_credit_limit(obj)
        used = self.get_month_credit_used(obj)
        return credit_limit - used

    def get_previous_month(self, obj):
        import datetime
        from django.utils import timezone
        if not obj.supplier:
            return 0
        today = timezone.now().date()
        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - datetime.timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        total = Quotation.objects.filter(
            supplier=obj.supplier,
            date_of_quote__gte=first_day_prev_month,
            date_of_quote__lte=last_day_prev_month,
        ).aggregate(total=Sum('quote_total'))['total']
        return float(total or 0)

    def get_invoice_due_this_month(self, obj):
        import datetime
        from django.utils import timezone
        if not obj.supplier:
            return 0
        today = timezone.now().date()
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)

        total = Quotation.objects.filter(
            supplier=obj.supplier,
            paid=False,
            date_of_quote__gte=first_day,
            date_of_quote__lte=last_day,
        ).aggregate(total=Sum('quote_total'))['total']
        return float(total or 0)
