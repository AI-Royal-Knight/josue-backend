from .serializers import UserSerializer

class ProfileService:
    @staticmethod
    def get_profile(user):

        data = UserSerializer(user).data

        if user.role == "super_admin":
            pass
            # data["profile"] = (
            #     AdminProfileSerializer(
            #         user.adminprofile
            #     ).data
            # )

        return data
