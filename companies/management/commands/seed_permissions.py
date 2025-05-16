from django.core.management.base import BaseCommand
from companies.models import Permission, Company, Role

class Command(BaseCommand):
    help = 'Creates predefined roles and permissions for companies'

    def handle(self, *args, **kwargs):
        # Initialize counters at the beginning
        created_permissions = 0
        updated_permissions = 0
        
        # Check if companies exist
        try:
            tech_company = Company.objects.filter(type=1)  # Tech company
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR("Tech company not found. Please create a company with type=1 first."))
            return
            
        try:
            educational_company = Company.objects.filter(type=2)  # Educational company
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR("Educational company not found. Please create a company with type=2 first."))
            return
            
        # Predefined Permissions for Tech and Educational companies
        permissions_data = [
            # --- Tech Company Permissions ---
            {"name": "Add Employee", "code": "tech_add_employee", "category": "employee", "company_type": "tech"},
            {"name": "View Employees", "code": "tech_view_employee", "category": "employee", "company_type": "tech"},
            {"name": "Edit Employee", "code": "tech_edit_employee", "category": "employee", "company_type": "tech"},
            {"name": "Deactivate Employee", "code": "tech_deactivate_employee", "category": "employee", "company_type": "tech"},
            {"name": "Add Department", "code": "tech_add_department", "category": "department", "company_type": "tech"},
            {"name": "View Departments", "code": "tech_view_departments", "category": "department", "company_type": "tech"},
            {"name": "Edit Departments", "code": "tech_edit_departments", "category": "department", "company_type": "tech"},
            {"name": "Manage Holidays", "code": "tech_manage_holidays", "category": "holidays", "company_type": "tech"},
            {"name": "View Attendance", "code": "tech_view_attendance", "category": "attendance", "company_type": "tech"},
            {"name": "Override Attendance", "code": "tech_override_attendance", "category": "attendance", "company_type": "tech"},
            {"name": "Apply Leave", "code": "tech_apply_leave", "category": "leaves", "company_type": "tech"},
            {"name": "Approve Leaves", "code": "tech_approve_leave", "category": "leaves", "company_type": "tech"},
            {"name": "View Leave Stats", "code": "tech_view_leave_stats", "category": "leaves", "company_type": "tech"},
            {"name": "Create Shift", "code": "tech_create_shift", "category": "shifts", "company_type": "tech"},
            {"name": "Assign Shift", "code": "tech_assign_shift", "category": "shifts", "company_type": "tech"},
            {"name": "View Shift Schedule", "code": "tech_view_shift", "category": "shifts", "company_type": "tech"},
            {"name": "Enable Round-Robin", "code": "tech_enable_rr", "category": "round_robin", "company_type": "tech"},
            {"name": "Manual RR Trigger", "code": "tech_manual_rr", "category": "round_robin", "company_type": "tech"},
            {"name": "Configure SMTP", "code": "tech_configure_smtp", "category": "notifications", "company_type": "tech"},
            {"name": "View Dashboard Reports", "code": "tech_view_reports", "category": "reports", "company_type": "tech"},
            {"name": "Download Reports", "code": "tech_download_reports", "category": "reports", "company_type": "tech"},
            {"name": "View Audit Logs", "code": "tech_view_audit_logs", "category": "audit", "company_type": "tech"},
            {"name": "Edit Company Policies", "code": "tech_edit_policies", "category": "company", "company_type": "tech"},
            {"name": "Add Position", "code": "tech_add_position", "category": "company", "company_type": "tech"},
            {"name": "Create Role", "code": "tech_create_role", "category": "company", "company_type": "tech"},
            {"name": "Create Position Level", "code": "tech_create_position_level", "category": "company", "company_type": "tech"},

            # --- Educational Company Permissions ---
            {"name": "Add Faculty", "code": "edu_add_faculty", "category": "faculty", "company_type": "educational"},
            {"name": "View Faculty", "code": "edu_view_faculty", "category": "faculty", "company_type": "educational"},
            {"name": "Edit Faculty", "code": "edu_edit_faculty", "category": "faculty", "company_type": "educational"},
            {"name": "Deactivate Faculty", "code": "edu_deactivate_faculty", "category": "faculty", "company_type": "educational"},
            {"name": "Add Department", "code": "edu_add_department", "category": "department", "company_type": "educational"},
            {"name": "View Department", "code": "edu_view_departments", "category": "department", "company_type": "educational"},
            {"name": "Edit Department", "code": "edu_edit_departments", "category": "department", "company_type": "educational"},
            {"name": "Manage Academic Calendar", "code": "edu_manage_academic_calendar", "category": "holidays", "company_type": "educational"},
            {"name": "View Attendance", "code": "edu_view_attendance", "category": "attendance", "company_type": "educational"},
            {"name": "Override Attendance", "code": "edu_override_attendance", "category": "attendance", "company_type": "educational"},
            {"name": "Apply Leave", "code": "edu_apply_leave", "category": "leaves", "company_type": "educational"},
            {"name": "Approve Leaves", "code": "edu_approve_leave", "category": "leaves", "company_type": "educational"},
            {"name": "View Leave Stats", "code": "edu_view_leave_stats", "category": "leaves", "company_type": "educational"},
            {"name": "Create Timetable", "code": "edu_create_timetable", "category": "scheduling", "company_type": "educational"},
            {"name": "Assign Timetable", "code": "edu_assign_timetable", "category": "scheduling", "company_type": "educational"},
            {"name": "View Timetable", "code": "edu_view_timetable", "category": "scheduling", "company_type": "educational"},
            {"name": "Enable Substitution Rotation", "code": "edu_enable_sub_rotation", "category": "round_robin", "company_type": "educational"},
            {"name": "Manual Substitution Trigger", "code": "edu_manual_sub_trigger", "category": "round_robin", "company_type": "educational"},
            {"name": "Configure Academic Alerts", "code": "edu_configure_alerts", "category": "notifications", "company_type": "educational"},
            {"name": "View Academic Reports", "code": "edu_view_reports", "category": "reports", "company_type": "educational"},
            {"name": "Download Reports", "code": "edu_download_reports", "category": "reports", "company_type": "educational"},
            {"name": "View Faculty Audit Logs", "code": "edu_view_audit_logs", "category": "audit", "company_type": "educational"},
            {"name": "Edit Academic Policies", "code": "edu_edit_policies", "category": "institute", "company_type": "educational"},
        ]

        for perm in permissions_data:
            code = perm['code']
            company_type = perm['company_type']
            
            try:
                # Try to get existing permission
                permission = Permission.objects.get(code=code, company_type=company_type)
                
                # Update other fields
                for key, value in perm.items():
                    if key not in ['code', 'company_type']:  # Don't update unique identifiers
                        setattr(permission, key, value)
                permission.save()
                updated_permissions += 1
                
            except Permission.DoesNotExist:
                # Create new permission
                try:
                    Permission.objects.create(**perm)
                    created_permissions += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error creating permission {code}: {str(e)}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error with permission {code}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"✅ {created_permissions} permissions created, {updated_permissions} permissions updated."))

        # # Predefined Roles for Tech and Educational companies
        # roles_data = [
        #     {'name': 'Company Admin', 'company': tech_company, 'is_default': True},
        #     {'name': 'CEO', 'company': tech_company, 'is_default': False},
        #     {'name': 'CTO', 'company': tech_company, 'is_default': False},
        #     {'name': 'HR Manager', 'company': tech_company, 'is_default': False},
        #     {'name': 'Department Manager', 'company': tech_company, 'is_default': False},
        #     {'name': 'Employee', 'company': tech_company, 'is_default': False},
        #     {'name': 'Intern', 'company': tech_company, 'is_default': False},

            
        #     {'name': 'Company Admin', 'company': educational_company, 'is_default': True},
        #     {'name': 'Faculty', 'company': educational_company, 'is_default': False},
        #     {'name': 'Department Head', 'company': educational_company, 'is_default': False},
        #     {'name': 'HR Manager', 'company': educational_company, 'is_default': False},
        #     {'name': 'Department Manager', 'company': educational_company, 'is_default': False},
        #     {'name': 'Student', 'company': educational_company, 'is_default': False},
        #     {'name': 'Intern', 'company': educational_company, 'is_default': False},
        # ]

        # created_roles = 0
        # for role in roles_data:
        #     try:
        #         _, created = Role.objects.get_or_create(
        #             name=role['name'],
        #             company=role['company'],
        #             defaults={'is_default': role['is_default']}
        #         )
        #         if created:
        #             created_roles += 1
        #     except Exception as e:
        #         self.stdout.write(self.style.ERROR(f"Error creating role {role['name']}: {str(e)}"))

        # self.stdout.write(self.style.SUCCESS(f"✅ {created_roles} roles created."))
        
        # Assign permissions to default roles
        # self.assign_permissions_to_roles(tech_company, educational_company)
        
    # def assign_permissions_to_roles(self, tech_company, educational_company):
    #     """Assign permissions to default roles"""
    #     try:
    #         # Get roles
    #         tech_admin = Role.objects.get(name='Company Admin', company=tech_company)
    #         tech_hr = Role.objects.get(name='HR Manager', company=tech_company)
    #         tech_dept_manager = Role.objects.get(name='Department Manager', company=tech_company)
    #         tech_employee = Role.objects.get(name='Employee', company=tech_company)
            
    #         edu_admin = Role.objects.get(name='Company Admin', company=educational_company)
    #         edu_faculty = Role.objects.get(name='Faculty', company=educational_company)
    #         edu_dept_head = Role.objects.get(name='Department Head', company=educational_company)
            
    #         # Assign all tech permissions to tech admin
    #         tech_permissions = Permission.objects.filter(company_type='tech')
    #         tech_admin.permissions.add(*tech_permissions)
            
    #         # Assign HR permissions to HR Manager
    #         hr_permissions = Permission.objects.filter(company_type='tech', category__in=['employee', 'leaves', 'attendance'])
    #         tech_hr.permissions.add(*hr_permissions)
            
    #         # Assign department permissions to department manager
    #         dept_permissions = Permission.objects.filter(company_type='tech', category__in=['department', 'shifts', 'attendance'])
    #         tech_dept_manager.permissions.add(*dept_permissions)
            
    #         # Assign basic permissions to employee
    #         employee_permissions = Permission.objects.filter(company_type='tech', code__in=['tech_apply_leave', 'tech_view_shift'])
    #         tech_employee.permissions.add(*employee_permissions)
            
    #         # Assign all educational permissions to educational admin
    #         edu_permissions = Permission.objects.filter(company_type='educational')
    #         edu_admin.permissions.add(*edu_permissions)
            
    #         # Assign faculty permissions
    #         faculty_permissions = Permission.objects.filter(company_type='educational', code__in=['edu_apply_leave', 'edu_view_timetable'])
    #         edu_faculty.permissions.add(*faculty_permissions)
            
    #         # Assign department head permissions
    #         dept_head_permissions = Permission.objects.filter(company_type='educational', category__in=['department', 'faculty', 'scheduling'])
    #         edu_dept_head.permissions.add(*dept_head_permissions)
            
    #         self.stdout.write(self.style.SUCCESS("✅ Permissions assigned to roles successfully."))
            
    #     except Role.DoesNotExist as e:
    #         self.stdout.write(self.style.ERROR(f"Error assigning permissions to roles: {str(e)}"))
    #     except Exception as e:
    #         self.stdout.write(self.style.ERROR(f"Unexpected error assigning permissions to roles: {str(e)}"))