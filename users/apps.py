# users/apps.py ya jahan bhi aapka User model defined hai
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'  # ya aapka app name
    
    def ready(self):
        import users.signals  # yahin signal file import karo