from django.contrib import admin
from .models import SupplierInvitation, SupplierInvoice

@admin.register(SupplierInvitation)
class SupplierInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "company", "supplier_name", "status", "expires_at", "created_at")
    list_filter = ("status", "company")
    search_fields = ("email", "supplier_name", "token")

@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "company", "company_supplier", "amount", "invoice_date", "status")
    list_filter = ("status", "company")
    search_fields = ("invoice_number", "company_supplier__supplier__company_name")
