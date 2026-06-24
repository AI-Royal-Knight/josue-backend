from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

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

