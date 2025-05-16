from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings  # Add this import
from companies.models import Permission,Role
from employees.models import Position, Department, PositionLevel 

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
# from companies.models import Permission, Role
# from employees.models import Position, Department, PositionLevel 

class User(AbstractUser):
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('companyadmin', 'Company Admin'),
        ('employee', 'Employee'),
    )
    
    ACCESS_LEVEL_CHOICES = (
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('basic', 'Basic'),
        ('custom', 'Custom'),
    )
    
    # Role and Position-based fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    position = models.ForeignKey('employees.Position', on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    department = models.ForeignKey('employees.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    positional_level = models.ForeignKey('employees.PositionLevel', on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    user_role = models.ForeignKey('companies.Role', on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    
    # Added access_level field
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='basic')
    # 
    is_active_employee = models.BooleanField(default=True)
   
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    permissions = models.ManyToManyField('companies.Permission', blank=True, related_name="users")
    
    app_running = models.BooleanField(default=False)
    last_status_update = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.username} ({self.role})"
    
    def can_login(self):
        """Check if user can login (both user and company are active)"""
        return self.is_active and self.is_active_employee and self.company and self.company.status == 'active'
    
    def get_all_permissions(self):
        """Get all permissions from user's direct permissions and position's role permissions"""
        direct_permissions = set(self.permissions.all())
        
        if self.position:
            # Check if position has a related role (using roles or whatever field you have)
            role_permissions = set()
            if hasattr(self.position, 'roles'):  # Check if 'roles' exists on Position
                for role in self.position.roles.all():  # Assuming roles is a related field with many roles
                        role_permissions.update(role.permissions.all())
            return direct_permissions.union(role_permissions)
        
        return direct_permissions
    
    # models.py - Add to User model
    def is_active_company_user(self):
        """Check if user belongs to an active company"""
        return self.company and self.company.status == 'active'
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission by code"""
        if self.permissions.filter(code=permission_code).exists():
            return True
        
        if self.position and self.position.role and self.position.role.permissions.filter(code=permission_code).exists():
            return True
        
        return False
    # Add this method to your User model
    def is_monitoring_app_running(self):
        """Check if user's monitoring app is running and recently updated"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.app_running:
            return False
            
        # Check if last update was within 15 minutes
        time_threshold = timezone.now() - timedelta(minutes=15)
        return self.last_status_update and self.last_status_update > time_threshold
# # activities/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class ActivityLog(models.Model):
    # Action types
    ACTION_TYPES = (
        ('company_created', _('Company Created')),
        ('company_updated', _('Company Updated')),
        ('company_status_changed', _('Company Status Changed')),
        ('admin_assigned', _('Admin Role Assigned')),
        ('user_created', _('User Created')),
        ('user_updated', _('User Updated')),
        ('user_login', _('User Login')),
        ('user_logout', _('User Logout')),
        ('failed_login', _('Failed Login Attempt')),
        ('employee_status_changed', _('Employee Status Changed')),
        # Add more action types as needed
    )
    
    # Fields
    timestamp = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    
    # Related models
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_activities'
    )
    
    # Store the role separately in case the user is deleted or role changes
    performed_by_role = models.CharField(max_length=50, null=True, blank=True)
    
    # Company can be null for system-wide actions
    company = models.ForeignKey(
        'companies.Company',  # Use string to avoid circular import
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    
    # Store additional details as JSON
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Activity Log')
        verbose_name_plural = _('Activity Logs')
    
    def __str__(self):
        action = dict(self.ACTION_TYPES).get(self.action_type, self.action_type)
        user = self.performed_by.username if self.performed_by else 'System'
        return f"{action} by {user} at {self.timestamp}"