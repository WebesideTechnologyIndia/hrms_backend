from functools import wraps
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

def employee_access_control(action_type):
    """
    Decorator to control employee-related actions based on user's access level.
    
    This decorator ensures users can only perform actions on employees based on their
    access level (self, team, department, company).
    
    Args:
        action_type: The type of action ('view', 'add', 'edit', 'delete')
        
    Usage:
        @employee_access_control('add')
        def create_employee(request):
            # User can only add employees if they have proper access
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required"}, status=401)
                
            # Superadmins bypass access control
            if request.user.is_superuser or request.user.role == 'superadmin':
                return view_func(request, *args, **kwargs)
            
            # Check for specific permission required for this action
            permission_name = f"tech_{'manage' if action_type != 'view' else 'view'}_employee"
            if not request.user.has_permission(permission_name):
                logger.info(f"User {request.user.username} denied access: missing permission {permission_name}")
                return JsonResponse(
                    {"detail": f"You don't have permission to {action_type} employees"},
                    status=403
                )
            
            # Get access level from request (set by middleware)
            if not hasattr(request, 'access_level'):
                logger.error(f"Access level not set for user {request.user.username}")
                return JsonResponse({"detail": "Access level not available"}, status=500)
            
            access_info = request.access_level
            access_level = access_info.get('level', 'self')
            user_dept_id = access_info.get('department_id')
            user_team_ids = access_info.get('team_ids', [])
            
            # Handle 'add' action - validate the department_id in the request
            if action_type == 'add':
                # Get target department from request data
                target_dept_id = None
                
                # Try to get from JSON data
                if hasattr(request, 'data'):
                    target_dept_id = request.data.get('department_id')
                # Or from POST data
                else:
                    target_dept_id = request.POST.get('department_id')
                
                # If no department provided, use the user's department
                if not target_dept_id:
                    # Modify the request data to include user's department
                    if hasattr(request, 'data') and isinstance(request.data, dict):
                        request.data['department_id'] = user_dept_id
                    elif request.method == 'POST':
                        request.POST = request.POST.copy()
                        request.POST['department_id'] = user_dept_id
                    
                    # Execute the view with modified data
                    return view_func(request, *args, **kwargs)
                
                # Try to convert to int for comparison
                try:
                    target_dept_id = int(target_dept_id)
                except (ValueError, TypeError):
                    pass
                
                # Enforce access restrictions based on level
                if access_level == 'self' and target_dept_id != user_dept_id:
                    logger.info(f"User {request.user.username} denied: self access trying to add employee to department {target_dept_id}")
                    return JsonResponse(
                        {"detail": "You can only add employees to your own department"},
                        status=403
                    )
                
                elif access_level == 'team':
                    # Check if target is in user's team
                    if target_dept_id != user_dept_id and target_dept_id not in user_team_ids:
                        logger.info(f"User {request.user.username} denied: team access trying to add employee to department {target_dept_id}")
                        return JsonResponse(
                            {"detail": "You can only add employees to departments in your team"},
                            status=403
                        )
                
                elif access_level == 'department' and target_dept_id != user_dept_id:
                    # For department-level, must be in same department or child department
                    from employees.models import Department
                    try:
                        target_dept = Department.objects.get(id=target_dept_id)
                        # If parent_department feature exists, check it
                        if hasattr(target_dept, 'parent') and target_dept.parent_id == user_dept_id:
                            # Allow access to child departments
                            pass
                        else:
                            logger.info(f"User {request.user.username} denied: department access trying to add employee to department {target_dept_id}")
                            return JsonResponse(
                                {"detail": "You can only add employees to your department or its sub-departments"},
                                status=403
                            )
                    except Department.DoesNotExist:
                        return JsonResponse({"detail": "Department not found"}, status=404)
                
                # Company level can add to any department
            
            # Get target employee ID based on the action (for edit/view/delete)
            elif action_type in ('view', 'edit', 'delete'):
                target_emp_id = None
                
                # From URL parameters
                if 'pk' in kwargs or 'employee_id' in kwargs or 'id' in kwargs:
                    target_emp_id = kwargs.get('pk') or kwargs.get('employee_id') or kwargs.get('id')
                
                # From request body (for PUT operations)
                elif request.method in ('PUT',):
                    # Try to get from JSON data
                    if hasattr(request, 'data'):
                        target_emp_id = request.data.get('id')
                    # Or from POST data
                    else:
                        target_emp_id = request.POST.get('id')
                
                if target_emp_id:
                    # Try to convert to int for comparison
                    try:
                        target_emp_id = int(target_emp_id)
                    except (ValueError, TypeError):
                        pass
                    
                    # For self access, can only view/edit self
                    if access_level == 'self' and target_emp_id != request.user.id:
                        logger.info(f"User {request.user.username} denied: self access trying to access employee {target_emp_id}")
                        return JsonResponse(
                            {"detail": "You can only access your own employee record"},
                            status=403
                        )
                    
                    # For team/department/company, check department relationship
                    elif access_level in ('team', 'department'):
                        # Get employee's department
                        from employees.models import Employee
                        try:
                            employee = Employee.objects.get(id=target_emp_id)
                            employee_dept_id = getattr(employee, 'department_id', None)
                            
                            if access_level == 'team':
                                # Check if employee is in one of the user's teams
                                if employee_dept_id != user_dept_id and employee_dept_id not in user_team_ids:
                                    logger.info(f"User {request.user.username} denied: team access trying to access employee {target_emp_id}")
                                    return JsonResponse(
                                        {"detail": "You can only access employees in your team"},
                                        status=403
                                    )
                            
                            elif access_level == 'department':
                                # For department access, check if employee is in same department or sub-department
                                if employee_dept_id != user_dept_id:
                                    # Check if employee's department is a child of user's department
                                    from employees.models import Department
                                    try:
                                        emp_dept = Department.objects.get(id=employee_dept_id)
                                        if not (hasattr(emp_dept, 'parent') and emp_dept.parent_id == user_dept_id):
                                            logger.info(f"User {request.user.username} denied: department access trying to access employee {target_emp_id}")
                                            return JsonResponse(
                                                {"detail": "You can only access employees in your department hierarchy"},
                                                status=403
                                            )
                                    except Department.DoesNotExist:
                                        pass
                                
                        except Employee.DoesNotExist:
                            return JsonResponse({"detail": "Employee not found"}, status=404)
            
            # For list views, we'll filter in the view function
            
            # Log the access
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type=f"employee_{action_type}_access",
                    performed_by=request.user,
                    company=getattr(request.user, 'company', None),
                    details={
                        'access_level': access_level,
                        'allowed': True
                    }
                )
            except Exception as e:
                logger.error(f"Error logging employee access: {e}")
            
            # If we got here, access is granted
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator

def department_access_control(action_type):
    """
    Decorator to control department-related actions based on user's access level.
    
    This decorator ensures users can only perform actions on departments based on their
    access level (self, team, department, company).
    
    Args:
        action_type: The type of action ('view', 'add', 'edit', 'delete')
        
    Usage:
        @department_access_control('add')
        def create_department(request):
            # User can only add departments if they have proper access
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required"}, status=401)
                
            # Superadmins bypass access control
            if request.user.is_superuser or request.user.role == 'superadmin':
                return view_func(request, *args, **kwargs)
            
            # Check for specific permission required for this action
            permission_name = f"tech_{'manage' if action_type != 'view' else 'view'}_department"
            if not request.user.has_permission(permission_name):
                logger.info(f"User {request.user.username} denied access: missing permission {permission_name}")
                return JsonResponse(
                    {"detail": f"You don't have permission to {action_type} departments"},
                    status=403
                )
            
            # Get access level from request (set by middleware)
            if not hasattr(request, 'access_level'):
                logger.error(f"Access level not set for user {request.user.username}")
                return JsonResponse({"detail": "Access level not available"}, status=500)
            
            access_info = request.access_level
            access_level = access_info.get('level', 'self')
            user_dept_id = access_info.get('department_id')
            
            # Get target department ID based on the action
            target_dept_id = None
            
            # For view/edit/delete operations
            if 'pk' in kwargs or 'department_id' in kwargs:
                target_dept_id = kwargs.get('pk') or kwargs.get('department_id')
            
            # From request body (for POST/PUT operations)
            elif request.method in ('POST', 'PUT'):
                # Try to get from JSON data
                if hasattr(request, 'data'):
                    target_dept_id = request.data.get('department_id') or request.data.get('id')
                # Or from POST data
                else:
                    target_dept_id = request.POST.get('department_id') or request.POST.get('id')
            
            # For list views, no target department - will filter in the view
            
            # Handle 'add' action differently - no target department yet
            if action_type == 'add':
                # For 'self' access level, ensure the new department is assigned to user's department
                if access_level == 'self':
                    # Attach the user's department ID to kwargs for the view to use
                    kwargs['parent_department_id'] = user_dept_id
                
                # For 'team' and 'department' access, new departments must be connected to their department
                elif access_level in ('team', 'department'):
                    kwargs['parent_department_id'] = user_dept_id
                
                # Company-level can add departments anywhere
                
                # Execute the view
                return view_func(request, *args, **kwargs)
            
            # For other actions (view, edit, delete), check access to target department
            if target_dept_id:
                # Try to convert to int for comparison
                try:
                    target_dept_id = int(target_dept_id)
                except (ValueError, TypeError):
                    pass
                
                # Check access based on access level
                if access_level == 'self' and target_dept_id != user_dept_id:
                    logger.info(f"User {request.user.username} denied: self access trying to access department {target_dept_id}")
                    return JsonResponse(
                        {"detail": "You can only access your own department"},
                        status=403
                    )
                
                elif access_level == 'team':
                    # Check if target is in user's team
                    team_depts = access_info.get('team_ids', [])
                    if target_dept_id != user_dept_id and target_dept_id not in team_depts:
                        logger.info(f"User {request.user.username} denied: team access trying to access department {target_dept_id}")
                        return JsonResponse(
                            {"detail": "You can only access departments in your team"},
                            status=403
                        )
                
                elif access_level == 'department' and target_dept_id != user_dept_id:
                    # For department-level, must be in same department
                    # Check if the target department is a child of user's department
                    from employees.models import Department
                    try:
                        target_dept = Department.objects.get(id=target_dept_id)
                        # If parent_department feature exists, check it
                        if hasattr(target_dept, 'parent') and target_dept.parent_id == user_dept_id:
                            # Allow access to child departments
                            pass
                        else:
                            logger.info(f"User {request.user.username} denied: department access trying to access department {target_dept_id}")
                            return JsonResponse(
                                {"detail": "You can only access departments in your department hierarchy"},
                                status=403
                            )
                    except Department.DoesNotExist:
                        return JsonResponse({"detail": "Department not found"}, status=404)
            
            # Log the access
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type=f"department_{action_type}_access",
                    performed_by=request.user,
                    company=getattr(request.user, 'company', None),
                    details={
                        'access_level': access_level,
                        'department_id': target_dept_id,
                        'allowed': True
                    }
                )
            except Exception as e:
                logger.error(f"Error logging department access: {e}")
            
            # If we got here, access is granted
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator

