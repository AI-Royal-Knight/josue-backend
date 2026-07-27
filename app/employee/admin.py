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

from .models import RAMS, DailyBriefing, ToolboxTalk, ToDoList

@admin.register(RAMS)
class RAMSAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'date', 'review_date', 'completed_at')
    list_filter = ('project', 'date')
    search_fields = ('title', 'project__project_name')

@admin.register(DailyBriefing)
class DailyBriefingAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'date', 'completed_at')
    list_filter = ('project', 'date')
    search_fields = ('title', 'project__project_name')

@admin.register(ToolboxTalk)
class ToolboxTalkAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'date', 'completed_at')
    list_filter = ('project', 'date')
    search_fields = ('title', 'project__project_name')

@admin.register(ToDoList)
class ToDoListAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'date', 'completion_date', 'assign_user', 'completed_at')
    list_filter = ('project', 'date')
    search_fields = ('title', 'assign_user', 'project__project_name')
