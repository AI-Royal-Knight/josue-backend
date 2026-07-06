from django.contrib import admin
from .models import AttendanceLog

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'date', 'check_in_time', 'check_out_time', 'status')
    list_filter = ('status', 'date', 'company')
    search_fields = ('user__email', 'user__first_name', 'project__project_name')

from .models import RFI

@admin.register(RFI)
class RFIAdmin(admin.ModelAdmin):
    list_display = ('rfi_number', 'project', 'status', 'created_at', 'closed_at')
    list_filter = ('status', 'project')
    search_fields = ('rfi_number',)
    readonly_fields = ('rfi_number',)
