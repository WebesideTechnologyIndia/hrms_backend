# middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

class AccessLevelMiddleware(MiddlewareMixin):
    """
    Middleware to check and add user's access level information to the request.
    This will be available to all views for access control.
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip for non-authenticated users or for certain exempt paths
        if not request.user.is_authenticated:
            return None
            
        # Add access level info to the request
        self._add_access_level_info(request)
        
        # Check if view requires specific permissions
        # This can be added to views using a decorator that sets view_func.required_permissions
        if hasattr(view_func, 'required_permissions'):
            if not self._check_permissions(request, view_func.required_permissions):
                return JsonResponse(
                    {"detail": "You do not have permission to perform this action."},
                    status=403
                )
        
        return None
    
    def _add_access_level_info(self, request):
        """
        Adds access level information to the request object for use in views.
        Access levels:
        - self: Only see/manage own data
        - team: Can see/manage team members' data
        - department: Can see/manage department members' data
        - company: Can see/manage all company data
        """
        user = request.user
        
        # Default access level - most restrictive
        access_info = {
            'level': 'self',  # Default to self access
            'department_id': None,
            'employee_id': user.id,
            'company_id': getattr(user.company, 'id', None) if hasattr(user, 'company') else None,
            'team_ids': []
        }
        
        try:
            # Get user's department ID if available
            if hasattr(user, 'department') and user.department:
                access_info['department_id'] = user.department.id
            
            # Get user's role from user_role field
            role = getattr(user, 'user_role', None)
            
            if role:
                # Set access level from role
                access_info['level'] = role.access_level
                
                # If team leader, get team member IDs
                if role.access_level == 'team':
                    # Try to get teams where user is manager
                    managed_teams = getattr(user, 'managed_teams', None)
                    if managed_teams and managed_teams.exists():
                        team_members = []
                        # Collect all team members from all teams managed by this user
                        for team in managed_teams.all():
                            team_members.extend(
                                team.members.values_list('employee_id', flat=True)
                            )
                        access_info['team_ids'] = list(set(team_members))  # Remove duplicates
            
            logger.debug(f"Access level for user {user.username}: {access_info['level']}")
            
        except Exception as e:
            logger.error(f"Error determining access level for user {user.username}: {str(e)}")
            # Fall back to self access on error
            access_info['level'] = 'self'
        
        # Store access info in request for use in views
        request.access_level = access_info
    
    def _check_permissions(self, request, required_permissions):
        """
        Checks if the user has the required permissions.
        
        Args:
            request: The HttpRequest object
            required_permissions: List of permission codes required for the view
            
        Returns:
            Boolean indicating if user has permission
        """
        # If not authenticated, no permissions
        if not request.user.is_authenticated:
            return False
            
        # Get user permissions
        user_permissions = getattr(request.user, 'get_permissions', lambda: [])()
        user_permission_codes = [p.code for p in user_permissions]
        
        # Check each required permission
        for permission in required_permissions:
            if permission not in user_permission_codes:
                logger.debug(f"User {request.user.username} missing required permission: {permission}")
                return False
                
        return True