from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from datetime import date

class SubscriptionCheckMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated:
            return None

        company = getattr(user, 'company', None)
        if not company:
            return None

        if company.subscription_end and company.subscription_end < date.today():
            # Dashboard APIs jaise GET /user-data allow, baki POST/PUT block
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                return JsonResponse({
                    "error": "Subscription expired. Please renew to continue using the system."
                }, status=403)

        return None

# users/middleware.py

from django.shortcuts import redirect
from django.contrib import messages

class PermissionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Get permission required attribute if exists
        permission_required = getattr(view_func, 'permission_required', None)
        
        if permission_required and request.user.is_authenticated:
            if not request.user.has_permission(permission_required):
                messages.error(request, "You don't have permission to access this page.")
                return redirect('dashboard')
        
        return None

# middleware.py
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

class CompanyStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user is authenticated
        if request.user.is_authenticated:
            # Check if user has a company and if it's inactive
            if hasattr(request.user, 'company') and request.user.company and request.user.company.status == 'inactive':
                # Log user out
                logout(request)
                # Add message
                messages.error(request, "Your company account has been deactivated. Please contact support.")
                # Redirect to login
                return redirect('login')
        
        response = self.get_response(request)
        return response
    
