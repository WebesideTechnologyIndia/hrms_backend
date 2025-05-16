import logging

logger = logging.getLogger(__name__)

class AccessLevelFilter:
    """
    Helper class to filter querysets based on user's access level.
    This enables consistent filtering across all views.
    """
    
    @staticmethod
    def filter_employees(queryset, request):
        """
        Filter employee queryset based on user's access level
        
        Args:
            queryset: The initial Employee queryset
            request: The HTTP request with access_level info
        
        Returns:
            Filtered queryset
        """
        if not hasattr(request, 'access_level'):
            logger.warning("Access level not set in request, no filtering applied")
            return queryset
            
        # Get access level information
        access_info = request.access_level
        access_level = access_info.get('level', 'self')
        user_id = access_info.get('employee_id')
        dept_id = access_info.get('department_id')
        team_ids = access_info.get('team_ids', [])
        
        # Apply filters based on access level
        if access_level == 'self':
            # Self access - only see themselves
            queryset = queryset.filter(user_id=user_id)
            
        elif access_level == 'team':
            # Team access - see members of their teams
            if team_ids:
                queryset = queryset.filter(user__department_id__in=team_ids + [dept_id])
            else:
                queryset = queryset.filter(user__department_id=dept_id)
                
        elif access_level == 'department':
            # Department access - see all in their department & sub-departments
            from employees.models import Department
            
            # Get all departments under user's department
            child_depts = []
            try:
                # Get immediate child departments
                child_depts = list(Department.objects.filter(parent_id=dept_id).values_list('id', flat=True))
                
                # For each child, also get their children (recursively if your structure is deep)
                # Note: For deep hierarchies, you might want to implement a more efficient approach
                for child_id in list(child_depts):  # Create a copy of the list for iteration
                    sub_children = Department.objects.filter(parent_id=child_id).values_list('id', flat=True)
                    child_depts.extend(sub_children)
            except Exception as e:
                logger.error(f"Error getting child departments: {e}")
            
            # Filter to include user's department and all child departments
            all_dept_ids = [dept_id] + child_depts
            queryset = queryset.filter(user__department_id__in=all_dept_ids)
        
        # For company access level, no filtering is needed
        
        return queryset
    
    @staticmethod
    def filter_departments(queryset, request):
        """
        Filter department queryset based on user's access level
        
        Args:
            queryset: The initial Department queryset
            request: The HTTP request with access_level info
        
        Returns:
            Filtered queryset
        """
        if not hasattr(request, 'access_level'):
            logger.warning("Access level not set in request, no filtering applied")
            return queryset
            
        # Get access level information
        access_info = request.access_level
        access_level = access_info.get('level', 'self')
        dept_id = access_info.get('department_id')
        team_ids = access_info.get('team_ids', [])
        
        # Apply filters based on access level
        if access_level == 'self':
            # Self access - only see own department
            queryset = queryset.filter(id=dept_id)
            
        elif access_level == 'team':
            # Team access - see their teams
            if team_ids:
                queryset = queryset.filter(id__in=team_ids + [dept_id])
            else:
                queryset = queryset.filter(id=dept_id)
                
        elif access_level == 'department':
            # Department access - see their department & sub-departments
            from employees.models import Department
            
            # First, include the user's own department
            ids_to_include = [dept_id]
            
            # Get all departments under user's department
            try:
                # Define a recursive function to get all descendants
                def get_children(parent_id):
                    children = Department.objects.filter(parent_id=parent_id).values_list('id', flat=True)
                    result = list(children)
                    for child_id in children:
                        result.extend(get_children(child_id))
                    return result
                
                # Get all descendants of the user's department
                child_departments = get_children(dept_id)
                ids_to_include.extend(child_departments)
            except Exception as e:
                logger.error(f"Error getting child departments: {e}")
            
            # Filter to include only the allowed departments
            queryset = queryset.filter(id__in=ids_to_include)
        
        # For company access level, no filtering is needed
        
        return queryset
    
    @staticmethod
    def filter_positions(queryset, request):
        """
        Filter position queryset based on user's access level
        
        Args:
            queryset: The initial Position queryset
            request: The HTTP request with access_level info
        
        Returns:
            Filtered queryset
        """
        # For positions, the access control is typically based on company-level
        # Since positions are shared across the company
        # But we could restrict based on departments if needed
        
        if not hasattr(request, 'access_level'):
            logger.warning("Access level not set in request, no filtering applied")
            return queryset
        
        # By default, return all positions in the company
        # You can implement more granular filtering if your business rules require it
        
        return queryset
    
    @staticmethod
    def filter_position_levels(queryset, request):
        """
        Filter position level queryset based on user's access level
        
        Args:
            queryset: The initial PositionLevel queryset
            request: The HTTP request with access_level info
        
        Returns:
            Filtered queryset
        """
        # Position levels are typically company-wide settings
        # Similar to positions, so we follow the same pattern
        
        if not hasattr(request, 'access_level'):
            logger.warning("Access level not set in request, no filtering applied")
            return queryset
        
        # By default, return all position levels in the company
        # You can implement more granular filtering if your business rules require it
        
        return queryset