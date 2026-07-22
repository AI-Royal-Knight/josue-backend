from django.db import models
from core.models import BaseModel
from app.project_admin.models import Project, ProjectFolder, ProjectSubfolder
from app.account.models import CompanySupplier, UserAccount

class PurchaseOrder(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="purchase_orders")
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date_created = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "purchase_orders"

    def __str__(self):
        return f"PO for {self.project.project_name} - {self.total_value}"


class POCallOff(BaseModel):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="call_offs")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "po_call_offs"

    def __str__(self):
        return f"Call Off for {self.po} - {self.amount}"


class Quotation(BaseModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    quote_ref = models.CharField(max_length=50, unique=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="quotations")
    main_folder = models.ForeignKey(ProjectFolder, on_delete=models.SET_NULL, null=True, blank=True)
    sub_folder = models.ForeignKey(ProjectSubfolder, on_delete=models.SET_NULL, null=True, blank=True)
    variation_ref = models.CharField(max_length=100, null=True, blank=True)
    
    supplier = models.ForeignKey(CompanySupplier, on_delete=models.CASCADE, related_name="quotations")
    supplier_email = models.CharField(max_length=255, blank=True, null=True)
    
    date_of_quote = models.DateField(auto_now_add=True)
    quote_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    po_created = models.BooleanField(default=False)
    date_po_created = models.DateField(null=True, blank=True)
    
    procurement_comments = models.TextField(blank=True, null=True)
    finance_comments = models.TextField(blank=True, null=True)
    commercial_comments = models.TextField(blank=True, null=True)
    quote_approval_reasons = models.TextField(blank=True, null=True)
    requote_comments = models.TextField(blank=True, null=True)

    paid = models.BooleanField(default=False)
    paid_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name="paid_quotations")
    date_scheduled = models.DateField(null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name="created_quotations")
    
    supplier_token = models.CharField(max_length=100, blank=True, null=True)
    supplier_quote_pdf = models.FileField(upload_to="supplier_quotes/", null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.quote_ref:
            import uuid
            from django.utils import timezone
            short_id = str(uuid.uuid4()).split('-')[0].upper()
            self.quote_ref = f"QR-{timezone.now().year}-{short_id}"
        
        if not self.supplier_token:
            import uuid
            self.supplier_token = str(uuid.uuid4())
            
        super().save(*args, **kwargs)

    class Meta:
        db_table = "quotations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quote_ref} - {self.project.project_name}"


class QuotationLineItem(BaseModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="line_items")
    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    per = models.CharField(max_length=50, blank=True, null=True)
    each = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    comments = models.TextField(blank=True, null=True)
    supplier_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Call Off List specific fields
    management_approved = models.BooleanField(default=False)
    management_approved_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "quotation_line_items"

    def __str__(self):
        return f"{self.description} for {self.quotation.quote_ref}"


class QuotationHistory(BaseModel):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="history")
    message = models.TextField(blank=True, null=True)
    previous_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    previous_pdf = models.FileField(upload_to="supplier_quotes/history/", null=True, blank=True)
    previous_line_items = models.JSONField(default=list)
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quotation_history"
        ordering = ["-date_recorded"]

    def __str__(self):
        return f"History for {self.quotation.quote_ref} on {self.date_recorded}"


class OrderLineCallOff(BaseModel):
    line_item = models.ForeignKey(QuotationLineItem, on_delete=models.CASCADE, related_name="call_offs")
    call_off_ref = models.CharField(max_length=100)
    date = models.DateField(auto_now_add=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=15, decimal_places=2)
    expected_delivery_date = models.DateField(null=True, blank=True)
    called_off_by = models.ForeignKey(UserAccount, related_name="called_off_items", on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(UserAccount, related_name="approved_call_offs", on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        if not self.call_off_ref:
            import uuid
            self.call_off_ref = f"CO-{str(uuid.uuid4()).split('-')[0].upper()}"
        super().save(*args, **kwargs)

    class Meta:
        db_table = "order_line_call_offs"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.call_off_ref} for {self.line_item.description}"
