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
