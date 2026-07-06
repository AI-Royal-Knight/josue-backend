from django.urls import path
from .views import (
    EmployeeAssignedProjectsView,
    EmployeeAvailableProjectsView,
    EmployeeAssignProjectView,
    AttendanceStatusView,
    CheckInView,
    CheckOutView,
    MyFoldersView,
    RFIListView,
    RFICreateView,
    DailyRegister,
    OperationsListView,
    RAMSCreateView,
    DailyBriefingCreateView,
    ToolboxTalkCreateView,
    ToDoCreateView,
    CompanyEmployeeListView,
)

app_name = 'employee'

urlpatterns = [
    path('assigned-projects/', EmployeeAssignedProjectsView.as_view(), name='assigned-projects'),
    path('available-projects/', EmployeeAvailableProjectsView.as_view(), name='available-projects'),
    path('assign-project/', EmployeeAssignProjectView.as_view(), name='assign-project'),
    path('attendance/status/', AttendanceStatusView.as_view(), name='attendance-status'),
    path('attendance/check-in/', CheckInView.as_view(), name='check-in'),
    path('attendance/check-out/', CheckOutView.as_view(), name='check-out'),
    path('my-folders/', MyFoldersView.as_view(), name='my-folders'),
    path('rfis/', RFIListView.as_view(), name='rfi-list'),
    path('rfis/create/', RFICreateView.as_view(), name='rfi-create'),
    path('daily-register/', DailyRegister.as_view(), name='daily-register'),
    path('operations/', OperationsListView.as_view(), name='operations-list'),
    path('operations/rams/create/', RAMSCreateView.as_view(), name='rams-create'),
    path('operations/briefings/create/', DailyBriefingCreateView.as_view(), name='briefing-create'),
    path('operations/toolbox-talks/create/', ToolboxTalkCreateView.as_view(), name='toolbox-talk-create'),
    path('operations/todos/create/', ToDoCreateView.as_view(), name='todo-create'),
    path('company-employees/', CompanyEmployeeListView.as_view(), name='company-employees'),
]
