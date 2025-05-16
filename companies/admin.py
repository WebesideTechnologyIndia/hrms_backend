from django.contrib import admin
from .models import Permission, Company, Role

class PermissionAdmin(admin.ModelAdmin):
    list_display = ('id','code', 'name', 'category', 'company_type')
    list_filter = ('category', 'company_type')
    search_fields = ('code', 'name')

class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_default')
    list_filter = ('company', 'is_default')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)  # Easier management of permissions

class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission', 'allowed')
    list_filter = ('allowed', 'permission')
    search_fields = ('user__username', 'permission__code')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        
        # Exclude UserPermission records for Super Admin users (if necessary)
        if request.user.role != 'superadmin':
            queryset = queryset.filter(user__role='superadmin')  # Only show Non-Super Admin permissions
        return queryset
    
    def has_change_permission(self, request, obj=None):
        # Prevent changes to Super Admin permissions
        if obj and obj.user.role == 'superadmin':
            return False
        return super().has_change_permission(request, obj)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'user_limit', 'status', 'subscription_plan', 'subscription_end')
    list_filter = ('type', 'status', 'subscription_plan')
    search_fields = ('name', 'domain')

admin.site.register(Permission, PermissionAdmin)
admin.site.register(Role, RoleAdmin)


#  teams/admin.py
from django.contrib import admin
from .models import Team, TeamMember

class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    autocomplete_fields = ['employee']

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'department', 'director', 'manager', 'created_at')
    list_filter = ('company', 'department')
    search_fields = ('name', 'director__username', 'manager__username')
    autocomplete_fields = ['company', 'department', 'director', 'manager']
    inlines = [TeamMemberInline]

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('employee', 'team', 'added_at')
    list_filter = ('team',)
    search_fields = ('employee__username', 'team__name')
    autocomplete_fields = ['employee', 'team']