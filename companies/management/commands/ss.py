# company/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Company, Permission, Role, Department, Position, PositionalLevel

# Define company structure templates
techORATE_STRUCTURE = {
    "Management": {
        "Manager": {
            "Mid-Level": ["Assistant Manager", "Operations Manager"],
            "Senior-Level": ["Senior Manager", "General Manager"]
        },
        "Executive": {
            "Junior-Level": ["Business Executive", "Client Coordinator"]
        }
    },
    "Development": {
        "Engineer": {
            "Junior-Level": ["Junior Developer"],
            "Mid-Level": ["Software Developer", "QA Engineer"],
            "Senior-Level": ["Tech Lead", "Senior Developer"]
        }
    },
    "Human Resources": {
        "HR Executive": {
            "Junior-Level": ["HR Intern"],
            "Mid-Level": ["HR Generalist"],
            "Senior-Level": ["HR Manager"]
        }
    },
    "Sales & Marketing": {
        "Executive": {
            "Junior-Level": ["Sales Intern", "Marketing Trainee"],
            "Mid-Level": ["Sales Executive", "Marketing Executive"],
            "Senior-Level": ["Sales Manager", "Digital Marketing Lead"]
        }
    },
    "IT & Support": {
        "Support Engineer": {
            "Junior-Level": ["IT Support Intern", "Helpdesk Technician"],
            "Mid-Level": ["System Administrator", "Network Engineer"],
            "Senior-Level": ["IT Manager", "Infrastructure Lead"]
        }
    }
}

EDUCATIONAL_STRUCTURE = {
    "Administration": {
        "Manager": {
            "Mid-Level": ["Office Coordinator", "Admission Officer"],
            "Senior-Level": ["Admin Head", "Principal"]
        },
        "Executive": {
            "Junior-Level": ["Admin Assistant", "Front Desk Executive"]
        }
    },
    "Teaching": {
        "Faculty": {
            "Junior-Level": ["Assistant Professor", "Lecturer"],
            "Mid-Level": ["Associate Professor", "Senior Lecturer"],
            "Senior-Level": ["Head of Department", "Dean"]
        }
    },
    "Student Affairs": {
        "Coordinator": {
            "Junior-Level": ["Activity Coordinator", "Student Assistant"],
            "Mid-Level": ["Academic Advisor", "Student Counselor"],
            "Senior-Level": ["Director of Student Affairs", "Head Counselor"]
        }
    },
    "Examination & Evaluation": {
        "Exam Officer": {
            "Junior-Level": ["Exam Clerk", "Evaluation Assistant"],
            "Mid-Level": ["Exam Coordinator", "Exam Data Analyst"],
            "Senior-Level": ["Controller of Examination", "Head of Evaluation"]
        }
    },
    "Library & Lab Support": {
        "Assistant": {
            "Entry-Level": ["Library Assistant", "Lab Assistant"],
            "Mid-Level": ["Catalog Manager", "Lab Technician"],
            "Senior-Level": ["Chief Librarian", "Lab Supervisor"]
        }
    }
}

# Define permissions by company type
TECH_PERMISSIONS = {
    # Employee Management
    'tech_add_employee': 'Add new employees to the system',
    'tech_view_employee': 'View employee details',
    'tech_edit_employee': 'Edit employee information',
    'tech_deactivate_employee': 'Deactivate employee accounts',
    
    # Department Management
    'tech_add_department': 'Create new departments',
    'tech_view_departments': 'View all departments',
    'tech_edit_departments': 'Modify department details',
    
    # Attendance Management
    'tech_view_attendance': 'View attendance records',
    'tech_override_attendance': 'Override attendance records',
    'tech_manage_holidays': 'Manage company holidays',
    
    # Leave Management
    'tech_apply_leave': 'Apply for leave',
    'tech_approve_leave': 'Approve leave requests',
    'tech_view_leave_stats': 'View leave statistics',
    
    # Shift Management
    'tech_create_shift': 'Create work shifts',
    'tech_assign_shift': 'Assign shifts to employees',
    'tech_view_shift': 'View shift schedules',
    
    # Reports & Analytics
    'tech_view_reports': 'View company reports',
    'tech_download_reports': 'Download reports',
    'tech_view_audit_logs': 'View system audit logs',
    
    # System Configuration
    'tech_edit_policies': 'Edit company policies',
    'tech_configure_smtp': 'Configure email settings',
    'tech_enable_automation': 'Enable workflow automation',
    
    # Organization Structure
    'tech_add_position': 'Add new positions',
    'tech_edit_position': 'Edit positions',
    'tech_add_level': 'Add positional levels',
    'tech_add_role': 'Add new roles',
}

