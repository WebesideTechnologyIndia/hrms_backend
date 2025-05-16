# activities/services.py
from .models import ActivityLog
import logging

# Set up logger
logger = logging.getLogger(__name__)

class ActivityLogger:
    @staticmethod
    def log_activity(action_type, performed_by, company=None, details=None):
        """
        Log an activity
        
        Args:
            action_type: Type of action from ActivityLog.ACTION_TYPES
            performed_by: User who performed the action
            company: Related company (can be None for system-wide actions)
            details: Dictionary containing action-specific details
        """
        try:
            if details is None:
                details = {}
                
            # Get the role of the user who performed the action
            performed_by_role = performed_by.role if performed_by else None
            
            # Create the activity log
            log = ActivityLog.objects.create(
                action_type=action_type,
                performed_by=performed_by,
                performed_by_role=performed_by_role,
                company=company,
                details=details
            )
            
            logger.info(f"Activity logged: {action_type} by {performed_by} for {company}")
            return log
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            # Re-raise the exception so it can be handled by the caller
            raise
    
    @staticmethod
    def log_company_created(performed_by, company, details=None):
        """Log when a company is created"""
        try:
            if details is None:
                details = {
                    'company_id': company.id,
                    'company_name': company.name,
                    'company_type': company.get_type_display() if hasattr(company, 'get_type_display') else str(getattr(company, 'type', 'Unknown')),
                    'user_limit': getattr(company, 'user_limit', 'Not specified')
                }
            return ActivityLogger.log_activity('company_created', performed_by, company, details)
        except Exception as e:
            logger.error(f"Error logging company creation: {e}")
            raise
    
    @staticmethod
    def log_company_updated(performed_by, company, changed_fields):
        """Log when a company is updated"""
        try:
            details = {
                'company_id': company.id,
                'company_name': company.name,
                'changed_fields': changed_fields
            }
            return ActivityLogger.log_activity('company_updated', performed_by, company, details)
        except Exception as e:
            logger.error(f"Error logging company update: {e}")
            raise
    
    @staticmethod
    def log_company_status_changed(performed_by, company, old_status, new_status):
        """Log when a company's status changes"""
        try:
            details = {
                'company_id': company.id,
                'company_name': company.name,
                'old_status': old_status,
                'new_status': new_status
            }
            return ActivityLogger.log_activity('company_status_changed', performed_by, company, details)
        except Exception as e:
            logger.error(f"Error logging company status change: {e}")
            raise
    
    @staticmethod
    def log_admin_assigned(performed_by, company, admin_user):
        """Log when an admin is assigned to a company"""
        try:
            details = {
                'company_id': company.id,
                'company_name': company.name,
                'admin_id': admin_user.id,
                'admin_username': admin_user.username
            }
            return ActivityLogger.log_activity('admin_assigned', performed_by, company, details)
        except Exception as e:
            logger.error(f"Error logging admin assignment: {e}")
            raise
    
    @staticmethod
    def log_user_created(performed_by, new_user, company=None):
        """Log when a user is created"""
        try:
            details = {
                'user_id': new_user.id,
                'username': new_user.username,
                'role': new_user.role
            }
            
            if company:
                details['company_id'] = company.id
                details['company_name'] = company.name
                
            return ActivityLogger.log_activity('user_created', performed_by, company, details)
        except Exception as e:
            logger.error(f"Error logging user creation: {e}")
            raise