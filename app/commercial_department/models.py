from django.db import models
from core.models import BaseModel
from app.project_admin.models import Project
from app.account.models import UserAccount


class Variation(BaseModel):

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="variations"
    )
    created_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, related_name="created_variations"
    )

    vo_number = models.CharField(max_length=20, unique=True, blank=True)
    variation_sheet_number = models.CharField(max_length=10, blank=True, default="")
    site_instruction_no = models.CharField(max_length=100, blank=True, default="")
    attention_of = models.CharField(max_length=200, blank=True, default="")
    description_of_works = models.TextField(blank=True, default="")
    comments = models.TextField(blank=True, default="")

    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Approval
    approval_status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    approved_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_variations"
    )

    # Client
    submitted_to_client = models.BooleanField(default=False)
    signed_by_client = models.BooleanField(default=False)
    assigned_users = models.ManyToManyField(
        UserAccount, related_name="assigned_variations", blank=True
    )

    # Monthly Application specific fields
    valuation_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    percent_claimed = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_claimed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    client_certified_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    corresponding_notice_no = models.CharField(max_length=100, blank=True, default="")
    client_qs_comment = models.TextField(blank=True, default="")

    date = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "variations"
        ordering = ["-date", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.vo_number:
            # Auto-generate VO number based on count
            count = Variation.objects.count() + 1
            self.vo_number = f"VO-{str(count).zfill(3)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vo_number} - {self.project.project_name}"

    @property
    def difference(self):
        return self.amount_claimed - self.client_certified_amount


class VariationLine(BaseModel):
    variation = models.ForeignKey(
        Variation, on_delete=models.CASCADE, related_name="lines"
    )
    site_instruction = models.CharField(max_length=255, blank=True, default="")
    work_area = models.CharField(max_length=255, blank=True, default="")
    work_section = models.CharField(max_length=255, blank=True, default="")
    labour = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    labour_target = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    material = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    class Meta:
        db_table = "variation_lines"

    @property
    def line_total(self):
        return (self.labour + self.material) * self.qty

    def __str__(self):
        return f"Line for {self.variation.vo_number}"


class MonthlyApplication(BaseModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="monthly_applications"
    )
    application_number = models.PositiveIntegerField()
    date = models.DateField()
    ref_no = models.CharField(max_length=100, blank=True, default="")
    
    retention_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    
    # Financial snapshots
    contract_works_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variations_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_claimed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    client_certified_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        db_table = "monthly_applications"
        unique_together = ('project', 'application_number')
        ordering = ["-application_number"]

    def __str__(self):
        return f"{self.project.project_name} - App {self.application_number}"