EDU_PERMISSIONS = {
    # Faculty Management
    'edu_add_faculty': 'Add new faculty members',
    'edu_view_faculty': 'View faculty details',
    'edu_edit_faculty': 'Edit faculty information',
    'edu_deactivate_faculty': 'Deactivate faculty accounts',
    
    # Department Management
    'edu_add_department': 'Create new departments',
    'edu_view_departments': 'View all departments',
    'edu_edit_departments': 'Modify department details',
    
    # Academic Management
    'edu_manage_academic_calendar': 'Manage academic calendar',
    'edu_view_curriculum': 'View curriculum details',
    'edu_edit_curriculum': 'Edit curriculum',
    
    # Attendance Management
    'edu_view_attendance': 'View attendance records',
    'edu_override_attendance': 'Override attendance records',
    
    # Leave Management
    'edu_apply_leave': 'Apply for leave',
    'edu_approve_leave': 'Approve leave requests',
    'edu_view_leave_stats': 'View leave statistics',
    
    # Timetable Management
    'edu_create_timetable': 'Create class timetables',
    'edu_assign_timetable': 'Assign timetables',
    'edu_view_timetable': 'View timetables',
    'edu_enable_sub_rotation': 'Enable substitute rotation',
    'edu_manual_sub_trigger': 'Manually trigger substitution',
    
    # Student Management
    'edu_add_student': 'Add new students',
    'edu_view_student': 'View student details',
    'edu_edit_student': 'Edit student information',
    
    # Reports & Analytics
    'edu_view_reports': 'View institutional reports',
    'edu_download_reports': 'Download reports',
    'edu_view_audit_logs': 'View system audit logs',
    
    # System Configuration
    'edu_edit_policies': 'Edit institutional policies',
    'edu_configure_alerts': 'Configure system alerts',
}

# Define role permissions
ROLE_PERMISSIONS = {
    # techorate Roles
    "techorate": {
        "General Manager": [
            'tech_add_employee', 'tech_view_employee', 'tech_edit_employee', 'tech_deactivate_employee',
            'tech_add_department', 'tech_view_departments', 'tech_edit_departments', 'tech_manage_holidays',
            'tech_view_attendance', 'tech_override_attendance', 'tech_apply_leave', 'tech_approve_leave',
            'tech_view_leave_stats', 'tech_create_shift', 'tech_assign_shift', 'tech_view_shift',
            'tech_view_reports', 'tech_download_reports', 'tech_view_audit_logs', 'tech_edit_policies',
            'tech_configure_smtp', 'tech_enable_automation', 'tech_add_position', 'tech_edit_position',
            'tech_add_level', 'tech_add_role'
        ],
        "Senior Manager": [
            'tech_add_employee', 'tech_view_employee', 'tech_edit_employee', 'tech_deactivate_employee',
            'tech_view_departments', 'tech_edit_departments', 'tech_manage_holidays', 'tech_view_attendance',
            'tech_override_attendance', 'tech_apply_leave', 'tech_approve_leave', 'tech_view_leave_stats',
            'tech_create_shift', 'tech_assign_shift', 'tech_view_shift', 'tech_view_reports',
            'tech_download_reports'
        ],
        "HR Manager": [
            'tech_add_employee', 'tech_view_employee', 'tech_edit_employee', 'tech_deactivate_employee',
            'tech_manage_holidays', 'tech_view_attendance', 'tech_override_attendance', 'tech_apply_leave',
            'tech_approve_leave', 'tech_view_leave_stats', 'tech_view_reports', 'tech_download_reports'
        ],
        "Tech Lead": [
            'tech_view_employee', 'tech_view_departments', 'tech_view_attendance', 'tech_apply_leave',
            'tech_view_leave_stats', 'tech_view_shift', 'tech_approve_leave'
        ],
        "IT Manager": [
            'tech_view_employee', 'tech_view_departments', 'tech_view_attendance', 'tech_apply_leave',
            'tech_view_leave_stats', 'tech_view_shift', 'tech_configure_smtp', 'tech_enable_automation'
        ],
        "Software Developer": [
            'tech_view_employee', 'tech_apply_leave', 'tech_view_leave_stats', 'tech_view_shift'
        ],
        "HR Intern": [
            'tech_apply_leave', 'tech_view_leave_stats'
        ],
    },
    # Educational Roles
    "Educational": {
        "Principal": [
            'edu_add_faculty', 'edu_view_faculty', 'edu_edit_faculty', 'edu_deactivate_faculty',
            'edu_add_department', 'edu_view_departments', 'edu_edit_departments',
            'edu_manage_academic_calendar', 'edu_view_curriculum', 'edu_edit_curriculum',
            'edu_view_attendance', 'edu_override_attendance', 'edu_apply_leave', 'edu_approve_leave',
            'edu_view_leave_stats', 'edu_create_timetable', 'edu_assign_timetable', 'edu_view_timetable',
            'edu_enable_sub_rotation', 'edu_manual_sub_trigger', 'edu_add_student', 'edu_view_student',
            'edu_edit_student', 'edu_view_reports', 'edu_download_reports', 'edu_view_audit_logs',
            'edu_edit_policies', 'edu_configure_alerts'
        ],
        "Head of Department": [
            'edu_view_faculty', 'edu_edit_faculty', 'edu_view_departments', 'edu_view_curriculum',
            'edu_view_attendance', 'edu_override_attendance', 'edu_apply_leave', 'edu_approve_leave',
            'edu_view_leave_stats', 'edu_create_timetable', 'edu_assign_timetable', 'edu_view_timetable',
            'edu_enable_sub_rotation', 'edu_manual_sub_trigger', 'edu_view_student', 'edu_view_reports'
        ],
        "Controller of Examination": [
            'edu_view_faculty', 'edu_view_departments', 'edu_view_attendance', 'edu_override_attendance',
            'edu_apply_leave', 'edu_view_leave_stats', 'edu_view_timetable', 'edu_view_student',
            'edu_view_reports', 'edu_download_reports'
        ],
        "Senior Lecturer": [
            'edu_view_faculty', 'edu_view_departments', 'edu_view_curriculum', 'edu_view_attendance',
            'edu_apply_leave', 'edu_view_leave_stats', 'edu_view_timetable', 'edu_view_student'
        ],
        "Assistant Professor": [
            'edu_view_faculty', 'edu_view_curriculum', 'edu_view_attendance', 'edu_apply_leave',
            'edu_view_leave_stats', 'edu_view_timetable', 'edu_view_student'
        ],
        "Lab Assistant": [
            'edu_view_attendance', 'edu_apply_leave', 'edu_view_leave_stats', 'edu_view_timetable'
        ]
    }
}

