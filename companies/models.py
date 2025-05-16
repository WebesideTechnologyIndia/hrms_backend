# companies/models.py
from django.conf import settings
from django.db import models
from datetime import date

class Company(models.Model):
    COMPANY_TYPES = (
        (1, 'Tech'),
        (2, 'Educational'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    SUBSCRIPTION_PLANS = (
        ('free', 'Free'),
        ('paid', 'Paid'),
    )

    name = models.CharField(max_length=255, unique=True)
    type = models.IntegerField(choices=COMPANY_TYPES, default=1)
    user_limit = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    # Address-related fields
    address_line = models.TextField(blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    domain = models.CharField(max_length=255, blank=True, null=True)

    # Subscription fields
    subscription_plan = models.CharField(max_length=10, choices=SUBSCRIPTION_PLANS, default='free')
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def is_subscription_active(self):
        if self.subscription_plan == 'free':
            return True
        if self.subscription_end:
            return date.today() <= self.subscription_end
        return False

    @property
    def remaining_days(self):
        if self.subscription_plan == 'free':
            return None  # Not applicable
        if self.subscription_end and date.today() <= self.subscription_end:
            return (self.subscription_end - date.today()).days
        return 0  # Already expired


class Permission(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    company_type = models.CharField(max_length=20, choices=(("tech", "Tech"), ("educational", "Educational")))
    category = models.CharField(max_length=50, default="general")

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='roles')
    is_default = models.BooleanField(default=False)
    permissions = models.ManyToManyField('companies.Permission', blank=True, related_name="roles")
    
    # Use string references to avoid circular imports
    department = models.ForeignKey('employees.Department', on_delete=models.CASCADE, related_name='roles', null=True)
    position = models.ForeignKey('employees.Position', on_delete=models.CASCADE, related_name='roles', null=True)
    position_level = models.ForeignKey('employees.PositionLevel', on_delete=models.CASCADE, related_name='roles', null=True)
    
    # Access level controls what data the role can access
    ACCESS_LEVEL_CHOICES = [
        ('self', 'Self Only'),
        ('department', 'Department'),
        ('team', 'Team'),
        ('company', 'Company-wide'),
    ]
    access_level = models.CharField(
        max_length=20, 
        choices=ACCESS_LEVEL_CHOICES,
        default='department',
        help_text="Determines the scope of data this role can access"
    )
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"
    
    class Meta:
        unique_together = ('name', 'company')

# teams/models.py (updated)
from django.db import models
from companies.models import Company
from django.conf import settings

class TeamCategory(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='team_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('name', 'company')
        verbose_name_plural = 'Team Categories'
    
    def __str__(self):
        return self.name

class Team(models.Model):
    name = models.CharField(max_length=255)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='teams')
    # Update to use the new TeamCategory model
    category = models.ForeignKey('companies.TeamCategory', on_delete=models.SET_NULL, 
                               null=True, blank=True, related_name='teams')
    # Keep this for backward compatibility
    category_type = models.CharField(max_length=50, null=True, blank=True)
    department = models.ForeignKey('employees.Department', on_delete=models.SET_NULL, 
                                  null=True, blank=True, related_name='teams')
    director = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                null=True, related_name='directed_teams')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                               null=True, related_name='managed_teams')
                               # Add this field to the Team model in teams/models.py
    team_leader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                              null=True, related_name='led_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class TeamMember(models.Model):
    team = models.ForeignKey('companies.Team', on_delete=models.CASCADE, related_name='members')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                                related_name='team_memberships')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('team', 'employee')
    
    def __str__(self):
        return f"{self.employee.username} in {self.team.name}"