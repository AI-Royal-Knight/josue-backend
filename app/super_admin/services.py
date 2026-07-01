from app.account.models import UserAccount
from app.super_admin.models import RecentActivity


class DashboardService:

    @staticmethod
    def get_super_admin_dashboard():

        return {
            "statistics": {
                "admin_users": UserAccount.objects.filter(
                    role=UserAccount.Role.ADMIN
                ).count(),

                "users": UserAccount.objects.count(),
            },

            "recent_activities": [
                {
                    "id": activity.id,
                    "message": activity.activity_name,
                    "created_at": activity.created_at,
                }
                for activity in RecentActivity.objects
                .order_by("-created_at")[:10]
            ],
        }
