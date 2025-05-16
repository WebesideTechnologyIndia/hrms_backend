from django.urls import path
from .views import *
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({"message": "CSRF cookie set"})

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_user, name='logout'),
    path('user/', get_user_data, name='get_user'),
    
    # New endpoint for app status updates
    path('user/app-status/', update_app_status, name='update_app_status'),
    path('user/app-status/check/', check_app_status, name='check_app_status'),
    path('user/app-status/inactive/', mark_app_inactive, name='mark_app_inactive'),
    path('user/sync-pending-logout/', sync_pending_logout, name='mark_app_inactive'),
    
    path('toggle-status/<int:id>/', toggle_employee_status, name='toggle_employee_status'),
    path('create-admin-form-fields/', get_create_admin_form_fields),
    path('get_user_data/', get_user_data, name='get_user_data'),
    path('update-user/<int:user_id>/', update_user, name='update_user'),
    path('api/get-csrf-token/', get_csrf_token, name='get-csrf-token'),
    path('get-user-permissions-by-email/', get_user_permissions_by_email, name='get-user-permissions-by-email'),
    path('get-user-permissions-by-email/<str:email>/', get_user_permissions_by_email, name='get-user-permissions-by-email'),
    path('logs/', get_activity_logs, name='activity_logs'),
]