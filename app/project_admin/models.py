from django.db import models
from django.utils import timezone

from core.models import BaseModel
from app.account.models import Company


class Project(BaseModel):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_projects",
        null=True,
        blank=True,
    )

    project_name = models.CharField(max_length=255)

    job_code = models.CharField(max_length=100)

    vat_rate = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    address = models.CharField(max_length=500, blank=True, null=True)

    project_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    material_estimate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    labour_estimate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    prelims_estimate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    start_date = models.DateField(null=True, blank=True)

    completion_date = models.DateField(null=True, blank=True)
    
    monthly_application_date = models.PositiveIntegerField(
        default=1,
        help_text="Day of the month the new application period starts (1-31)."
    )

    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["job_code"]),
            models.Index(fields=["is_completed"]),
        ]

    def __str__(self):
        return f"{self.project_name} ({self.job_code})"

    @property
    def estimate_profit(self):
        """Project Value minus all estimates."""
        return (
            self.project_value
            - self.material_estimate
            - self.labour_estimate
            - self.prelims_estimate
        )

    @property
    def is_overdue(self):
        """True if past completion date and not completed."""
        if self.completion_date and not self.is_completed:
            return timezone.now().date() > self.completion_date
        return False


class ProjectFolder(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=255, help_text="e.g. Electrical, Plumbing")
    is_management = models.BooleanField(default=False, help_text="If this is a special management prelims folder")

    class Meta:
        db_table = "project_folders"

    def __str__(self):
        return f"{self.project.project_name} - {self.name}"


class ProjectSubfolder(BaseModel):
    folder = models.ForeignKey(ProjectFolder, on_delete=models.CASCADE, related_name="subfolders")
    name = models.CharField(max_length=255, help_text="e.g. Work Area")
    project_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    labour_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    rows = models.JSONField(default=list, help_text="Stores the datagrid rows for this subfolder")

    class Meta:
        db_table = "project_subfolders"

    def __str__(self):
        return f"{self.folder.name} -> {self.name}"


class FolderAssignment(BaseModel):
    subfolder = models.ForeignKey(ProjectSubfolder, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="folder_assignments")
    hide_labour_target = models.BooleanField(default=False)
    is_management_assignment = models.BooleanField(default=False)
    employee_labour_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "folder_assignments"

    def __str__(self):
        return f"{self.user.email} assigned to {self.subfolder.name}"


class ApprovalConfiguration(BaseModel):
    class ActionType(models.TextChoices):
        USER_INVOICE = "user_invoice", "User Invoices"
        SUPPLIER_INVOICE = "supplier_invoice", "Supplier Invoices"
        VARIATIONS = "variations", "Variations"
        PURCHASE_ORDER = "purchase_order", "Purchase Orders"
        PROFORMA = "proforma", "Proforma Nr Invoices"
        USER_VARIATIONS_INVOICE = "user_variations_invoice", "User Variations Invoices"
        
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="approval_configs")
    action_type = models.CharField(max_length=50, choices=ActionType.choices)
    
    # E.g. ">£2000" or "ALL"
    condition_value = models.CharField(max_length=50, default="ALL")
    
    # Store roles that need to sign. e.g. "supervisor,contracts_manager" (comma separated)
    required_roles = models.CharField(max_length=255)
    
    toggle_states = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "approval_configurations"

    def __str__(self):
        return f"{self.project.project_name} - {self.action_type} - {self.condition_value}"

class LabourBooking(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="labour_bookings")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="labour_bookings")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "labour_bookings"

class ProjectValueBooking(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_value_bookings")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="project_value_bookings")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "project_value_bookings"

class PlantHireBooking(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="plant_hire_bookings")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "plant_hire_bookings"

class LoadingClearingBooking(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="loading_clearing_bookings")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="loading_clearing_bookings", null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    description = models.TextField(blank=True, null=True)
    attachment_urls = models.JSONField(default=list, blank=True)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "loading_clearing_bookings"

class ManagementPrelimBooking(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="management_prelim_bookings")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "management_prelim_bookings"

class ProformaAccess(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="proforma_accesses")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="proforma_accesses")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "proforma_accesses"
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.email} - Proforma Access on {self.project.project_name}"

class LoadingClearingAccess(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="loading_clearing_accesses")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="loading_clearing_accesses")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "loading_clearing_accesses"
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.email} - Loading & Clearing Access on {self.project.project_name}"

class VariationsAccess(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="variations_accesses")
    user = models.ForeignKey('account.UserAccount', on_delete=models.CASCADE, related_name="variations_accesses")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "variations_accesses"
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.email} - Variations Access on {self.project.project_name}"


class UserInvoice(BaseModel):
    """
    Auto-generated invoice when an employee submits work via the app.
    Sources: variation, labour_target, proforma, loading_clearing
    """

    class SourceType(models.TextChoices):
        VARIATION = "variation", "Variation"
        LABOUR_TARGET = "labour_target", "Labour Target"
        PROFORMA = "proforma", "Proforma NR"
        LOADING_CLEARING = "loading_clearing", "Loading & Clearing"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="user_invoices"
    )
    created_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        related_name="user_invoices",
    )

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    source_id = models.CharField(max_length=100, blank=True, default="")
    variation_sheet_no = models.CharField(max_length=50, blank=True, default="")
    proforma_no = models.CharField(max_length=50, blank=True, default="")
    work_area = models.CharField(max_length=255, blank=True, default="")
    work_section = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField(auto_now_add=True)

    # ── 4-stage management approval chain ─────────────────────
    supervisor_approved = models.BooleanField(default=False)
    supervisor_approved_date = models.DateField(null=True, blank=True)
    supervisor_approved_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervisor_approved_invoices",
    )

    contracts_manager_approved = models.BooleanField(default=False)
    contracts_manager_approved_date = models.DateField(null=True, blank=True)
    contracts_manager_approved_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cm_approved_invoices",
    )

    project_director_approved = models.BooleanField(default=False)
    project_director_approved_date = models.DateField(null=True, blank=True)
    project_director_approved_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pd_approved_invoices",
    )

    managing_director_approved = models.BooleanField(default=False)
    managing_director_approved_date = models.DateField(null=True, blank=True)
    managing_director_approved_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="md_approved_invoices",
    )

    # ── Finance paid status ───────────────────────────────────
    finance_paid = models.BooleanField(default=False)
    finance_paid_date = models.DateField(null=True, blank=True)
    finance_paid_by = models.ForeignKey(
        "account.UserAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_paid_invoices",
    )
    finance_comments = models.TextField(blank=True, default="")
    commercial_comments = models.TextField(blank=True, default="")

    class Meta:
        db_table = "user_invoices"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import datetime
            year = datetime.date.today().year
            count = UserInvoice.objects.filter(
                date__year=year
            ).count() + 1
            self.invoice_number = f"INV-{year}-{str(count).zfill(4)}"
        super().save(*args, **kwargs)

    @property
    def fully_approved(self):
        return (
            self.supervisor_approved
            and self.contracts_manager_approved
            and self.project_director_approved
            and self.managing_director_approved
        )

    def __str__(self):
        return f"{self.invoice_number} - {self.project.project_name}"