def create_permissions(company):
    """Create all permissions based on company type"""
    company_type = 1 if company.type == 1 else 2  # 1=techorate, 2=Educational
    permission_set = tech_PERMISSIONS if company_type == 1 else EDU_PERMISSIONS
    
    created_permissions = 0
    for code, description in permission_set.items():
        perm, created = Permission.objects.get_or_create(
            code=code,
            defaults={
                'name': ' '.join(code.split('_')[1:]).title(),
                'description': description,
                'company_type': company_type
            }
        )
        if created:
            created_permissions += 1
    
    return created_permissions

def create_org_structure(company):
    """Create the full organizational structure for a company"""
    structure = techORATE_STRUCTURE if company.type == 1 else EDUCATIONAL_STRUCTURE
    company_type_name = "techorate" if company.type == 1 else "Educational"
    
    # Track created items
    created_departments = 0
    created_positions = 0
    created_levels = 0
    created_roles = 0
    
    # Create departments, positions, levels, and roles
    for dept_name, positions in structure.items():
        # Create department
        department, dept_created = Department.objects.get_or_create(
            name=dept_name,
            company=company
        )
        if dept_created:
            created_departments += 1
        
        # Create positions for this department
        for pos_name, levels in positions.items():
            position, pos_created = Position.objects.get_or_create(
                name=pos_name,
                department=department,
                company=company
            )
            if pos_created:
                created_positions += 1
            
            # Create positional levels for this position
            for level_name, role_names in levels.items():
                # Convert level name to enum value
                level_type = 1  # Default to Entry-Level
                if level_name == "Entry-Level":
                    level_type = 1
                elif level_name == "Junior-Level":
                    level_type = 2
                elif level_name == "Mid-Level":
                    level_type = 3
                elif level_name == "Senior-Level":
                    level_type = 4
                elif level_name == "Executive-Level":
                    level_type = 5
                
                level, level_created = PositionalLevel.objects.get_or_create(
                    name=level_name,
                    level_type=level_type,
                    position=position,
                    company=company
                )
                if level_created:
                    created_levels += 1
                
                # Create roles for this level
                for role_name in role_names:
                    role, role_created = Role.objects.get_or_create(
                        name=role_name,
                        positional_level=level,
                        company=company
                    )
                    if role_created:
                        created_roles += 1
                    
                    # Assign permissions to this role if defined
                    role_perms = ROLE_PERMISSIONS.get(company_type_name, {}).get(role_name, [])
                    if role_perms:
                        permissions = Permission.objects.filter(code__in=role_perms)
                        if permissions.exists():
                            # Clear existing permissions first
                            role.permissions.clear()
                            # Add new permissions
                            role.permissions.add(*permissions)
    
    return created_departments, created_positions, created_levels, created_roles

@receiver(post_save, sender=Company)
def setup_company(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set up a new company with
    organizational structure and permissions
    """
    if created:
        try:
            # 1. Create all permissions for this company type
            perm_count = create_permissions(instance)
            
            # 2. Create the full organizational structure with roles and permissions
            dept_count, pos_count, level_count, role_count = create_org_structure(instance)
            
            # 3. Log the setup completion (optional)
            from django.contrib.admin.models import LogEntry, ADDITION
            from django.contrib.contenttypes.models import ContentType
            
            LogEntry.objects.create(
                user_id=1,  # Admin user ID, adjust as needed
                content_type_id=ContentType.objects.get_for_model(Company).id,
                object_id=instance.id,
                object_repr=f"Company: {instance.name}",
                action_flag=ADDITION,
                change_message=f"Auto-setup completed: {perm_count} permissions, {dept_count} departments, "
                               f"{pos_count} positions, {level_count} positional levels, {role_count} roles"
            )
            
        except Exception as e:
            # Log error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in auto-setup for company {instance.name}: {str(e)}")