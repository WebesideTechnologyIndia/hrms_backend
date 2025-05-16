# companies/utils.py

from employees.models import EmployeeProfile

def has_permission(employee: EmployeeProfile, permission_code: str) -> bool:
    if not employee.role:
        return False
    return employee.role.permissions.filter(permission__code=permission_code, allowed=True).exists()
