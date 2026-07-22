from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid
from decimal import Decimal
from core.models import BaseModel


class CustomAccountManager(BaseUserManager):

    def normalize_email_strict(self, email: str) -> str:
        return self.normalize_email(email).lower().strip()

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("Email must be provided"))

        email = self.normalize_email_strict(email)

        user = self.model(
            email=email,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault(
            "role",
            UserAccount.Role.SUPER_ADMIN
        )
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("role") != UserAccount.Role.SUPER_ADMIN:
            raise ValueError(
                "Superuser must have role=SUPER_ADMIN"
            )

        if extra_fields.get("is_staff") is not True:
            raise ValueError(
                "Superuser must have is_staff=True"
            )

        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                "Superuser must have is_superuser=True"
            )

        return self.create_user(
            email,
            password,
            **extra_fields
        )


class UserAccount(
    AbstractBaseUser,
    PermissionsMixin,
    BaseModel
):

    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        ADMIN = "admin", "Admin"
        PROJECT_ADMIN = "project_admin", "Project Admin"
        MANAGING_DIRECTOR = "managing_director", "Managing Director"
        PROJECT_DIRECTOR = "project_director", "Project Director"
        PROCUREMENT_DEPARTMENT = "procurement_department", "Procurement Department"
        COMMERCIAL_DEPARTMENT = "commercial_department", "Commercial Department"
        DOCUMENT_CONTROLLER = "document_controller", "Document Controller"
        FINANCE_DEPARTMENT = "finance_department", "Finance Department"
        CONTRACTS_MANAGER = "contracts_manager", "Contracts Manager"
        MANAGERS = "managers", "Managers"
        SUPERVISOR = "supervisor", "Supervisor"
        EMPLOYEE = "employee", "Employee"
        SUPPLIER = "supplier", "Supplier"

    email = models.EmailField(
        _("email address"),
        unique=True,
    )

    backup_email = models.EmailField(
        _("backup email address"),
        blank=True,
        null=True,
    )

    first_name = models.CharField(
        max_length=80
    )

    last_name = models.CharField(
        max_length=80
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.ADMIN,
    )

    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    assigned_projects = models.ManyToManyField(
        'project_admin.Project',
        related_name='assigned_users',
        blank=True
    )

    profile_updated_at = models.DateTimeField(
        blank=True,
        null=True
    )

    is_staff = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    is_banned = models.BooleanField(
        default=False
    )

    date_joined = models.DateTimeField(
        default=timezone.now
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomAccountManager()

    class Meta:
        db_table = "users"

        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["date_joined"]),
        ]

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def save(self, *args, **kwargs):
        if self.email:
            self.email = (
                self.email
                .lower()
                .strip()
            )

        if self.backup_email:
            self.backup_email = (
                self.backup_email
                .lower()
                .strip()
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return (
            f"{self.first_name} {self.last_name}"
        ).strip()

class Company(BaseModel):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    # Company Information
    company_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    company_logo = models.ImageField(
        upload_to="companies/logos/",
        blank=True,
        null=True,
    )

    company_number = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    building_number = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    street = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    town = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    postcode = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    vat_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    utr = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    public_liability_policy = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    public_liability_expiry = models.DateField(
        blank=True,
        null=True,
    )
    public_liability_document = models.FileField(
        upload_to="companies/insurance/",
        blank=True,
        null=True,
    )

    employers_liability_policy = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    employers_liability_expiry = models.DateField(
        blank=True,
        null=True,
    )
    employers_liability_document = models.FileField(
        upload_to="companies/insurance/",
        blank=True,
        null=True,
    )

    # Bank Details
    bank_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    bank_address = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    sort_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    account_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    iban = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    swift_bic = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    # File Upload
    attachment = models.FileField(
        upload_to="companies/files/",
        blank=True,
        null=True,
    )

    # Statistics
    user = models.PositiveIntegerField(
        default=0,
    )

    projects = models.PositiveIntegerField(
        default=0,
    )

    # Subscription
    activate = models.BooleanField(
        default=False,
    )

    monthly_subscription = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    per_user_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    auto_monthly_inv = models.BooleanField(
        default=False,
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    def __str__(self):
        return self.company_name or f"Company {self.id}"


class RoleAssignment(BaseModel):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.CharField(max_length=50, choices=UserAccount.Role.choices)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="role_assignments")
    project = models.ForeignKey('project_admin.Project', on_delete=models.CASCADE, null=True, blank=True, related_name="role_assignments")

    class Meta:
        db_table = "role_assignments"
        unique_together = ('user', 'role', 'company', 'project')
        
    def __str__(self):
        return f"{self.user.email} - {self.role}"


class UserProfile(BaseModel):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name="profile")
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    
    # Certifications
    cscs_card_no = models.CharField(max_length=50, blank=True, null=True)
    cscs_expiry_date = models.DateField(blank=True, null=True)
    ipaf_certification = models.CharField(max_length=100, blank=True, null=True)
    pasma_certification = models.CharField(max_length=100, blank=True, null=True)
    sssts_smsts = models.CharField(max_length=100, blank=True, null=True)
    profession = models.CharField(max_length=100, blank=True, null=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_number = models.CharField(max_length=50, blank=True, null=True)

    # Tax & Identity
    ni_number = models.CharField(max_length=50, blank=True, null=True)
    utr = models.CharField(max_length=100, blank=True, null=True)
    passport_number = models.CharField(max_length=100, blank=True, null=True)
    passport_expiry_date = models.DateField(blank=True, null=True)
    passport_document = models.FileField(upload_to="profiles/documents/", blank=True, null=True)
    
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_profiles")

    # Application details
    categories = models.TextField(blank=True, null=True)
    insurance_policy = models.CharField(max_length=100, blank=True, null=True)
    employer_liability = models.CharField(max_length=100, blank=True, null=True)
    terms_accepted = models.BooleanField(default=False)
    digital_signature = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile for {self.user.email}"


class SupplierProfile(BaseModel):
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name="supplier_profile")
    company_name = models.CharField(max_length=255)
    sort_code = models.CharField(max_length=20, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        db_table = "supplier_profiles"

    def __str__(self):
        return self.company_name


class CompanySupplier(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    supplier = models.ForeignKey(SupplierProfile, on_delete=models.CASCADE, related_name="companies")
    
    eom_payment_terms = models.PositiveIntegerField(help_text="End of Month payment terms in days", default=30)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        db_table = "company_suppliers"
        unique_together = ('company', 'supplier')

    def __str__(self):
        return f"{self.supplier.company_name} -> {self.company.company_name}"


class Invitation(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    email = models.EmailField()
    role = models.CharField(max_length=50, choices=UserAccount.Role.choices)
    
    # Context
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    project = models.ForeignKey('project_admin.Project', on_delete=models.CASCADE, null=True, blank=True)
    
    invited_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name="sent_invitations")
    
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = "invitations"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Invite {self.email} as {self.role}"


class Notification(BaseModel):
    class Type(models.TextChoices):
        PROJECT_ASSIGNED = "project_assigned", "Project Assigned"
        TASK_ASSIGNED = "task_assigned", "Task Assigned"
        WORK_APPROVED = "work_approved", "Work Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"
        INFO = "info", "Info"

    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    type = models.CharField(max_length=50, choices=Type.choices, default=Type.INFO)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.title}"
