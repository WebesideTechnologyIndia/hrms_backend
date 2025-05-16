# company/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Company, Permission
from employees.models import Department, Position, PositionLevel
import logging

# Define company structure templates with departments, positions, and position levels
TECH_STRUCTURE = {
    "Management": {
        "Manager": ["Mid-Level", "Senior-Level"],
        "Executive": ["Junior-Level"]
    },
    "Development": {
        "Engineer": ["Junior-Level", "Mid-Level", "Senior-Level"],
        "Team Leader":["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "Human Resources": {
        "HR Executive": ["Junior-Level", "Mid-Level", "Senior-Level"],
        "HR Head": ["Junior-Level", "Mid-Level", "Senior-Level"],
        "HR Department": ["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "Sales & Marketing": {
        "Executive": ["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "IT & Support": {
        "Support Engineer": ["Junior-Level", "Mid-Level", "Senior-Level"]
    }
}

EDUCATIONAL_STRUCTURE = {
    "Administration": {
        "Manager": ["Mid-Level", "Senior-Level"],
        "Executive": ["Junior-Level"]
    },
    "Teaching": {
        "Faculty": ["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "Student Affairs": {
        "Coordinator": ["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "Examination & Evaluation": {
        "Exam Officer": ["Junior-Level", "Mid-Level", "Senior-Level"]
    },
    "Library & Lab Support": {
        "Assistant": ["Entry-Level", "Mid-Level", "Senior-Level"]
    }
}

# Define permissions by company type
TECH_PERMISSIONS = {
    # Employee Management
    'tech_add_employee': 'Add Employee',
    'tech_view_employee': 'View Employees',
    'tech_edit_employee': 'Edit Employee',
    'tech_deactivate_employee': 'Deactivate Employee',
    'tech_delete_employee': 'Delete Employee',
    
    # Department Management
    'tech_add_department': 'Add Department',
    'tech_view_departments': 'View Departments',
    'tech_edit_departments': 'Edit Departments',
    'tech_delete_department': 'Delete Department',
    
    # Attendance Management
    'tech_view_attendance': 'View Attendance',
    'tech_edit_attendance': 'Edit Attendance',
    'tech_mark_attendance':'Mark Attendance',

    # Leave Management
    'tech_apply_leave': 'Apply Leave',
    'tech_approve_leave': 'Approve Leaves',
    'tech_view_leave_stats': 'View Leave Stats',
    
    # Company Configuration
    'tech_add_position': 'Add Position',
    'tech_edit_position': 'Edit Position',
    'tech_view_position': ' View Position',
    'tech_delete_position' : 'Delete Position',


    'tech_create_position_level': 'Create Position Level',
    'tech_view_positional_level':'View Positional Level',
    'tech_edit_positional_level':'Edit Positional Level',
    'tech_delete_positional_level': 'Delete Positional Level',


    'tech_add_role': 'Add Role',
    'tech_view_role':'View Role',
    'tech_edit_role':'Edit Role',
    'tech_delete_role': 'Delete Role',

    # teams
    'tech_create_team':'Create Team',
    'tech_view_team' : 'View Teams',
    'tech_edit_team' : 'Edit Team',
    'tech_delete_team' :'Delete Team',

    #documents
    'tech_view_all_documents':'View Documents',
    'tech_add_document':'Add Document',

}

EDU_PERMISSIONS = {
    # Faculty Management
    'edu_add_faculty': 'Add Faculty',
    'edu_view_faculty': 'View Faculty',
    'edu_edit_faculty': 'Edit Faculty',
    'edu_deactivate_faculty': 'Deactivate Faculty',
    
    # Department Management
    'edu_add_department': 'Add Department',
    'edu_view_departments': 'View Department',
    'edu_edit_departments': 'Edit Department',
    
    # Holidays Management
    'edu_manage_academic_calendar': 'Manage Academic Calendar',
    
    # Attendance Management
    'edu_view_attendance': 'View Attendance',
    'edu_override_attendance': 'Override Attendance',
    
    # Leave Management
    'edu_apply_leave': 'Apply Leave',
    'edu_approve_leave': 'Approve Leaves',
    'edu_view_leave_stats': 'View Leave Stats',
    
    # Round Robin / Substitution
    'edu_enable_sub_rotation': 'Enable Substitution Rotation',
    'edu_manual_sub_trigger': 'Manual Substitution Trigger',
    
    # Timetable Management
    'edu_create_timetable': 'Create Timetable',
    'edu_assign_timetable': 'Assign Timetable',
    'edu_view_timetable': 'View Timetable',
    
    # Notifications
    'edu_configure_alerts': 'Configure Academic Alerts',
    
    # Reports & Analytics
    'edu_view_reports': 'View Academic Reports',
    'edu_download_reports': 'Download Reports',
    'edu_view_audit_logs': 'View Faculty Audit Logs',
    
    # Curriculum Management
    'edu_view_curriculum': 'View Curriculum',
    'edu_edit_curriculum': 'Edit Curriculum',
    
    # Student Management
    'edu_add_student': 'Add Student',
    'edu_view_student': 'View Student',
    'edu_edit_student': 'Edit Student',
    
    # Institution Configuration
    'edu_edit_policies': 'Edit Academic Policies',
}

# Default permissions for company admin - all permissions for the company type
DEFAULT_ADMIN_PERMISSIONS = {
    "tech": list(TECH_PERMISSIONS.keys()),
    "educational": list(EDU_PERMISSIONS.keys())
}

# Set up logging
logger = logging.getLogger(__name__)

def create_permissions(company):
    """Create all permissions based on company type"""
    logger.info(f"Creating permissions for company {company.name} (type: {company.type})")
    
    company_type = "tech" if company.type == 1 else "educational"
    permission_set = TECH_PERMISSIONS if company.type == 1 else EDU_PERMISSIONS
    
    tech_categories = {
    # Employee
    'tech_add_employee': 'employee',
    'tech_view_employee': 'employee',
    'tech_edit_employee': 'employee',
    'tech_deactivate_employee': 'employee',
    'tech_delete_employee': 'employee',

    # Department
    'tech_add_department': 'department',
    'tech_view_departments': 'department',
    'tech_edit_departments': 'department',
    'tech_delete_department': 'department',

    # Attendance
    'tech_view_attendance': 'attendance',
    'tech_edit_attendance': 'attendance',
    'tech_mark_attendance': 'attendance',

    # Leave
    'tech_apply_leave': 'leaves',
    'tech_approve_leave': 'leaves',
    'tech_view_leave_stats': 'leaves',

    # Company (Position/Role/Level)
    'tech_add_position': 'company',
    'tech_edit_position': 'company',
    'tech_view_position': 'company',
    'tech_delete_position': 'company',

    'tech_create_position_level': 'company',
    'tech_view_positional_level': 'company',
    'tech_edit_positional_level': 'company',
    'tech_delete_positional_level': 'company',

    'tech_add_role': 'company',
    'tech_view_role': 'company',
    'tech_edit_role': 'company',
    'tech_delete_role': 'company',

    # Teams
    'tech_create_team': 'teams',
    'tech_view_team': 'teams',
    'tech_edit_team': 'teams',
    'tech_delete_team': 'teams',

    # Documents
    'tech_view_all_documents': 'documents',
    'tech_add_document': 'documents',
}

    
    edu_categories = {
        'edu_add_faculty': 'faculty', 'edu_view_faculty': 'faculty', 
        'edu_edit_faculty': 'faculty', 'edu_deactivate_faculty': 'faculty',
        'edu_add_department': 'department', 'edu_view_departments': 'department', 
        'edu_edit_departments': 'department',
        'edu_manage_academic_calendar': 'holidays',
        'edu_view_attendance': 'attendance', 'edu_override_attendance': 'attendance',
        'edu_apply_leave': 'leaves', 'edu_approve_leave': 'leaves', 
        'edu_view_leave_stats': 'leaves',
        'edu_enable_sub_rotation': 'round_robin', 'edu_manual_sub_trigger': 'round_robin',
        'edu_create_timetable': 'scheduling', 'edu_assign_timetable': 'scheduling', 
        'edu_view_timetable': 'scheduling',
        'edu_configure_alerts': 'notifications',
        'edu_view_reports': 'reports', 'edu_download_reports': 'reports',
        'edu_view_audit_logs': 'audit',
        'edu_view_curriculum': 'general', 'edu_edit_curriculum': 'general',
        'edu_add_student': 'general', 'edu_view_student': 'general', 
        'edu_edit_student': 'general',
        'edu_edit_policies': 'institute'
    }
    
    categories_map = tech_categories if company.type == 1 else edu_categories
    
    created_permissions = 0
    for code, description in permission_set.items():
        try:
            category = categories_map.get(code, 'general')
            perm, created = Permission.objects.get_or_create(
                code=code,
                defaults={
                    'name': description,
                    'company_type': company_type,
                    'category': category
                }
            )
            if created:
                created_permissions += 1
                logger.info(f"Created permission: {code} with category {category}")
        except Exception as e:
            logger.error(f"Error creating permission {code}: {str(e)}")
    
    logger.info(f"Created {created_permissions} permissions for company {company.name}")
    return created_permissions

def create_org_structure(company):
    """Create the organizational structure (departments, positions, and position levels)"""
    logger.info(f"Creating organizational structure for company {company.name} (type: {company.type})")
    
    # Get appropriate structure
    structure = TECH_STRUCTURE if company.type == 1 else EDUCATIONAL_STRUCTURE
    
    created_departments = 0
    created_positions = 0
    created_position_levels = 0
    
    # Create departments, positions, and position levels
    for dept_name, positions in structure.items():
        department = None
        try:
            # Create department
            department, dept_created = Department.objects.get_or_create(
                name=dept_name,
                company=company
            )
            if dept_created:
                created_departments += 1
                logger.info(f"Created department: {dept_name}")
        except Exception as e:
            logger.error(f"Error creating department {dept_name}: {str(e)}")
            continue  # Skip this department if it fails
        
        # Create positions
        for pos_name, level_list in positions.items():
            try:
                # Create position
                position, pos_created = Position.objects.get_or_create(
                    name=pos_name,
                    company=company
                )
                if pos_created:
                    created_positions += 1
                    logger.info(f"Created position: {pos_name}")
                
                # Create position levels, not associating them with departments or positions yet
                # These will be combined with department and position when user creates a role
                for level_name in level_list:
                    try:
                        # Create position level (company-wide, not tied to departments or positions yet)
                        position_level, pl_created = PositionLevel.objects.get_or_create(
                            name=level_name,
                            company=company
                        )
                        if pl_created:
                            created_position_levels += 1
                            logger.info(f"Created position level: {level_name}")
                    except Exception as e:
                        logger.error(f"Error creating position level {level_name}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error creating position {pos_name}: {str(e)}")
    
    logger.info(f"Created {created_departments} departments, {created_positions} positions, " 
               f"{created_position_levels} position levels")
    logger.info(f"Note: Users will need to create roles by combining department, position, and position level.")
    return created_departments, created_positions, created_position_levels

@receiver(post_save, sender=Company)
def setup_company(sender, instance, created, **kwargs):
    """Signal handler to set up a new company"""
    if created:
        logger.info(f"Company {instance.name} created, starting setup...")
        try:
            with transaction.atomic():  # Use transaction to ensure all or nothing
                # Create permissions
                perm_count = create_permissions(instance)
                
                # Create organizational structure
                dept_count, pos_count, level_count = create_org_structure(instance)
                
                # Log completion
                logger.info(f"Setup complete for company {instance.name}: "
                           f"{perm_count} permissions, {dept_count} departments, "
                           f"{pos_count} positions, {level_count} position levels")
                logger.info(f"Note: Users will need to create roles by combining department, position, and position level.")
        except Exception as e:
            logger.error(f"Error in setup_company for {instance.name}: {str(e)}")
            # Re-raise to roll back transaction
            raise

