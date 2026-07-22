from .serializers import UserSerializer

class ProfileService:
    @staticmethod
    def get_profile(user, context=None):
        data = UserSerializer(user, context=context).data

        if user.role == "super_admin":
            pass
            # data["profile"] = (
            #     AdminProfileSerializer(
            #         user.adminprofile
            #     ).data
            # )

        return data
