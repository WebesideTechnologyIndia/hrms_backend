# Clean imports section
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout as django_logout

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from companies.models import Company, Permission
from employees.models import EmployeeProfile
from users.services import ActivityLogger
from users.models import ActivityLog

import json
from datetime import datetime

User = get_user_model()

# ------------------- AUTH VIEWS -------------------

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            print(f"Login attempt for username: {username}")

            if not username or not password:
                return JsonResponse({'error': 'Username and password are required'}, status=400)

            User = get_user_model()
            try:
                user_obj = User.objects.get(username=username)
                if user_obj.company and user_obj.company.status == 'inactive':
                    return JsonResponse({
                        'error': 'Your company account has been deactivated. Please contact support.'
                    }, status=403)
                
                if not user_obj.is_active_employee:
                    return JsonResponse({
                        'error': 'Your account has been deactivated. Please contact your administrator.'
                    }, status=403)
            except User.DoesNotExist:
                # We'll continue and let authenticate handle the non-existent user
                pass

            user = authenticate(request, username=username, password=password)

            if user is not None:
                if not user.is_active_employee:
                    return JsonResponse({
                        'error': 'Your account has been deactivated. Please contact your administrator.'
                    }, status=403)

                role = getattr(user, 'role', 'unknown')
                refresh = RefreshToken.for_user(user)
                
                # Extend token expiry if needed
                # Default is usually 5 minutes, extend it to match your idle timeout
                # For example, if idle timeout is 60 minutes, access token should be valid for at least that long
                
                # Log successful login
                try:
                    ActivityLogger.log_activity(
                        action_type='user_login',
                        performed_by=user,
                        company=user.company if hasattr(user, 'company') else None,
                        details={
                            'username': user.username,
                            'method': 'api',
                            'ip_address': request.META.get('REMOTE_ADDR', 'unknown')
                        }
                    )
                except Exception as e:
                    print(f"Error logging login activity: {e}")
                
                return JsonResponse({
                    'message': 'Login successful',
                    'username': user.username,
                    'role': role,
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                })
            else:
                # Log failed login attempts
                try:
                    ActivityLogger.log_activity(
                        action_type='failed_login',
                        performed_by=None,  # No user since authentication failed
                        company=None,
                        details={
                            'attempted_username': username,
                            'ip_address': request.META.get('REMOTE_ADDR', 'unknown')
                        }
                    )
                except Exception as e:
                    print(f"Error logging failed login: {e}")
                    
                return JsonResponse({'error': 'Invalid credentials'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # Return error for non-POST methods
    return JsonResponse({'error': 'Method not allowed'}, status=405)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout as django_logout

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    try:
        user = request.user
        company = user.company if hasattr(user, 'company') else None
        
        # Log logout before processing it
        try:
            ActivityLogger.log_activity(
                action_type='user_logout',
                performed_by=user,
                company=company,
                details={
                    'username': user.username,
                    'ip_address': request.META.get('REMOTE_ADDR', 'unknown')
                }
            )
        except Exception as e:
            print(f"Error logging logout: {e}")
        
        # JWT token blacklist
        refresh_token = request.data.get("refresh_token")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception as token_error:
                print(f"Error blacklisting token: {token_error}")
                # Continue with logout even if token blacklisting fails
        
        # Django logout (for session cleanup if using session auth alongside JWT)
        django_logout(request)

        response = Response({"message": "Logout successful"}, status=200)

        # Clear cookies if you're using them
        response.delete_cookie("sessionid", path="/")
        response.delete_cookie("csrftoken", path="/")
        
        return response

    except Exception as e:
        return Response({"message": "Logout failed", "error": str(e)}, status=400)

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from users.models import ActivityLog

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from users.models import ActivityLog

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from users.models import ActivityLog
from datetime import timedelta
from django.db.models import Q
import threading
import time

# Keep track of the background thread
inactivity_checker_thread = None
stop_thread = threading.Event()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_app_status(request):
    """API endpoint for PC app to update its running status"""
    user = request.user
    
    # Update user's app status
    user.app_running = True
    user.last_status_update = timezone.now()
    user.save()
    
    # Log status update (optional)
    try:
        # Check if this action type exists in your ACTION_TYPES
        action_types_dict = dict(ActivityLog.ACTION_TYPES)
        
        # If 'app_status_update' is not in ACTION_TYPES, use a fallback type
        if 'app_status_update' not in action_types_dict:
            # Use 'user_login' or any other existing type as fallback
            action_type = 'user_login'  # or any other type that exists
        else:
            action_type = 'app_status_update'
            
        ActivityLog.objects.create(
            action_type=action_type,
            performed_by=user,
            performed_by_role=user.role,
            company=user.company if hasattr(user, 'company') else None,
            details={
                'app_running': True,
                'ip_address': request.META.get('REMOTE_ADDR', 'unknown')
            }
        )
    except Exception as e:
        print(f"Error logging app status update: {e}")
    
    # Ensure the inactivity checker is running
    start_inactivity_checker()
    
    return JsonResponse({
        'status': 'success',
        'message': 'App status updated successfully',
        'timestamp': timezone.now().isoformat()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_app_status(request):
    """API endpoint for app to check its current status on the server"""
    user = request.user
    
    return JsonResponse({
        'status': 'success',
        'app_running': user.app_running,
        'last_update': user.last_status_update.isoformat() if user.last_status_update else None
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_app_inactive(request):
    """API endpoint to mark the app as inactive immediately and update attendance"""
    user = request.user
    print(f"Mark inactive called for user: {user.username}")
    
    # Import required models
    from employees.models import EmployeeProfile, Attendance, AttendanceLog
    
    # Update user's app status to inactive
    user.app_running = False
    user.save()
    print("User marked as inactive")
    
    # Get today's date
    today = timezone.now().date()
    print(f"Today's date: {today}")
    
    # Find if the user has an attendance record for today without check-out
    try:
        employee = EmployeeProfile.objects.get(user=user)
        print(f"Found employee profile for: {employee}")
        
        try:
            attendance = Attendance.objects.get(
                employee=employee, 
                date=today,
                check_out_time__isnull=True  # Only get records without checkout
            )
            print(f"Found open attendance record: {attendance.id}")
            
            # Record checkout time
            attendance.check_out_time = timezone.now()
            # If you're storing latitude/longitude for checkout, use default values
            attendance.check_out_latitude = attendance.check_in_latitude if hasattr(attendance, 'check_in_latitude') else None
            attendance.check_out_longitude = attendance.check_in_longitude if hasattr(attendance, 'check_in_longitude') else None
            attendance.save()
            print("Updated attendance with checkout time")
            
            # Create attendance log for automatic checkout
            log = AttendanceLog.objects.create(
                attendance=attendance,
                employee=employee,
                company=employee.company,
                latitude=attendance.check_in_latitude if hasattr(attendance, 'check_in_latitude') else None,
                longitude=attendance.check_in_longitude if hasattr(attendance, 'check_in_longitude') else None,
                face_verification_result=True,  # Assume verification OK for auto-checkout
                location_verification_result=True,  # Assume verification OK for auto-checkout
                device_info={"auto_logout": True, "app_closed": True},
                log_message="Automatic check-out when monitoring app was closed"
            )
            print(f"Created attendance log: {log.id}")
        except Attendance.DoesNotExist:
            print("No open attendance record found")
    except EmployeeProfile.DoesNotExist:
        print("Employee profile not found")
    
    # Log status update (optional)
    try:
        from users.models import ActivityLog
        ActivityLog.objects.create(
            action_type='app_status_update',
            performed_by=user,
            performed_by_role=user.role,
            company=user.company if hasattr(user, 'company') else None,
            details={
                'app_running': False,
                'action': 'app_closed',
                'attendance_updated': 'attendance' in locals()
            }
        )
        print("Created activity log")
    except Exception as e:
        print(f"Error logging app inactive status: {e}")
    
    return JsonResponse({
        'status': 'success',
        'message': 'App marked as inactive and attendance updated if needed',
        'timestamp': timezone.now().isoformat()
    })

def check_inactive_users():
    """Check for users who haven't pinged in the last 3 minutes and mark them as inactive"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Get current time
    now = timezone.now()
    # Get the cutoff time (3 minutes ago)
    cutoff_time = now - timedelta(minutes=3)
    
    # Find users who are marked as active but haven't updated their status in 3+ minutes
    inactive_users = User.objects.filter(
        Q(app_running=True) & 
        (Q(last_status_update__lt=cutoff_time) | Q(last_status_update__isnull=True))
    )
    
    print(f"Found {inactive_users.count()} users inactive for more than 3 minutes")
    
    # Process each inactive user
    for user in inactive_users:
        print(f"Auto-marking user {user.username} as inactive due to timeout")
        
        # Import required models
        from employees.models import EmployeeProfile, Attendance, AttendanceLog
        
        # Update user's app status to inactive
        user.app_running = False
        user.save()
        
        # Get today's date
        today = timezone.now().date()
        
        # Find if the user has an attendance record for today without check-out
        try:
            employee = EmployeeProfile.objects.get(user=user)
            
            try:
                attendance = Attendance.objects.get(
                    employee=employee, 
                    date=today,
                    check_out_time__isnull=True  # Only get records without checkout
                )
                
                # Record checkout time
                attendance.check_out_time = now
                # If you're storing latitude/longitude for checkout, use default values
                attendance.check_out_latitude = attendance.check_in_latitude if hasattr(attendance, 'check_in_latitude') else None
                attendance.check_out_longitude = attendance.check_in_longitude if hasattr(attendance, 'check_in_longitude') else None
                attendance.save()
                
                # Create attendance log for automatic checkout
                AttendanceLog.objects.create(
                    attendance=attendance,
                    employee=employee,
                    company=employee.company,
                    latitude=attendance.check_in_latitude if hasattr(attendance, 'check_in_latitude') else None,
                    longitude=attendance.check_in_longitude if hasattr(attendance, 'check_in_longitude') else None,
                    face_verification_result=True,  # Assume verification OK for auto-checkout
                    location_verification_result=True,  # Assume verification OK for auto-checkout
                    device_info={"auto_logout": True, "inactivity_timeout": True},
                    log_message="Automatic check-out due to 3-minute inactivity timeout"
                )
            except Attendance.DoesNotExist:
                print(f"No open attendance record found for user {user.username}")
        except EmployeeProfile.DoesNotExist:
            print(f"Employee profile not found for user {user.username}")
        
        # Log the automatic logout
        try:
            from users.models import ActivityLog
            ActivityLog.objects.create(
                action_type='auto_logout',
                performed_by=user,
                performed_by_role=user.role,
                company=user.company if hasattr(user, 'company') else None,
                details={
                    'app_running': False,
                    'action': 'auto_logout',
                    'reason': 'inactivity_timeout',
                    'inactive_duration_minutes': 3
                }
            )
        except Exception as e:
            print(f"Error logging auto-logout: {e}")

def inactivity_checker_worker():
    """Background thread function to periodically check for inactive users"""
    print("Starting inactivity checker background thread")
    
    CHECK_INTERVAL = 60  # Check once per minute
    
    while not stop_thread.is_set():
        try:
            # Check for inactive users
            check_inactive_users()
        except Exception as e:
            print(f"Error in inactivity checker: {e}")
            import traceback
            traceback.print_exc()
        
        # Sleep for the interval
        for _ in range(CHECK_INTERVAL):
            if stop_thread.is_set():
                break
            time.sleep(1)
    
    print("Inactivity checker thread exiting")

def start_inactivity_checker():
    """Start the background thread to check for inactive users"""
    global inactivity_checker_thread, stop_thread
    
    # Only start if not already running
    if inactivity_checker_thread is None or not inactivity_checker_thread.is_alive():
        # Reset the stop event
        stop_thread.clear()
        
        # Create and start the thread
        inactivity_checker_thread = threading.Thread(target=inactivity_checker_worker)
        inactivity_checker_thread.daemon = True
        inactivity_checker_thread.start()
        print("Inactivity checker thread started")

def stop_inactivity_checker():
    """Stop the background thread"""
    global inactivity_checker_thread, stop_thread
    
    if inactivity_checker_thread and inactivity_checker_thread.is_alive():
        # Signal the thread to stop
        stop_thread.set()
        
        # Wait for it to finish (with timeout)
        inactivity_checker_thread.join(5)
        print("Inactivity checker thread stopped")
    
def is_monitoring_app_running(user):
    """Check if user's monitoring app is running"""
    return user.app_running  # Now we only rely on the app_running flag


from employees.models import Attendance

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_pending_logout(request):
    user = request.user
    logout_time = request.data.get('logout_time')
    reason = request.data.get('reason', 'Connection lost')
    
    try:
        # Parse the ISO format datetime
        logout_datetime = datetime.fromisoformat(logout_time)
        
        # Get the EmployeeProfile for this user
        from employees.models import EmployeeProfile, Attendance, AttendanceLogs
        
        # Find the EmployeeProfile that is related to this user
        employee_profile = EmployeeProfile.objects.get(user=user)
        
        # Get the latest attendance record for this employee
        attendance = Attendance.objects.filter(employee=employee_profile).latest('check_in_time')
        
        # Update the checkout time
        attendance.check_out_time = logout_datetime  # Adjust as needed for your status choices
        attendance.save()
        
        # Create an AttendanceLogs record for the logout
        AttendanceLogs.objects.create(
            employee=employee_profile,
            attendance=attendance,
            action_type='logout',
            action_time=logout_datetime,
            action_by=user,
            reason=reason,
            status='completed',
            details=f"Synced logout after connection loss. Original logout time: {logout_time}"
        )
        
        # Also update the application status if needed
        from employees.models import ApplicationStatus
        try:
            app_status = ApplicationStatus.objects.get(employee=employee_profile)
            app_status.is_running = False
            app_status.last_updated = logout_datetime
            app_status.save()
        except ApplicationStatus.DoesNotExist:
            # If no status exists, create one
            ApplicationStatus.objects.create(
                employee=employee_profile,
                is_running=False,
                last_updated=logout_datetime
            )
        
        return Response({"message": "Attendance and logs updated successfully"})
    except EmployeeProfile.DoesNotExist:
        return Response({"error": "Employee profile not found for this user"}, status=404)
    except Attendance.DoesNotExist:
        return Response({"error": "No attendance record found for this employee"}, status=404) 
    except Exception as e:
        return Response({"error": str(e)}, status=400)
# --------------- FORM FIELDS FOR FRONTEND -------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_create_admin_form_fields(request):
    if not request.user.is_superuser and request.user.role != 'superadmin':
        return JsonResponse({'error': 'Only superadmin can access form fields'}, status=403)

    # Get company_type from query params
    company_type = request.GET.get("company_type")
    
    if not company_type or company_type not in ['tech', 'educational']:
        # If company_type is not provided or invalid, don't include permissions
        return JsonResponse({
            "fields": [
                {"name": "username", "type": "text", "label": "Username"},
                {"name": "email", "type": "email", "label": "Email"},
                {"name": "password", "type": "password", "label": "Password"},
                {"name": "confirm_password", "type": "password", "label": "Confirm Password"},
                {"name": "company_id", "type": "number", "label": "Company ID"},
                {"name": "role", "label": "Select Role", "type": "select"}
            ],
            "permissions": []  # No permissions if company_type is invalid or not provided
        }, status=400)  # Optional: return error 400 for invalid company_type

    # Fetch permissions based on company type
    perms = Permission.objects.filter(company_type=company_type)
    permissions = list(perms.values("id", "name", "company_type"))

    return JsonResponse({
        "fields": [
            {"name": "username", "type": "text", "label": "Username"},
            {"name": "email", "type": "email", "label": "Email"},
            {"name": "password", "type": "password", "label": "Password"},
            {"name": "confirm_password", "type": "password", "label": "Confirm Password"},
            {"name": "company_id", "type": "number", "label": "Company ID"},
            {"name": "role", "label": "Select Role", "type": "select"}
        ],
        "permissions": permissions  # Only include relevant permissions if company_type is valid
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_data(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    user = request.user
    company = getattr(user, 'company', None)

    access_level = None
    try:
        employee_profile = user.employeeprofile
        access_level = employee_profile.access_level
    except EmployeeProfile.DoesNotExist:
        employee_profile = None

    return JsonResponse({
        'username': user.username,
        'email': user.email,
        'role': user.role,

        'access_level': access_level,  # ✅ now comes from EmployeeProfile

        'company': company.name if company else None,
        'company_id': company.id if company else None,

        'department': user.department.name if user.department else None,
        'department_id': user.department.id if user.department else None,

        'position': user.position.name if user.position else None,
        'position_id': user.position.id if user.position else None,

        'positional_level': user.positional_level.name if user.positional_level else None,

        'user_role': user.user_role.name if user.user_role else None,
        'user_role_id': user.user_role.id if user.user_role else None,

        'permissions': list(user.permissions.values('id', 'name', 'code', 'category')),

        'employee_id': user.id,
        'team_ids': [],
    })




@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    print("User:", request.user)
    print("Is Authenticated:", request.user.is_authenticated)

    data = request.data
    print("Received data:", data)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Store old values for logging
    old_email = user.email
    old_username = user.username
    old_role = user.role
    
    # Update user fields
    user.email = data.get('email', user.email)
    user.username = data.get('username', user.username)
    user.role = data.get('role', user.role)
    user.save()

    # Get permission changes
    old_permissions = list(user.permissions.values_list('id', flat=True))
    permission_ids = data.get('permission_ids', [])
    print("Permission IDs received:", permission_ids)

    if permission_ids:
        user.permissions.set(permission_ids)
        print("Permissions updated!")
    
    # Log user update
    try:
        # Build details for logging
        changed_fields = []
        if old_email != user.email:
            changed_fields.append(f"email: {old_email} → {user.email}")
        if old_username != user.username:
            changed_fields.append(f"username: {old_username} → {user.username}")
        if old_role != user.role:
            changed_fields.append(f"role: {old_role} → {user.role}")
        
        # Add permission changes
        if set(old_permissions) != set(permission_ids):
            changed_fields.append("permissions updated")
        
        if changed_fields:
            ActivityLogger.log_activity(
                action_type='user_updated',
                performed_by=request.user,
                company=getattr(request.user, 'company', None),
                details={
                    'target_user_id': user.id,
                    'target_username': user.username,
                    'changes': ", ".join(changed_fields)
                }
            )
    except Exception as e:
        print(f"Error logging user update: {e}")

    return Response({'message': 'User updated successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_permissions_by_email(request):
    email = request.GET.get('email')
    if email:
        try:
            user = User.objects.get(email=email)
            
            # Get only direct permissions, not those from groups
            if hasattr(user, 'permissions'):
                # For custom permissions model
                permissions = user.permissions.all()
            else:
                # For Django's default permissions
                permissions = user.user_permissions.all()
                
            serialized_permissions = [
                {"name": p.name, "code": getattr(p, 'code', p.code), "category": getattr(p, 'category', 'other')}
                for p in permissions
            ]
            
            return JsonResponse({
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "permissions": serialized_permissions
            })
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)
    
    return JsonResponse({"error": "Email parameter is required."}, status=400)


def toggle_employee_status(request, id):
    try:
        # Find the employee by ID, ensuring it belongs to the current user's company
        employee = EmployeeProfile.objects.get(id=id, user__company=request.user.company)
        
        # Toggle the is_active_employee status
        user = employee.user
        old_status = user.is_active_employee
        user.is_active_employee = not user.is_active_employee
        user.save()
        
        # Log employee status change
        try:
            from activities.services import ActivityLogger
            
            ActivityLogger.log_activity(
                action_type='employee_status_changed',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'employee_id': employee.id,
                    'username': user.username,
                    'full_name': employee.full_name,
                    'previous_status': 'Active' if old_status else 'Inactive',
                    'new_status': 'Active' if user.is_active_employee else 'Inactive',
                    'changed_by': request.user.username
                }
            )
        except Exception as log_error:
            print(f"Error logging employee status change: {log_error}")
        
        return Response({
            'success': True,
            'message': f"Employee {'activated' if user.is_active_employee else 'deactivated'} successfully",
            'is_active': user.is_active_employee
        })
    except EmployeeProfile.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
# activities/views.py
# activities/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils.timezone import datetime
from .models import ActivityLog
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_activity_logs(request):
    """
    Get activity logs with filtering options.
    
    Query parameters:
    - action_type: Filter by action type
    - user_id: Filter by user ID
    - company_id: Filter by company ID
    - start_date: Filter logs after this date (YYYY-MM-DD)
    - end_date: Filter logs before this date (YYYY-MM-DD)
    - search: Search term to filter by details or role
    - limit: Limit number of results (default 50)
    - page: Page number for pagination
    """
    try:
        # Check if user has permission to view logs
        if not (request.user.is_superuser or 
                request.user.role == 'superadmin' or 
                request.user.role == 'companyadmin' or
                request.user.has_permission('view_activity_logs')):
            return Response(
                {"error": "You do not have permission to view activity logs."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get query parameters
        action_type = request.GET.get('action_type')
        user_id = request.GET.get('user_id')
        company_id = request.GET.get('company_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        search = request.GET.get('search')
        limit = int(request.GET.get('limit', 50))
        page = int(request.GET.get('page', 1))
        
        # Calculate offset for pagination
        offset = (page - 1) * limit
        
        # Start with all logs
        logs_query = ActivityLog.objects.all()
        
        # Exclude activity_logs_viewed actions - this prevents logs about viewing logs
        logs_query = logs_query.exclude(action_type='activity_logs_viewed')
        
        # Apply filters
        if action_type:
            logs_query = logs_query.filter(action_type=action_type)
        
        if user_id:
            logs_query = logs_query.filter(performed_by_id=user_id)
        
        # For non-superadmins, limit to their company
        if not (request.user.is_superuser or request.user.role == 'superadmin'):
            # If company_id is specified and user is companyadmin, check if it's their company
            if company_id and request.user.role == 'companyadmin':
                if str(request.user.company.id) != company_id:
                    return Response(
                        {"error": "You can only view logs for your own company."},
                        status=status.HTTP_403_FORBIDDEN
                    )
            # Force filter by user's company
            logs_query = logs_query.filter(company=request.user.company)
        elif company_id:  # Superadmin with company filter
            logs_query = logs_query.filter(company_id=company_id)
        
        # Date filters
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                logs_query = logs_query.filter(timestamp__date__gte=start_date_obj)
            except ValueError:
                return Response(
                    {"error": "Invalid start_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                logs_query = logs_query.filter(timestamp__date__lte=end_date_obj)
            except ValueError:
                return Response(
                    {"error": "Invalid end_date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Search in details or role
        if search:
            logs_query = logs_query.filter(
                Q(performed_by__username__icontains=search) |
                Q(performed_by__first_name__icontains=search) |
                Q(performed_by__last_name__icontains=search) |
                Q(performed_by_role__icontains=search) |
                Q(company__name__icontains=search) |
                Q(details__icontains=search)  # This works only if details is stored as text
            )
        
        # Get total count before pagination
        total_count = logs_query.count()
        
        # Order by most recent first and apply pagination
        logs = logs_query.order_by('-timestamp')[offset:offset+limit]
        
        # Manual serialization without using serializers
        serialized_logs = []
        for log in logs:
            # Get performer name
            performer_name = "System"
            if log.performed_by:
                first_name = getattr(log.performed_by, 'first_name', '')
                last_name = getattr(log.performed_by, 'last_name', '')
                username = getattr(log.performed_by, 'username', '')
                performer_name = f"{first_name} {last_name}".strip() or username
            
            # Get company name
            company_name = None
            if log.company:
                company_name = log.company.name
            
            # Convert details JSON to dict if stored as string
            details = log.details
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    details = {"raw": details}
            
            # Get action display name
            action_display = log.action_type
            for action_code, action_name in ActivityLog.ACTION_TYPES:
                if action_code == log.action_type:
                    action_display = action_name
                    break
            
            log_data = {
                'id': log.id,
                'action_type': log.action_type,
                'action_display': action_display,
                'timestamp': log.timestamp.isoformat(),
                'formatted_timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': details,
                'performed_by_id': log.performed_by.id if log.performed_by else None,
                'performed_by_name': performer_name,
                'performed_by_role': log.performed_by_role or 'System',
                'company_id': log.company.id if log.company else None,
                'company_name': company_name,
            }
            serialized_logs.append(log_data)
        
        # Log this activity ONLY for non-superadmin users
        if not (request.user.is_superuser or request.user.role == 'superadmin'):
            try:
                ActivityLog.objects.create(
                    action_type='activity_logs_viewed',
                    performed_by=request.user,
                    performed_by_role=request.user.role,
                    company=getattr(request.user, 'company', None),
                    details={
                        'filters': {
                            'action_type': action_type,
                            'user_id': user_id,
                            'company_id': company_id,
                            'start_date': start_date,
                            'end_date': end_date,
                            'search': search,
                        },
                        'results_count': len(serialized_logs),
                        'total_count': total_count,
                        'page': page,
                        'limit': limit
                    }
                )
            except Exception as e:
                logger.error(f"Error logging activity_logs_viewed: {e}")
        
        # Get action types for filtering
        action_types_dict = {}
        for action_code, action_name in ActivityLog.ACTION_TYPES:
            action_types_dict[action_code] = action_name
        
        # Return response with pagination info
        return Response({
            'results': serialized_logs,
            'count': total_count,
            'next': f"/api/logs/?limit={limit}&page={page+1}" if (offset + limit) < total_count else None,
            'previous': f"/api/logs/?limit={limit}&page={page-1}" if page > 1 else None,
            'page': page,
            'total_pages': (total_count + limit - 1) // limit,  # Ceiling division
            'action_types': action_types_dict
        })
    
    except Exception as e:
        logger.error(f"Error getting activity logs: {e}")
        return Response(
            {"error": "Failed to fetch activity logs", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )