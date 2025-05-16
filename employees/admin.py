from django.contrib import admin
from .models import (
    Department, Position, PositionLevel, EmployeeProfile,
    EmployeeFaceData, Attendance, AttendanceLog,
    EmployeeLocation, EmployeeScreenshot,
    Shift, ShiftAssignment, UserShift  # Added these models
)

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company']
    list_filter = ['company']
    search_fields = ['name']

class PositionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company']
    list_filter = ['company']
    search_fields = ['name']

class PositionLevelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'company']
    list_filter = ['name', 'company']
    search_fields = ['name']
    
    def get_departments(self, obj):
        """Get departments associated with this position level through roles"""
        departments = set([role.department.name for role in obj.roles.all() if role.department])
        return ", ".join(departments) if departments else "N/A"
    get_departments.short_description = 'Departments'
    
    def get_positions(self, obj):
        """Get positions associated with this position level through roles"""
        positions = set([role.position.name for role in obj.roles.all() if role.position])
        return ", ".join(positions) if positions else "N/A"
    get_positions.short_description = 'Positions'

class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'position', 'department', 'company', 'date_of_joining']
    list_filter = ['department', 'position', 'company', 'date_of_joining']
    search_fields = ['full_name', 'user__username', 'position', 'department']
    date_hierarchy = 'date_of_joining'

@admin.register(EmployeeFaceData)
class EmployeeFaceDataAdmin(admin.ModelAdmin):
    list_display = ('employee', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('employee__full_name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Employee Information', {
            'fields': ('employee',)
        }),
        ('Face Data', {
            'fields': ('face_image', 'face_encoding')
        }),
        ('Location Data', {
            'fields': ('default_latitude', 'default_longitude', 'allowed_radius')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'status', 'shift_name', 'check_in_time', 'check_out_time', 
                   'is_face_verified', 'is_location_verified', 'location_name', 'duration_minutes')
    list_filter = ('date', 'status', 'is_face_verified', 'is_location_verified', 'company', 'shift')
    search_fields = ('employee__full_name', 'location_name', 'employee__user__username', 'shift__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at', 'duration_display')
    
    fieldsets = (
        ('Employee Information', {
            'fields': ('employee', 'company', 'date', 'status')
        }),
        ('Shift Information', {
            'fields': ('shift',)
        }),
        ('Check-in Data', {
            'fields': ('check_in_time', 'check_in_latitude', 'check_in_longitude', 'location_name')
        }),
        ('Check-out Data', {
            'fields': ('check_out_time', 'check_out_latitude', 'check_out_longitude')
        }),
        ('Duration', {
            'fields': ('duration_display',)
        }),
        ('Verification', {
            'fields': ('is_face_verified', 'is_location_verified', 'is_blink_verified', 'face_image')
        }),
        ('Additional Information', {
            'fields': ('device_info', 'created_at', 'updated_at')
        }),
    )
    
    # Add custom actions
    actions = ['mark_as_present', 'mark_as_absent', 'mark_as_late', 'mark_as_leave']
    
    def shift_name(self, obj):
        """Get shift name for display in list"""
        if obj.shift:
            return obj.shift.name
        return "-"
    
    shift_name.short_description = 'Shift'
    shift_name.admin_order_field = 'shift__name'
    
    def duration_minutes(self, obj):
        """Calculate duration in minutes between check-in and check-out"""
        if obj.check_in_time and obj.check_out_time:
            duration = obj.check_out_time - obj.check_in_time
            return int(duration.total_seconds() / 60)
        return None
    
    duration_minutes.short_description = 'Duration (min)'
    
    def duration_display(self, obj):
        """Format duration for detail view"""
        minutes = self.duration_minutes(obj)
        if minutes is not None:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            return f"{hours}h {remaining_minutes}m ({minutes} minutes total)"
        return "Not available"
    
    duration_display.short_description = 'Duration'
    
    def mark_as_present(self, request, queryset):
        """Mark selected attendance records as present"""
        queryset.update(status='present')
        self.message_user(request, f"{queryset.count()} attendance records marked as present.")
    
    mark_as_present.short_description = "Mark selected records as present"
    
    def mark_as_absent(self, request, queryset):
        """Mark selected attendance records as absent"""
        queryset.update(status='absent')
        self.message_user(request, f"{queryset.count()} attendance records marked as absent.")
    
    mark_as_absent.short_description = "Mark selected records as absent"
    
    def mark_as_late(self, request, queryset):
        """Mark selected attendance records as late"""
        queryset.update(status='late')
        self.message_user(request, f"{queryset.count()} attendance records marked as late.")
    
    mark_as_late.short_description = "Mark selected records as late"
    
    def mark_as_leave(self, request, queryset):
        """Mark selected attendance records as on leave"""
        queryset.update(status='leave')
        self.message_user(request, f"{queryset.count()} attendance records marked as on leave.")
    
    mark_as_leave.short_description = "Mark selected records as on leave"

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'timestamp', 'face_verification_result', 'location_verification_result', 'blink_verification_result')
    list_filter = ('timestamp', 'face_verification_result', 'location_verification_result', 'blink_verification_result', 'company')
    search_fields = ('employee__full_name', 'log_message')
    date_hierarchy = 'timestamp'
    fieldsets = (
        ('Basic Information', {
            'fields': ('attendance', 'employee', 'company', 'timestamp')
        }),
        ('Location Data', {
            'fields': ('latitude', 'longitude')
        }),
        ('Verification Results', {
            'fields': ('face_verification_result', 'location_verification_result', 'blink_verification_result')
        }),
        ('Additional Information', {
            'fields': ('device_info', 'log_message')
        }),
    )

@admin.register(EmployeeLocation)
class EmployeeLocationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'location_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('employee__full_name', 'location_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Employee Information', {
            'fields': ('employee', 'location_name')
        }),
        ('Location Data', {
            'fields': ('latitude', 'longitude', 'allowed_radius', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )

@admin.register(EmployeeScreenshot)
class EmployeeScreenshotAdmin(admin.ModelAdmin):
    list_display = ('employee', 'company', 'timestamp', 'is_active')
    list_filter = ('company', 'timestamp', 'is_active')
    search_fields = ('employee__full_name',)
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
    fieldsets = (
        ('Screenshot Information', {
            'fields': ('employee', 'company', 'screenshot', 'is_active')
        }),
        ('Additional Information', {
            'fields': ('timestamp', 'device_info')
        }),
    )

# Shift-related admin classes
@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'company', 'start_time', 'end_time', 'display_days')
    list_filter = ('company', 'start_time')
    search_fields = ('name', 'company__name')
    
    def display_days(self, obj):
        days = obj.get_active_days()
        return ", ".join(days) if days else "No days selected"
    display_days.short_description = "Active Days"

@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'shift', 'company', 'assignment_type', 'get_target_name', 
                    'start_date', 'end_date', 'auto_rotate')
    list_filter = ('company', 'assignment_type', 'auto_rotate', 'shift')
    search_fields = ('shift__name', 'company__name', 'department__name', 'team__name', 'user__username')
    
    def get_target_name(self, obj):
        if obj.assignment_type == 'department' and obj.department:
            return f"Department: {obj.department.name}"
        elif obj.assignment_type == 'team' and obj.team:
            return f"Team: {obj.team.name}"
        elif obj.assignment_type == 'individual' and obj.user:
            return f"User: {obj.user.username}"
        return "Not set"
    get_target_name.short_description = "Assigned To"

