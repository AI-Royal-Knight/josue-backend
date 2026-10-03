from django.urls import path
from .views import InviteEmployeeView, ApproveEmployeeView, RevokeEmployeeView

app_name = 'document_controller'

urlpatterns = [
    path('invite-employee/', InviteEmployeeView.as_view(), name='invite_employee'),
    path('approve-employee/', ApproveEmployeeView.as_view(), name='approve_employee'),
    path('revoke-employee/', RevokeEmployeeView.as_view(), name='revoke_employee'),
]
