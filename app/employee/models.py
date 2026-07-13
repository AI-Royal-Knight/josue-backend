from django.db import models
from django.utils import timezone
import uuid
from app.account.models import UserAccount, Company
from app.project_admin.models import Project

class AttendanceLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='attendance_logs')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='attendance_logs')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='attendance_logs')
    date = models.DateField(default=timezone.now)
    
    # Check-in Details
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_in_lat = models.FloatField(null=True, blank=True)
    check_in_long = models.FloatField(null=True, blank=True)
    
    # Check-out Details
    check_out_time = models.DateTimeField(null=True, blank=True)
    check_out_lat = models.FloatField(null=True, blank=True)
    check_out_long = models.FloatField(null=True, blank=True)
    
    STATUS_CHOICES = (
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='checked_in')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-check_in_time']
        
    def __str__(self):
        return f"{self.user.email} - {self.project.project_name} - {self.date}"

from core.models import BaseModel

class RFI(BaseModel):
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='rfis')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='rfis_created')
    
    rfi_number = models.CharField(max_length=50, blank=True)
    trade = models.CharField(max_length=100, default='General')
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    document_url = models.URLField(max_length=500, blank=True, null=True)
    
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rfi_number}"

    def save(self, *args, **kwargs):
        if not self.rfi_number:
            # Auto-generate rfi_number scoped to project
            count = RFI.objects.filter(project=self.project).count()
            self.rfi_number = f"#{str(count + 1).zfill(3)}"
            
        if self.status == 'CLOSED' and not self.closed_at:
            self.closed_at = timezone.now()
        elif self.status == 'OPEN':
            self.closed_at = None
            
        super().save(*args, **kwargs)

class RFIMessage(BaseModel):
    rfi = models.ForeignKey(RFI, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='rfi_messages')
    text = models.TextField()
    document_url = models.URLField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.author.email} on {self.rfi.rfi_number}"

class RAMS(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='rams')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='rams_created')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    review_date = models.DateField(null=True, blank=True)
    document_url = models.URLField(max_length=500, blank=True, null=True)
    signed_document_url = models.URLField(max_length=500, blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"RAMS: {self.title} for {self.project.project_name}"

class DailyBriefing(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='daily_briefings')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='daily_briefings_created')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    document_url = models.URLField(max_length=500, blank=True, null=True)
    signed_document_url = models.URLField(max_length=500, blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Briefing: {self.title} for {self.project.project_name}"

class ToolboxTalk(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='toolbox_talks')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='toolbox_talks_created')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    document_url = models.URLField(max_length=500, blank=True, null=True)
    signed_document_url = models.URLField(max_length=500, blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Toolbox: {self.title} for {self.project.project_name}"

class ToDoList(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='todos')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='todos_created')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    assign_user = models.CharField(max_length=255, blank=True, null=True)
    signed_document_url = models.URLField(max_length=500, blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"ToDo: {self.title} for {self.project.project_name}"
