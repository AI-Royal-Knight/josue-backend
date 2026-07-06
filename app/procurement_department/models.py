from django.db import models
from core.models import BaseModel
from app.project_admin.models import Project

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
