from django import forms
from .models import Role
from employees.models import Position

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'is_default']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_default'].label = "Make this the default role for new users"
        self.fields['is_default'].help_text = "Only one role can be default"

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['name', 'role']