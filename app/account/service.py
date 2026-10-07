from .serializers import UserSerializer
from .models import UserProfile

class ProfileService:
    @staticmethod
    def get_profile(user, context=None):
        if getattr(user, 'role', None) == "super_admin":
            try:
                _ = user.profile
            except Exception:
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "company_name": "Tresta",
                        "account_name": "Estrada building services",
                        "bank_name": "Santander",
                        "sort_code": "09-01-28",
                        "account_number": "82051171",
                        "vat_number": "237 5409 01",
                        "address": "84 Alers Road, Bexleyheath, DA6 8HT",
                        "bank_address": "84 Alers Road, Bexleyheath, DA6 8HT",
                    }
                )

        data = UserSerializer(user, context=context).data
        return data