from django.contrib import admin
from .models import UserShift

@admin.register(UserShift)
class UserShiftAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user_info', 'shift', 'get_shift_id', 'get_start_time', 'get_end_time', 'is_shift_active']
    list_filter = ['shift__name', 'company', 'department', 'position', 'role']
    search_fields = ['user__username', 'shift__name', 'department', 'position', 'role', 'positional_level']
    
    def get_user_info(self, obj):
        department = obj.department or "-"
        position = obj.position or "-"
        level = obj.positional_level or "-"
        role = obj.role or "-"
        return f"{obj.user.username} ({department} - {position} - {level} - {role})"
    get_user_info.short_description = 'User Info'
    
    def get_shift_id(self, obj):
        return obj.shift.id
    get_shift_id.short_description = 'Shift ID'
    
    def get_start_time(self, obj):
        return obj.shift.start_time
    get_start_time.short_description = 'Start Time'
    
    def get_end_time(self, obj):
        return obj.shift.end_time
    get_end_time.short_description = 'End Time'

    def is_shift_active(self, obj):
        return obj.shift.is_active if hasattr(obj.shift, 'is_active') else True
    is_shift_active.boolean = True
    is_shift_active.short_description = 'Is Active'
# Register models using site.register (for those not using the decorator)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Position, PositionAdmin)
admin.site.register(PositionLevel, PositionLevelAdmin)
admin.site.register(EmployeeProfile, EmployeeProfileAdmin)