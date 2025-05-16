# companies/urls.py
from django.urls import path
from .views import *
from companies.views import role_list_create, get_roles_for_form

urlpatterns = [
    path('check-subscription-status/', check_subscription_status, name='check_subscription_status'),
    path('create-company-admin/', create_company_admin, name='create_company_admin'),
   
    path('create-company/', create_company, name='create_company'),
    path('get-company-list/',get_company_list),
    # urls.py
    path('delete-company/<int:id>/',delete_company, name='delete_company'),
    path('get-company/<int:id>/', get_company),
    path('update-company/<int:id>/', update_company, name='update_company'),
    path('get-company-admin/<int:company_id>/', get_company_admin),
    path('get-all-permissions/', get_all_permissions),
    # Role endpoints
    path('roles/', role_list_create, name='role_list_create'),
    path('roles/<int:role_id>/', role_detail, name='role_detail'),
    path('get-roles-for-form/', get_roles_for_form, name='get_roles_for_form'),  # New endpoint
    
    # Position endpoints
    path('positions/', position_list_create, name='position_list_create'),
    path('positions/<int:position_id>/', position_detail, name='position_detail'),
    # Permission endpoints
    path('permissions/', get_permissions, name='get_permissions'),
    path('roles/<int:role_id>/permissions/', role_permissions, name='role_permissions'),
    path('get-role-permissions/<int:role_id>/',role_permissions, name='get_role_permissions'),
    path('roles/<int:role_id>/assign-permissions/', assign_permissions, name='assign_permissions'),
    path('user-permissions/', user_permissions, name='user_permissions'),
    path('user-check-permission/', check_permission, name='check_permission'),
    path('dashboard-stats/', dashboard_stats, name='dashboard_stats'),
    path('user-permissions/<int:user_id>/', get_user_permissions, name='get_user_permissions'),



    path('create-team-category/', create_team_category, name='create_team_category'),
    path('list-team-categories/', list_team_categories, name='list_team_categories'),
    
    # Teams
    path('create-team/', create_team, name='create_team'),
    path('list-teams/', list_teams, name='list_teams'),
    path('team-details/<int:team_id>/', get_team_details, name='team_details'),
    path('update-team/<int:team_id>/', update_team, name='update_team'),
    path('delete-team/<int:team_id>/', delete_team, name='delete_team'),
    
    # Department Personnel
    path('department-personnel/<int:department_id>/', get_department_personnel, name='department_personnel'),

    # role level access
    path('get-role-access-level/<int:role_id>/', get_role_access_level, name='get-role-access-level'),
]