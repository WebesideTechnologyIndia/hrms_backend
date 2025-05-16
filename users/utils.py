# utils.py
def apply_access_level_filter(queryset, user, field_name='department_id'):
    """
    Apply access level filtering to any queryset based on user's role access level.
    
    Args:
        queryset: The queryset to filter
        user: The user requesting the data
        field_name: Field to filter by for department access (default: department_id)
        
    Returns:
        Filtered queryset according to user's access level
        
    Usage:
        def get_employees(request):
            queryset = User.objects.filter(role='employee')
            filtered_queryset = apply_access_level_filter(queryset, request.user)
            # Continue with serialization, etc.
    """
    if not user.is_authenticated:
        return queryset.none()
    
    # Handle superuser case
    if user.is_superuser:
        return queryset
    
    # Get user's role
    role = getattr(user, 'user_role', None)
    if not role:
        # Default to self-only access if no role assigned
        return queryset.filter(id=user.id)
    
    access_level = role.access_level
    
    # Apply filters based on access level
    if access_level == 'self':
        # Self access - only show user's own data
        return queryset.filter(id=user.id)
        
    elif access_level == 'department':
        # Department access - filter by user's department
        if user.department:
            filter_kwargs = {field_name: user.department.id}
            return queryset.filter(**filter_kwargs)
        else:
            # If user has no department, default to self-access
            return queryset.filter(id=user.id)
            
    elif access_level == 'team':
        # Team access - only show team members
        from teams.models import TeamMember
        
        # Get teams where user is manager
        managed_teams = user.managed_teams.all() if hasattr(user, 'managed_teams') else []
        
        if managed_teams:
            # Get all team members from those teams
            team_member_ids = TeamMember.objects.filter(
                team__in=managed_teams
            ).values_list('employee_id', flat=True)
            
            # Include user themselves
            team_member_ids = list(team_member_ids) + [user.id]
            
            return queryset.filter(id__in=team_member_ids)
        else:
            # No teams to manage, default to self-access
            return queryset.filter(id=user.id)
    
    # Company-wide access - return all results in the company
    if hasattr(queryset.model, 'company'):
        return queryset.filter(company=user.company)
    
    # Default - return original queryset (for company-wide access)
    return queryset


def check_access_level_permission(user, obj=None, field_name='department_id'):
    """
    Check if user has access to a specific object based on their access level.
    
    Args:
        user: The user requesting access
        obj: The object being accessed
        field_name: Field to check for department access
        
    Returns:
        Boolean indicating if access is allowed
        
    Usage:
        def get_employee_detail(request, employee_id):
            employee = User.objects.get(id=employee_id)
            if not check_access_level_permission(request.user, employee):
                return Response({"error": "Access denied"}, status=403)
            # Continue with serialization, etc.
    """
    if not user.is_authenticated:
        return False
    
    # Superusers always have access
    if user.is_superuser:
        return True
    
    # If no object specified, no access check needed
    if not obj:
        return True
    
    # Get user's role
    role = getattr(user, 'user_role', None)
    if not role:
        # Default to self-only access if no role assigned
        return obj.id == user.id
    
    access_level = role.access_level
    
    # Apply access level checks
    if access_level == 'self':
        # Self access - only own data
        return obj.id == user.id
        
    elif access_level == 'department':
        # Department access
        if user.department:
            # Check if object belongs to same department
            obj_department_id = getattr(obj, field_name, None)
            return obj_department_id == user.department.id
        else:
            # No department, default to self-access
            return obj.id == user.id
            
    elif access_level == 'team':
        # Team access - check if object is a team member
        from teams.models import TeamMember
        
        # Get teams where user is manager
        managed_teams = user.managed_teams.all() if hasattr(user, 'managed_teams') else []
        
        if managed_teams:
            # Check if object is a member of any team the user manages
            team_member_exists = TeamMember.objects.filter(
                team__in=managed_teams,
                employee_id=obj.id
            ).exists()
            
            # Also allow access to own data
            return team_member_exists or obj.id == user.id
        else:
            # No teams to manage, default to self-access
            return obj.id == user.id
    
    # Company-wide access - check company association
    if hasattr(obj, 'company') and hasattr(user, 'company'):
        return obj.company_id == user.company_id
    
    # Default - allow access (for company-wide access)
    return True