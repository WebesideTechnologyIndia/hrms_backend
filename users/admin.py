from django import forms
from django.contrib import admin
from .models import User
from companies.models import Permission

class UserPermissionForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    # Only include permissions field for non-superadmin users
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = (
            'username', 'email', 'role', 'company', 
            'position', 'department', 'is_active', 'is_active_employee', 'positional_level', 
            'user_role', 'password', 'confirm_password', 'app_running', 'last_status_update'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # For existing users, check role
        if self.instance and self.instance.pk:
            user_role = self.instance.role
            
            # For superadmin, remove permissions field
            if user_role == 'superadmin':
                if 'permissions' in self.fields:
                    self.fields.pop('permissions')
            # For others with a company, filter permissions by company type
            elif self.instance.company and 'permissions' in self.fields:
                company_type = self.instance.company.type
                company_category = 'tech' if company_type == 1 else 'educational'
                self.fields['permissions'].queryset = Permission.objects.filter(company_type=company_category.lower())
                
                # Add current permissions to initial data
                self.initial['permissions'] = self.instance.permissions.all()
        
        # Make app_running and last_status_update readonly in the form
        if 'app_running' in self.fields:
            self.fields['app_running'].widget.attrs['readonly'] = True
        if 'last_status_update' in self.fields:
            self.fields['last_status_update'].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')

        if password:
            user.set_password(password)

        if commit:
            user.save()

            # Assign permissions only if not super admin and permissions field exists
            if user.role != "superadmin" and 'permissions' in self.cleaned_data:
                permissions = self.cleaned_data.get('permissions')
                user.permissions.set(permissions)  # Directly set ManyToMany relation

        return user

class CustomUserAdmin(admin.ModelAdmin):
    form = UserPermissionForm
    list_display = ('id', 'username', 'email', 'role', 'position', 'company', 'is_staff', 'is_active', 'is_active_employee', 'app_status', 'permissions_display')
    list_filter = ('role', 'is_active', 'is_active_employee', 'company', 'app_running')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('app_running', 'last_status_update')

    def get_fieldsets(self, request, obj=None):
        if obj and obj.role == 'superadmin':
            return [
                (None, {'fields': ('username', 'email', 'role', 'is_active', 'password', 'confirm_password')}),
            ]
        elif obj:  # Existing user
            return [
                ('User Information', {'fields': (
                    'username', 'email', 'role', 'is_active', 'is_active_employee', 'company', 
                    'position', 'department', 'positional_level', 'user_role', 
                    'password', 'confirm_password'
                )}),
                ('Permissions', {'fields': ('permissions',)}),
                ('Monitoring App Status', {'fields': ('app_running', 'last_status_update')}),
            ]
        else:  # New user
            return [
                ('User Information', {'fields': (
                    'username', 'email', 'role', 'is_active', 'is_active_employee', 'company', 
                    'position', 'department', 'positional_level', 'user_role', 
                    'password', 'confirm_password'
                )}),
            ]

    def app_status(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        
        if not obj.app_running:
            return "Not Running"
        
        if not obj.last_status_update:
            return "No Updates"
            
        time_threshold = timezone.now() - timedelta(minutes=15)
        if obj.last_status_update > time_threshold:
            return "Running"
        else:
            return "Inactive"
    
    app_status.short_description = 'App Status'

    def permissions_display(self, obj):
        if obj.role == 'superadmin':
            return "All Permissions (Super Admin)"
        
        company = obj.company
        if not company:
            return "No Company Assigned"
        
        user_permissions = obj.permissions.all()
        if not user_permissions.exists():
            return "No permissions assigned"
        
        return ", ".join([p.name for p in user_permissions])

    permissions_display.short_description = 'Permissions'

admin.site.register(User, CustomUserAdmin)