# auth_backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class CompanyStatusAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First authenticate normally
        user = super().authenticate(request, username=username, password=password, **kwargs)
        
        # If user authenticated, check company status
        if user and user.company and user.company.status == 'inactive':
            return None  # Return None to deny authentication
        
        return user