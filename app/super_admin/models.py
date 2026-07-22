from django.db import models

from core.models import BaseModel
from app.account.models import Company, UserAccount

import uuid

class RecentActivity(BaseModel):
    activity_name = models.CharField()
    activity_time = models.DateTimeField(auto_now_add=True)

class CompanyInvitation(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="invitations"
    )

    user = models.OneToOneField(
        UserAccount,
        on_delete=models.CASCADE
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    accepted = models.BooleanField(
        default=False
    )

    expires_at = models.DateTimeField()

    accepted_at = models.DateTimeField(
        null=True,
        blank=True
    )

class MonthlyInvoice(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="monthly_invoices"
    )
    year = models.IntegerField()
    month = models.IntegerField()  # 1-12
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_sent = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)

    class Meta:
        unique_together = ('company', 'year', 'month')

