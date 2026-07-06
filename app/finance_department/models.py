from django.db import models
from core.models import BaseModel
from app.project_admin.models import Project

class ProformaNR(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="proformas")
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    material_estimate = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date = models.DateField()

    class Meta:
        db_table = "proforma_nrs"

    def __str__(self):
        return f"ProformaNR for {self.project.project_name} - {self.amount}"
