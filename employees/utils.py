from django.utils import timezone
from django.db.models import Q
from employees.models import Department
from companies.models import Team, TeamMember
from .models import ShiftAssignment, UserShift, Shift
from django.core.exceptions import ValidationError


from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import UserShift

User = get_user_model()

def create_user_shifts_for_assignment(assignment):
    """
    Create individual UserShift records based on a ShiftAssignment.
    """
    company = assignment.company
    shift = assignment.shift
    start_date = assignment.start_date
    end_date = assignment.end_date
    
    # Determine which users to create shifts for based on assignment type
    users = []
    
    if assignment.assignment_type == 'department' and assignment.department:
        # Get all users in this department
        users = User.objects.filter(company=company, department__id=assignment.department.id)
    
    elif assignment.assignment_type == 'team' and assignment.team:
        # Get all users in this team
        users = User.objects.filter(company=company, teams__id=assignment.team.id)
    
    elif assignment.assignment_type == 'individual' and assignment.user:
        # Single user assignment
        users = [assignment.user]
    
    # Create UserShift records for each user
    created_shifts = []
    errors = []
    
    for user in users:
        try:
            # Check if user has a profile, and get their info
            department = None
            position = None
            positional_level = None
            role = None
            
            try:
                profile = user.employeeprofile
                department = profile.department
                position = profile.position
                positional_level = profile.positional_level
                role = profile.role
            except:
                # If no profile exists, leave these fields as None
                pass
            
            # Create the UserShift with user info
            user_shift = UserShift.objects.create(
                user=user,
                shift=shift,
                company=company,
                assignment=assignment,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                # Add the user's info fields
                department=department,
                position=position,
                positional_level=positional_level,
                role=role
            )
            
            created_shifts.append(user_shift)
            
        except ValidationError as e:
            # If a validation error occurs (e.g., overlapping shifts),
            # add to error list and continue with next user
            errors.append(f"Error creating shift for {user.username}: {str(e)}")
        except Exception as e:
            errors.append(f"Unexpected error for {user.username}: {str(e)}")
    
    # If no shifts created due to errors, raise exception
    if not created_shifts and errors:
        raise ValidationError(f"No shifts created. Errors: {'; '.join(errors)}")
    
    # If some shifts created, but some errors, log them
    if errors:
        print(f"Some shift assignments had errors: {'; '.join(errors)}")
    
    return created_shifts


def process_shift_rotations():
    """
    Process all shift rotations that are due
    This function is meant to be run daily via a scheduled task
    """
    today = timezone.now().date()
    
    # Find all shift assignments with auto-rotation enabled
    rotation_assignments = ShiftAssignment.objects.filter(
        auto_rotate=True,
        start_date__lte=today,
        end_date__gte=today
    )
    
    for assignment in rotation_assignments:
        # Check if rotation is due based on last rotation date
        if not assignment.last_rotation_date or \
           (today - assignment.last_rotation_date).days >= assignment.rotation_days:
            rotate_shift_assignment(assignment)

def rotate_shift_assignment(assignment):
    """Rotate a shift assignment to the next shift in the rotation"""
    today = timezone.now().date()
    
    # First, get all shifts for this company for rotation
    company_shifts = Shift.objects.filter(company=assignment.company).order_by('id')
    
    if company_shifts.count() <= 1:
        # Need at least 2 shifts for rotation
        return
    
    # Find the current shift's index in the rotation
    current_shift_index = -1
    for i, shift in enumerate(company_shifts):
        if shift.id == assignment.shift.id:
            current_shift_index = i
            break
    
    if current_shift_index == -1:
        # Current shift not found in rotation
        return
    
    # Determine the next shift in rotation
    next_shift_index = (current_shift_index + 1) % company_shifts.count()
    next_shift = company_shifts[next_shift_index]
    
    # Update the assignment
    assignment.shift = next_shift
    assignment.last_rotation_date = today
    assignment.save()
    
    # Update user shifts by deactivating the current ones and creating new ones
    current_user_shifts = UserShift.objects.filter(
        assignment=assignment,
        is_active=True
    )
    
    for user_shift in current_user_shifts:
        # Deactivate the current shift
        user_shift.is_active = False
        user_shift.end_date = today
        user_shift.save()
        
        # Create a new user shift with the next shift
        UserShift.objects.create(
            user=user_shift.user,
            shift=next_shift,
            company=assignment.company,
            assignment=assignment,
            start_date=today,
            end_date=assignment.end_date,
            is_active=True
        )

def get_active_shifts_for_user(user, date=None):
    """Get active shifts for a user on a specific date (default: today)"""
    if date is None:
        date = timezone.now().date()
    
    return UserShift.objects.filter(
    Q(user=user) &
    Q(is_active=True) &
    Q(start_date__lte=date) &
    (Q(end_date__gte=date) | Q(end_date__isnull=True))
).select_related('shift')


def get_users_by_current_shift(company, shift=None):
    """
    Get all users currently assigned to a specific shift
    If shift is None, returns a dictionary of shift_id -> list of users
    """
    today = timezone.now().date()
    
    # Base query for active user shifts
    query = UserShift.objects.filter(
    Q(company=company) &
    Q(is_active=True) &
    Q(start_date__lte=today) &
    (Q(end_date__gte=today) | Q(end_date__isnull=True))
).select_related('user', 'shift')

    if shift:
        # Filter for specific shift
        query = query.filter(shift=shift)
        return [user_shift.user for user_shift in query]
    else:
        # Group by shifts
        result = {}
        for user_shift in query:
            shift_id = user_shift.shift.id
            if shift_id not in result:
                result[shift_id] = []
            result[shift_id].append(user_shift.user)
        return result