# employees/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Department(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='departments')
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = ('name', 'company')

class Position(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='positions')
    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='positions', null=True, blank=True)
    
    def __str__(self):
        return f"{self.name}"


class PositionLevel(models.Model):
    name = models.CharField(max_length=150)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='position_levels')
    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='position_levels', null=True, blank=True)
    
    def __str__(self):
        return f"{self.name}"

    class Meta:
        unique_together = ('name', 'company')
    
from django.db import models
from django.conf import settings
from django.db.models import JSONField  # Import JSONField

class EmployeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255, default="John Doe")
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(default="Not Provided")
    
    # These fields store names as strings from the related objects in User model
    position = models.CharField(max_length=255, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    positional_level = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    
    # Add access level field directly to EmployeeProfile
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
        help_text="Determines the scope of data this employee can access"
    )
    
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE)
    date_of_joining = models.DateField()
    profile_photo = models.ImageField(upload_to='documents/photos/', null=True, blank=True)
    aadhaar_card = models.FileField(upload_to='documents/aadhaar/', null=True, blank=True)
    additional_document = models.FileField(upload_to='documents/others/', null=True, blank=True)
    
    # New field to store multiple documents
    additional_documents = JSONField(default=dict, blank=True, null=True)
    
    def __str__(self):
        return f"{self.full_name} ({self.user.username})"
    
    def update_from_user(self):
        """Update profile fields from associated user data"""
        user = self.user
        if user.position:
            self.position = user.position.name
        if user.department:
            self.department = user.department.name
        if user.positional_level:
            self.positional_level = user.positional_level.name
        if user.user_role:
            self.role = user.user_role.name
            # Also update access level from user's role
            if hasattr(user.user_role, 'access_level'):
                self.access_level = user.user_role.access_level
        self.save()
    def add_additional_document(self, file, name=None):
        """
        Add an additional document file to the employee's documents.
        Returns the document ID.
        """
        import uuid
        import os
        from django.conf import settings
        from datetime import datetime  # Add this import
        
        # Generate a unique ID for the document
        doc_id = str(uuid.uuid4())
        
        # Get a safe filename
        original_name = file.name
        file_ext = os.path.splitext(original_name)[1].lower()
        safe_name = f"{uuid.uuid4()}{file_ext}"
        
        # Set upload path
        relative_path = f"documents/employee_{self.id}/{safe_name}"
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # Create directory if not exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file to disk
        with open(full_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Initialize additional_documents if it doesn't exist
        if not hasattr(self, 'additional_documents') or not self.additional_documents:
            self.additional_documents = {}
        
        # Document name defaults to original filename if not provided
        doc_name = name if name else original_name
        
        # Add document info to employee's documents
        self.additional_documents[doc_id] = {
            'name': doc_name,
            'file_path': relative_path,
            'url': f"/media/{relative_path}",
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Save is handled by the caller
        
        print(f"Added document: {doc_id} -> {doc_name} ({relative_path})")
        return doc_id


from django.db import models
from django.conf import settings
import uuid
import os
from employees.models import EmployeeProfile

def face_image_path(instance, filename):
    """Generate a unique path for storing face images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('attendance/faces', filename)

class EmployeeFaceData(models.Model):
    """Model for storing employee face recognition data"""
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name='face_data')
    face_image = models.ImageField(upload_to=face_image_path, blank=True, null=True)
    face_encoding = models.TextField(blank=True, null=True)  # Store face encoding as JSON string
    
    # Default location for attendance checks (office location)
    default_latitude = models.FloatField(blank=True, null=True)
    default_longitude = models.FloatField(blank=True, null=True)
    
    # Allowed radius in meters for attendance marking
    allowed_radius = models.IntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Face data for {self.employee.full_name}"

# employees/models.py

from django.db import models
from django.conf import settings  # Add this import

class EmployeeLocation(models.Model):
    """Model for storing multiple allowed locations for employee attendance"""
    employee = models.ForeignKey('EmployeeProfile', on_delete=models.CASCADE, related_name='allowed_locations')
    location_name = models.CharField(max_length=255)  # Name/description of the location
    latitude = models.FloatField()
    longitude = models.FloatField()
    allowed_radius = models.IntegerField(default=100)  # Radius in meters
    is_active = models.BooleanField(default=True)  # To enable/disable locations without deleting
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_locations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.location_name} for {self.employee.full_name}"
    
    class Meta:
        ordering = ['employee', 'location_name']
        unique_together = ['employee', 'location_name']  # Prevent duplicate location names for same employee

# employees/models.py - Attendance मॉडल में परिवर्तन

# employees/models.py

# models.py
class Attendance(models.Model):
    """Model for storing attendance records"""
    ATTENDANCE_STATUS = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('leave', 'Leave'),
    )
    
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='attendance_records')
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE)
    shift = models.ForeignKey('employees.Shift', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_records')
    date = models.DateField()
    check_in_time = models.DateTimeField(blank=True, null=True)
    check_out_time = models.DateTimeField(blank=True, null=True)
    
    # Location data
    check_in_latitude = models.FloatField(blank=True, null=True)
    check_in_longitude = models.FloatField(blank=True, null=True)
    check_out_latitude = models.FloatField(blank=True, null=True)
    check_out_longitude = models.FloatField(blank=True, null=True)
    
    # Attendance verification
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default='absent')
    is_location_verified = models.BooleanField(default=False)
    is_face_verified = models.BooleanField(default=False)
    is_blink_verified = models.BooleanField(default=False)  # Add this new field
    
    # Device information
    device_info = models.JSONField(blank=True, null=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    # Face capture for this attendance
    face_image = models.ImageField(upload_to=face_image_path, blank=True, null=True)
    # In your Attendance model
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-check_in_time']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.status}"

    def duration_minutes(self):
        """Calculate duration in minutes between check-in and check-out"""
        if self.check_in_time and self.check_out_time:
            duration = self.check_out_time - self.check_in_time
            return int(duration.total_seconds() / 60)
        return None

class AttendanceLog(models.Model):
    """Model for storing detailed attendance logs"""
    attendance = models.ForeignKey('employees.Attendance', on_delete=models.CASCADE, related_name='logs')
    employee = models.ForeignKey('employees.EmployeeProfile', on_delete=models.CASCADE)
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    face_verification_result = models.BooleanField(default=False)
    location_verification_result = models.BooleanField(default=False)
    blink_verification_result = models.BooleanField(default=False)  # Add blink verification field
    device_info = models.JSONField(blank=True, null=True)
    log_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        
# employees/models.py (Add this to your existing file)

class EmployeeScreenshot(models.Model):
    """Model for storing employee screenshots for monitoring"""
    employee = models.ForeignKey('employees.EmployeeProfile', on_delete=models.CASCADE, related_name='screenshots')
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    screenshot = models.ImageField(upload_to='screenshots/%Y/%m/%d/')
    
    # Optional metadata
    is_active = models.BooleanField(default=True)  # Whether user was active at capture time
    device_info = models.JSONField(blank=True, null=True)
    
    def __str__(self):
        return f"Screenshot of {self.employee.full_name} at {self.timestamp}"


from django.db import models
from django.conf import settings
from companies.models import Company
from employees.models import Department

class Shift(models.Model):
    """Model for defining shift patterns"""
    name = models.CharField(max_length=100)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='shifts')
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Days of the week
    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"
    
    def get_active_days(self):
        """Returns a list of days when this shift is active"""
        days = []
        if self.monday: days.append('Monday')
        if self.tuesday: days.append('Tuesday')
        if self.wednesday: days.append('Wednesday')
        if self.thursday: days.append('Thursday')
        if self.friday: days.append('Friday')
        if self.saturday: days.append('Saturday')
        if self.sunday: days.append('Sunday')
        return days
    # Add this method to your Shift model class
    def get_weekdays(self):
        """Returns a list of weekdays this shift is active on"""
        weekdays = []

        # Assuming your Shift model has boolean fields for each day
        if hasattr(self, 'monday') and self.monday:
            weekdays.append(0)  # Monday is 0 in Python's datetime
        if hasattr(self, 'tuesday') and self.tuesday:
            weekdays.append(1)
        if hasattr(self, 'wednesday') and self.wednesday:
            weekdays.append(2)
        if hasattr(self, 'thursday') and self.thursday:
            weekdays.append(3)
        if hasattr(self, 'friday') and self.friday:
            weekdays.append(4)
        if hasattr(self, 'saturday') and self.saturday:
            weekdays.append(5)
        if hasattr(self, 'sunday') and self.sunday:
            weekdays.append(6)

        return weekdays


class ShiftAssignment(models.Model):
    """Model for assigning shifts to departments, teams or individual users"""
    ASSIGNMENT_TYPE_CHOICES = (
        ('department', 'Department'),
        ('team', 'Team'),
        ('individual', 'Individual'),
    )
    
    shift = models.ForeignKey('employees.Shift', on_delete=models.CASCADE, related_name='assignments')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='shift_assignments')
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE_CHOICES)
    
    # Only one of the following should be set based on assignment_type
    department = models.ForeignKey('employees.Department', on_delete=models.CASCADE, 
                                   related_name='shift_assignments', null=True, blank=True)
    team = models.ForeignKey('companies.Team', on_delete=models.CASCADE, 
                             related_name='shift_assignments', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                             related_name='shift_assignments', null=True, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # Null means indefinite
    
    # Auto-rotation settings
    auto_rotate = models.BooleanField(default=False)
    rotation_days = models.PositiveIntegerField(default=15)  # Default rotation every 15 days
    last_rotation_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        assignment_target = "Unknown"
        if self.assignment_type == 'department' and self.department:
            assignment_target = f"Department: {self.department.name}"
        elif self.assignment_type == 'team' and self.team:
            assignment_target = f"Team: {self.team.name}"
        elif self.assignment_type == 'individual' and self.user:
            assignment_target = f"User: {self.user.username}"
        
        return f"{self.shift.name} assigned to {assignment_target}"

class UserShift(models.Model):
    """Model for tracking individual user shift assignments (generated from ShiftAssignment)"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_shifts')
    shift = models.ForeignKey('employees.Shift', on_delete=models.CASCADE, related_name='user_shifts')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='user_shifts')
    assignment = models.ForeignKey('employees.ShiftAssignment', on_delete=models.CASCADE, related_name='user_shifts',null=True,blank=True)
    
    # Add these fields to store user info directly in UserShift
    department = models.CharField(max_length=255, null=True, blank=True)
    position = models.CharField(max_length=255, null=True, blank=True)
    positional_level = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    
    start_date = models.DateField(null=True,blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True,null=True,blank=True)
    updated_at = models.DateTimeField(auto_now=True,null=True,blank=True)
    
    def save(self, *args, **kwargs):
        # Before saving, copy user profile information to this model
        try:
            profile = self.user.employeeprofile
            self.department = profile.department
            self.position = profile.position
            self.positional_level = profile.positional_level
            self.role = profile.role
        except:
            # If unable to get profile info, leave fields as they are
            pass
            
        # Check for overlapping shifts before saving
        if self.pk is None:  # Only check when creating, not updating
            overlapping_shifts = UserShift.objects.filter(
                user=self.user,
                company=self.company,
                start_date__lte=self.start_date,
                end_date__gte=self.start_date if self.end_date else self.start_date
            ).exclude(pk=self.pk)
            
            # For each potentially overlapping shift, check time overlap
            for existing_shift in overlapping_shifts:
                if self._times_overlap(existing_shift.shift):
                    raise ValidationError("User already has a shift assigned during this time period")
        
        super().save(*args, **kwargs)
    
    def _times_overlap(self, other_shift):
        """Check if this shift's times overlap with another shift"""
        # Convert times to comparable format (minutes since midnight)
        this_start = self._time_to_minutes(self.shift.start_time)
        this_end = self._time_to_minutes(self.shift.end_time)
        other_start = self._time_to_minutes(other_shift.start_time)
        other_end = self._time_to_minutes(other_shift.end_time)
        
        # Handle overnight shifts
        if this_end < this_start:
            this_end += 24 * 60  # Add a full day in minutes
        
        if other_end < other_start:
            other_end += 24 * 60
        
        # Check for overlap
        return (this_start < other_end) and (this_end > other_start)
        
    def _time_to_minutes(self, time_obj):
        """Convert a time object to minutes since midnight"""
        return time_obj.hour * 60 + time_obj.minute
        
    def __str__(self):
        # Use the stored fields instead of fetching from profile
        department = self.department or "No Department"
        position = self.position or "No Position"
        level = self.positional_level or "No Level"
        role = self.role or "No Role"
        
        return f"{self.user.username} ({department} - {position} - {level} - {role}) assigned to {self.shift.name}"