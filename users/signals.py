# users/signals.py

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.db import transaction
from django.contrib.auth import get_user_model
from companies.models import Role  # Adjust this import based on your project structure
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(m2m_changed, sender=Role.permissions.through)
def remove_permissions_from_company_users(sender, instance, action, pk_set, **kwargs):
    """
    When permissions are removed from a role, remove the same permissions
    from all users belonging to the role's company.
    """
    if action == 'post_remove' and pk_set:
        try:
            with transaction.atomic():
                role = instance  # The role from which permissions were removed
                company = role.company
                
                if not company:
                    return
                
                removed_permissions = pk_set
                
                # Get all users belonging to this company
                company_users = User.objects.filter(company=company)
                logger.info(f"Removing permissions {pk_set} from {company_users.count()} users of company {company.name}")
                
                # Remove permissions from all company users
                for user in company_users:
                    user.permissions.remove(*removed_permissions)
                    logger.info(f"Removed permissions from user: {user.username}")
                
        except Exception as e:
            logger.error(f"Error removing permissions from company users: {str(e)}")

# Keep your existing admin signal handler
@receiver(m2m_changed, sender=User.permissions.through)
def sync_admin_permissions_to_roles(sender, instance, action, pk_set, **kwargs):
    """
    Jab company admin ke permissions change hote hain, to us company ke
    sabhi roles ko update karta hai
    """
    if action in ['post_remove', 'post_clear'] and instance.role == 'companyadmin':
        try:
            with transaction.atomic():
                company = instance.company
                if not company:
                    logger.warning(f"User {instance.username} has no company assigned")
                    return
                
                # Admin ke current permissions
                admin_permission_ids = set(instance.permissions.values_list('id', flat=True))
                
                # Company ke saare roles
                company_roles = Role.objects.filter(company=company)
                
                for role in company_roles:
                    # Role ke permissions mein se wo hata do jo admin ke paas nahi hain
                    role_permission_ids = set(role.permissions.values_list('id', flat=True))
                    permissions_to_remove = role_permission_ids - admin_permission_ids
                    
                    if permissions_to_remove:
                        role.permissions.remove(*permissions_to_remove)
                        logger.info(f"Removed {len(permissions_to_remove)} permissions from role '{role.name}'")
                
        except Exception as e:
            logger.error(f"Error syncing permissions to roles: {str(e)}")