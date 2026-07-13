from django.contrib import admin
from .models import UserAccount, SupplierProfile, CompanySupplier, Invitation

admin.site.register(UserAccount)
admin.site.register(SupplierProfile)
admin.site.register(CompanySupplier)
admin.site.register(Invitation)
