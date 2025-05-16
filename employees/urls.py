from django.urls import path
from .views import *

urlpatterns = [
    path('create/', create_employee, name='create-employee'),
    path('list/', list_employees, name='list_employees'),
    path('delete/<int:id>/',delete_employee, name='delete_employee'),
    path('employees/<int:id>/', get_employee), 
    path('fix-document-paths/', fix_document_paths, name='fix_document_paths'),
    # Department routes
    path("departments/", department_view, name="departments"),
    path("departments/<int:pk>/", department_view, name="department_detail"),
    
    # Position routes
    path('positions/', position_view, name="positions"),  # POST & GET all positions
    path('positions/<int:position_id>/', position_view, name="position_detail"),  # GET, PUT, DELETE for specific position
    
    # Position Level routes
    path('position-levels/', position_level_view, name="position_levels"),  # POST & GET all position levels
    path('position-levels/<int:position_level_id>/', position_level_view, name="position_level_detail"),  # GET, PUT, DELETE for specific position level
    
    # Other existing routes
    path('get_departments/',get_departments),
    path('get_positions/', get_positions),
    path('view_all_documents/', get_all_employee_documents),
    # path('create-position-level/', create_position_level, name='create_position_level'),
    path('get_roles/', get_roles, name='get_roles'),
    path('get_position_levels/', get_position_levels, name='get_roles'),
    path('employee-permissions/<int:employee_id>/', get_employee_permissions),


    # path('current-user-info/', get_current_user_info, name='current_user_info'),

    # Check if employee has registered face data
    path('has-face-data/', has_face_data, name='has_face_data'),
    
    # Register face data
    path('register-face/', register_face_data, name='register_face_data'),
    path('check-face-data/', check_face_data, name='check_face_data'),
    path('get-face-image/', get_face_image, name='get_face_image'),
    # Add to urlpatterns
    path('compare-faces/', compare_faces, name='compare_faces'),
    # Mark attendance
    path('mark/', mark_attendance, name='mark_attendance'),
    
    # Get attendance history
    path('history/', attendance_history, name='attendance_history'),
    
    # Get last attendance record
    path('last/', last_attendance, name='last_attendance'),
    path('locations/', manage_employee_locations, name='employee-locations'),
    path('locations/<int:location_id>/', manage_employee_location_detail, name='employee-location-detail'),
    path('my-allowed-locations/', get_my_allowed_locations, name='my-allowed-locations'),
    


    # sofware sc 
    path('screenshot/', upload_screenshot, name='upload_screenshot'),
    path('screenshots/', get_employee_screenshots, name='get_employee_screenshots'),
    path('screenshots/<int:employee_id>/', get_employee_screenshots, name='get_employee_screenshots_by_id'),



    # Shift management
path('shifts/', shift_list, name='shift_list'),
path('create_shift/', shift_create, name='create_shift'),
path('shifts/<int:shift_id>/', shift_detail, name='shift_detail'),
path('shifts/<int:shift_id>/update/', shift_update, name='shift_update'),
path('shifts/<int:shift_id>/delete/', shift_delete, name='shift_delete'),
path('filtered_shift_assignments/', filtered_shift_assignments, name='filtered_user_shifts'),

# Shift assignment
path('shift-assignments/', shift_assignment_list, name='shift_assignment_list'),
path('shift-assignments/create/', shift_assignment_create, name='shift_assignment_create'),
path('shift-assignments/<int:assignment_id>/', shift_assignment_detail, name='shift_assignment_detail'),
path('shift-assignments/<int:assignment_id>/update/', shift_assignment_update, name='shift_assignment_update'),
path('shift-assignments/<int:assignment_id>/delete/', shift_assignment_delete, name='shift_assignment_delete'),

# User shifts
path('user-shifts/', user_shift_list, name='user_shift_list'),
path('current-user-shift/', current_user_shift, name='current_user_shift'),
path('users_by_shift/<int:shift_id>/', users_by_shift, name='users_by_shift'),

# Shift rotation
path('trigger-shift-rotation/', trigger_shift_rotation, name='trigger_shift_rotation'),

# Utility endpoints
path('departments/', get_departments, name='get_departments'),
path('teams/', get_teams, name='get_teams'),
path('users/', get_users, name='get_users'),
]