def position_access_control(action_type):
    """
    Decorator to control position-related actions based on user's access level.
    
    This decorator ensures users can only perform actions on positions based on their
    access level (self, team, department, company).
    
    Args:
        action_type: The type of action ('view', 'add', 'edit', 'delete')
        
    Usage:
        @position_access_control('add')
        def create_position(request):
            # User can only add positions if they have proper access
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required"}, status=401)
                
            # Superadmins bypass access control
            if request.user.is_superuser or request.user.role == 'superadmin':
                return view_func(request, *args, **kwargs)
            
            # Check for specific permission required for this action
            permission_name = f"tech_{'manage' if action_type != 'view' else 'view'}_position"
            if not request.user.has_permission(permission_name):
                logger.info(f"User {request.user.username} denied access: missing permission {permission_name}")
                return JsonResponse(
                    {"detail": f"You don't have permission to {action_type} positions"},
                    status=403
                )
            
            # Get access level from request (set by middleware)
            if not hasattr(request, 'access_level'):
                logger.error(f"Access level not set for user {request.user.username}")
                return JsonResponse({"detail": "Access level not available"}, status=500)
            
            access_info = request.access_level
            access_level = access_info.get('level', 'self')
            
            # For 'add', 'edit', 'delete' actions, check access level
            if action_type in ('add', 'edit', 'delete'):
                # Users with 'self' access can't create or modify positions
                if access_level == 'self':
                    logger.info(f"User {request.user.username} denied: self access trying to {action_type} position")
                    return JsonResponse(
                        {"detail": f"You don't have permission to {action_type} positions with self access level"},
                        status=403
                    )
                
                # For team-level users, additional restrictions may apply
                # e.g., only create positions for their teams
                
                # Department and company level users can manage positions for their scope
            
            # Log the access
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type=f"position_{action_type}_access",
                    performed_by=request.user,
                    company=getattr(request.user, 'company', None),
                    details={
                        'access_level': access_level,
                        'allowed': True
                    }
                )
            except Exception as e:
                logger.error(f"Error logging position access: {e}")
            
            # If we got here, access is granted
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator

def position_level_access_control(action_type):
    """
    Decorator to control position level-related actions based on user's access level.
    
    Args:
        action_type: The type of action ('view', 'add', 'edit', 'delete')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required"}, status=401)
                
            # Superadmins bypass access control
            if request.user.is_superuser or request.user.role == 'superadmin':
                return view_func(request, *args, **kwargs)
            
            # Check for specific permission required for this action
            permission_name = f"tech_{'manage' if action_type != 'view' else 'view'}_position_level"
            if not request.user.has_permission(permission_name):
                logger.info(f"User {request.user.username} denied access: missing permission {permission_name}")
                return JsonResponse(
                    {"detail": f"You don't have permission to {action_type} position levels"},
                    status=403
                )
            
            # Get access level from request (set by middleware)
            if not hasattr(request, 'access_level'):
                logger.error(f"Access level not set for user {request.user.username}")
                return JsonResponse({"detail": "Access level not available"}, status=500)
            
            access_info = request.access_level
            access_level = access_info.get('level', 'self')
            
            # For 'add', 'edit', 'delete' actions, check access level
            if action_type in ('add', 'edit', 'delete'):
                # Users with 'self' access can't create or modify position levels
                if access_level == 'self':
                    logger.info(f"User {request.user.username} denied: self access trying to {action_type} position level")
                    return JsonResponse(
                        {"detail": f"You don't have permission to {action_type} position levels with self access level"},
                        status=403
                    )
            
            # Log the access
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type=f"position_level_{action_type}_access",
                    performed_by=request.user,
                    company=getattr(request.user, 'company', None),
                    details={
                        'access_level': access_level,
                        'allowed': True
                    }
                )
            except Exception as e:
                logger.error(f"Error logging position level access: {e}")
            
            # If we got here, access is granted
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator