from app.account.models import UserAccount, Notification
from django.utils import timezone
from datetime import timedelta

email = "soper17343@homephit.com"
try:
    user = UserAccount.objects.get(email=email)
    
    # Create some dummy notifications
    notifications = [
        {
            "title": "Welcome to Josue",
            "body": "Your account has been successfully created and approved.",
            "type": Notification.Type.INFO,
            "created_at": timezone.now() - timedelta(days=2)
        },
        {
            "title": "Project Assigned",
            "body": "You have been assigned to the New Highway Construction project.",
            "type": Notification.Type.PROJECT_ASSIGNED,
            "created_at": timezone.now() - timedelta(days=1)
        },
        {
            "title": "Task Assigned",
            "body": "A new To Do list task has been assigned to you by your manager.",
            "type": Notification.Type.TASK_ASSIGNED,
            "created_at": timezone.now() - timedelta(hours=5)
        },
        {
            "title": "Work Approved",
            "body": "Your submission for the Foundation Work has been approved.",
            "type": Notification.Type.WORK_APPROVED,
            "created_at": timezone.now() - timedelta(minutes=30)
        }
    ]
    
    for n in notifications:
        notif = Notification.objects.create(
            user=user,
            title=n["title"],
            body=n["body"],
            type=n["type"],
            is_read=False
        )
        # Hack to override auto_now_add
        notif.created_at = n["created_at"]
        notif.save(update_fields=['created_at'])
        
    print(f"Successfully created {len(notifications)} notifications for {email}.")
except UserAccount.DoesNotExist:
    print(f"Error: User with email {email} does not exist in the database.")
except Exception as e:
    print(f"Error: {e}")
