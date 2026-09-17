from django.db import models
from django.utils import timezone
from core.models import BaseModel


class SupplierInvitation(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    company = models.ForeignKey(
        'account.Company',
        on_delete=models.CASCADE,
        related_name="supplier_invitations"
    )
    company_supplier = models.ForeignKey(
        'account.CompanySupplier',
        on_delete=models.CASCADE,
        related_name="invitations"
    )
    email = models.EmailField()
    supplier_name = models.CharField(max_length=255, blank=True, default="")
    invited_by = models.ForeignKey(
        'account.UserAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_supplier_invitations"
    )

    token = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    class Meta:
        db_table = "supplier_invitations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Supplier Invitation for {self.email} -> {self.company.company_name} ({self.status})"


class SupplierInvoice(BaseModel):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        PROCESSING = "processing", "Processing"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"

    company = models.ForeignKey(
        'account.Company',
        on_delete=models.CASCADE,
        related_name="supplier_invoices"
    )
    company_supplier = models.ForeignKey(
        'account.CompanySupplier',
        on_delete=models.CASCADE,
        related_name="invoices"
    )
    submitted_by = models.ForeignKey(
        'account.UserAccount',
        on_delete=models.CASCADE,
        related_name="submitted_supplier_invoices"
    )

    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="supplier_invoices/", null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED
    )

    # PO / Call-Off linkage
    po_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="The PO (Quotation) reference this invoice is against, e.g. QR-2026-ABC123"
    )
    call_off = models.ForeignKey(
        'procurement_department.OrderLineCallOff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_invoices',
        help_text="FK to the specific call-off this invoice covers"
    )
    call_off_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Call-off reference string, e.g. CO-XXXXXX (mirrors call_off.call_off_ref)"
    )

    procurement_comments = models.TextField(blank=True, default="")
    processed_by = models.ForeignKey(
        'account.UserAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_supplier_invoices"
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "supplier_invoices"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.company_supplier.supplier.company_name} ({self.status})"
