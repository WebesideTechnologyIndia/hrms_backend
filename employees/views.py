# employees/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.models import User
from .models import EmployeeProfile
from django.contrib.auth.hashers import make_password

from django.db import IntegrityError, transaction
import json
import os
from django.conf import settings
from django.utils import timezone


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_employee(request):
    if not request.user.permissions.filter(code='tech_add_employee').exists():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get the company and check user creation limit
    company = request.user.company
    user_limit = company.user_limit if hasattr(company, 'user_limit') else 1
    
    # Count existing employees in the company
    current_user_count = User.objects.filter(company=company, role='employee').count()
    
    # Check if limit is reached
    if current_user_count >= user_limit:
        return JsonResponse({'error': f'User creation limit reached. Your plan allows {user_limit} employees maximum.'}, status=400)
    
    data = request.data
    
    # Debug what permissions are being sent
    print("Form data received:", data)
    print("Add permission IDs:", data.get('add_permission_ids'))
    print("Remove permission IDs:", data.get('remove_permission_ids'))
    print("Has custom permissions:", data.get('has_custom_permissions'))
    print("User permissions received:", data.get('user_permissions'))
    print("Permission IDs received:", data.get('permission_ids'))
    print("DEBUG: Raw permission_codes value:", data.get('permission_codes', 'NOT FOUND'))
    print("Access level received:", data.get('access_level', 'NOT FOUND'))

    try:
        with transaction.atomic():
            # ✅ Step 1: Fetch foreign key objects
            position_id = data.get('position')
            department_id = data.get('department')
            level_id = data.get('positional_level')
            role_id = data.get('role')

            # Log for debugging
            print(f"Received IDs - position: {position_id}, department: {department_id}, level: {level_id}, role: {role_id}")

            # Try to get objects by ID - make sure the IDs exist
            try:
                position = Position.objects.get(id=position_id) if position_id else None
                department = Department.objects.get(id=department_id) if department_id else None
                positional_level = PositionLevel.objects.get(id=level_id) if level_id else None
                user_role = Role.objects.get(id=role_id) if role_id else None

                # Log for debugging
                print(f"Found objects - position: {position}, department: {department}, level: {positional_level}, role: {user_role}")

            except (Position.DoesNotExist, Department.DoesNotExist, 
                   PositionLevel.DoesNotExist, Role.DoesNotExist) as e:
                print(f"Error finding object: {e}")
                return Response({'error': f'Invalid reference: {str(e)}'}, status=400)

            # ✅ Get access level from role or request data
            access_level = data.get('access_level')
            
            # If access_level not provided in request but role exists, get it from role
            if not access_level and user_role and hasattr(user_role, 'access_level'):
                access_level = user_role.access_level
                print(f"Using access level '{access_level}' from role '{user_role.name}'")
            elif not access_level:
                # Default access level if not provided and not found in role
                access_level = 'basic'
                print(f"Using default access level: '{access_level}'")
            else:
                print(f"Using provided access level: '{access_level}'")

            # ✅ Step 2: Create User
            user = User.objects.create_user(
                username=data.get('username'),
                email=data.get('email'),
                password=data.get('password'),
                role='employee',
                company=request.user.company,
                position=position,
                department=department,
                positional_level=positional_level,
                user_role=user_role,
                access_level=access_level,  # Add the access_level field
            )

            # ✅ Step 3: Create EmployeeProfile
            profile = EmployeeProfile.objects.create(
                user=user,
                company=request.user.company,
                full_name=data.get('full_name', ''),
                dob=data.get('dob') or None,
                address=data.get('address', ''),
                position=data.get('position_name') or (position.name if position else ''),
                department=data.get('department_name') or (department.name if department else ''),
                positional_level=data.get('position_level_name') or (positional_level.name if positional_level else ''),
                role=data.get('role_name') or (user_role.name if user_role else ''),
                date_of_joining=data.get('date_of_joining') or None,
                profile_photo=request.FILES.get('profile_photo'),
                aadhaar_card=request.FILES.get('aadhaar_card'),
                additional_document=request.FILES.get('additional_document'),
                access_level=access_level,  # Also store in profile if needed
            )
            
            # ✅ Process additional documents
            try:
                # Check if additional_documents JSON data is present
                if data.get('additional_documents'):
                    documents_data = json.loads(data.get('additional_documents'))
                    
                    
                    # Process each document in the JSON data
                    for doc_key, doc_info in documents_data.items():
                        file_key = doc_info.get('file_key')
                        doc_name = doc_info.get('name')
                        
                        if file_key and doc_name and file_key in request.FILES:
                            # Get the file object from request.FILES
                            file_obj = request.FILES[file_key]
                            
                            # Create file path (you'll need to implement file saving logic separately)
                             # Use the new method to save the file and update the JSONField
                            profile.add_additional_document(file_obj, doc_name)
                            print(f"Added document {doc_name}")
                    
            except Exception as doc_error:
                print(f"Error processing additional documents: {doc_error}")
            
            # ✅ Step 4: Handle permissions
            from companies.models import Permission
            
            # Check if permissions are provided
            if data.get('permission_ids') or data.get('user_permissions'):
                try:
                    # First try permission_ids (comma-separated string of IDs)
                    if data.get('permission_ids'):
                        if isinstance(data.get('permission_ids'), str):
                            permission_ids = data.get('permission_ids').split(',')
                            permission_ids = [int(pid.strip()) for pid in permission_ids if pid.strip()]
                        else:
                            permission_ids = data.get('permission_ids')
                    # Then try user_permissions (JSON string of IDs)
                    elif data.get('user_permissions'):
                        if isinstance(data.get('user_permissions'), str):
                            try:
                                permission_ids = json.loads(data.get('user_permissions'))
                            except json.JSONDecodeError:
                                # If it's not valid JSON, try comma-separated
                                permission_ids = data.get('user_permissions').replace('[', '').replace(']', '').split(',')
                                permission_ids = [int(pid.strip()) for pid in permission_ids if pid.strip()]
                        else:
                            permission_ids = data.get('user_permissions')
                    else:
                        permission_ids = []
                    
                    # Get the Permission objects
                    permissions = Permission.objects.filter(id__in=permission_ids)
                    
                    # Clear existing permissions and add new ones
                    user.permissions.clear()
                    for permission in permissions:
                        user.permissions.add(permission)
                    
                    print(f"Added {len(permissions)} permissions to user {user.username}")
                except Exception as e:
                    print(f"Error assigning permissions: {e}")
            else:
                print("No permissions provided for the user")
            
            # Handle permission_codes if available
            if data.get('permission_codes'):
                try:
                    # Parse permission codes
                    if isinstance(data.get('permission_codes'), str):
                        try:
                            permission_codes = json.loads(data.get('permission_codes'))
                        except json.JSONDecodeError:
                            permission_codes = []
                    else:
                        permission_codes = data.get('permission_codes')
                    
                    # Get permissions by code
                    code_permissions = Permission.objects.filter(code__in=permission_codes)
                    
                    # Add permissions by code
                    for permission in code_permissions:
                        user.permissions.add(permission)
                    
                    print(f"Added {len(code_permissions)} permissions by code to user {user.username}")
                except Exception as e:
                    print(f"Error assigning permissions by code: {e}")
            
            # Log employee creation using ActivityLogger
            try:
                from users.services import ActivityLogger
                
                # Prepare details about the created employee
                details = {
                    'employee_id': profile.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': profile.full_name,
                    'department': profile.department,
                    'position': profile.position,
                    'role': user.role,
                    'access_level': user.access_level,  # Include access_level in logs
                    'created_by': request.user.username
                }
                
                # Log the activity
                ActivityLogger.log_activity(
                    action_type='user_created',
                    performed_by=request.user,
                    company=company,
                    details=details
                )
            except Exception as log_error:
                # Just print the error, don't prevent the employee creation
                print(f"Error logging employee creation: {log_error}")

        # Include access_level in the response
        return Response({
            'message': 'Employee created successfully',
            'access_level': access_level,
            'user_id': user.id,
            'username': user.username,
            'email': user.email
        })

    except IntegrityError as e:
        error_message = str(e)
        if "users_user.email" in error_message:
            return Response({'error': 'Email already exists. Please use a different email.'}, status=400)
        elif "users_user.username" in error_message:
            return Response({'error': 'Username already exists. Please choose another username.'}, status=400)
        return Response({'error': 'Integrity error: ' + error_message}, status=400)

    except Exception as e:
        print("Unexpected error:", e)
        return Response({'error': str(e)}, status=400)    
# employees/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import EmployeeProfile

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_employees(request):
    user_company = request.user.company
    employees = EmployeeProfile.objects.filter(user__company=user_company)

    data = []
    for emp in employees:
        # Handle file fields with try/except blocks as you already do
        try:
            profile_photo = emp.profile_photo.url if emp.profile_photo else None
        except:
            profile_photo = None

        try:
            aadhaar_card = emp.aadhaar_card.url if emp.aadhaar_card else None
        except:
            aadhaar_card = None

        try:
            additional_document = emp.additional_document.url if emp.additional_document else None
        except:
            additional_document = None
            
        # Fix for additional_documents JSONFiel
        try:
            additional_docs = {}
            if emp.additional_documents and isinstance(emp.additional_documents, dict):
                for doc_id, doc_info in emp.additional_documents.items():
                    # Make a copy of the document info
                    doc_copy = doc_info.copy()

                    # Ensure URL is properly formatted
                    if 'file_path' in doc_info:
                        file_path = doc_info['file_path']
                        # Make sure the URL starts with /media/
                        doc_copy['url'] = f"/media/{file_path}"

                    # Add the document to our processed dictionary
                    additional_docs[doc_id] = doc_copy
        except Exception as e:
            print(f"Error processing additional_documents for employee {emp.id}: {str(e)}")
            additional_docs = {}
        data.append({
            'id': emp.id,
            'username': emp.user.username,
            'email': emp.user.email,
            'full_name': emp.full_name,
            'dob': emp.dob,
            'address': emp.address,
            'position': emp.position,
            'department': emp.department,
            'role': emp.user.get_role_display(),
            'user_role': emp.user.user_role.name if emp.user.user_role else None,
            'positional_level': emp.positional_level,
            'date_of_joining': emp.date_of_joining,
            'profile_photo': profile_photo,
            'aadhaar_card': aadhaar_card,
            'additional_document': additional_document,
            'is_active': emp.user.is_active_employee,
            'access_level': getattr(emp.user, 'access_level', 'basic'),
            'additional_documents': additional_docs  # Use our processed version
        })
        print(f"Employee {emp.id} data: {data}")  # 👈 Yeh line add karo
    return Response(data)
# employees/views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fix_document_paths(request):
    """
    Administrative endpoint to fix document paths
    """
    if not request.user.is_staff:
        return Response({"error": "Permission denied"}, status=403)
    
    import os
    from django.conf import settings
    
    fixed_count = 0
    problem_count = 0
    
    # Get all employee profiles
    employees = EmployeeProfile.objects.all()
    
    for emp in employees:
        if not emp.additional_documents:
            continue
            
        docs = emp.additional_documents.copy()
        updated = False
        
        for doc_id, doc_info in docs.items():
            if 'file_path' in doc_info:
                # Get old path
                old_path = doc_info['file_path']
                
                # Create clean path without spaces
                parts = old_path.split('/')
                filename = parts[-1].replace(' ', '_')
                new_path = '/'.join(parts[:-1] + [filename])
                
                # Check if old file exists
                old_full_path = os.path.join(settings.MEDIA_ROOT, old_path)
                new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
                
                if os.path.exists(old_full_path):
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                    
                    # Rename the file
                    try:
                        os.rename(old_full_path, new_full_path)
                        
                        # Update the path in docs
                        docs[doc_id]['file_path'] = new_path
                        docs[doc_id]['url'] = f'/media/{new_path}'
                        updated = True
                        fixed_count += 1
                    except Exception as e:
                        problem_count += 1
                        print(f"Error fixing file for employee {emp.id}, doc {doc_id}: {e}")
                else:
                    problem_count += 1
        
        # Save changes if any were made
        if updated:
            emp.additional_documents = docs
            emp.save()
    
    return Response({
        "success": True,
        "fixed_documents": fixed_count,
        "problem_documents": problem_count
    })


from django.views.decorators.http import require_http_methods

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_employee(request, id):   
    try:
        employee = EmployeeProfile.objects.get(id=id, user__company=request.user.company)
        
        # Store employee information before deletion for logging
        employee_details = {
            'employee_id': employee.id,
            'username': employee.user.username,
            'email': employee.user.email,
            'full_name': employee.full_name,
            'department': employee.department,
            'position': employee.position
        }
        
        # Delete the user (this will cascade delete the employee profile)
        employee.user.delete()
        
        # Log employee deletion
        try:
            from users.services import ActivityLogger
            
            ActivityLogger.log_activity(
                action_type='user_deleted',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'deleted_employee': employee_details,
                    'deleted_by': request.user.username
                }
            )
        except Exception as log_error:
            print(f"Error logging employee deletion: {log_error}")
        
        return Response({'message': 'Employee deleted successfully'})
    except EmployeeProfile.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=404)

import json
import traceback
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from employees.models import EmployeeProfile, Position, Department, PositionLevel

User = get_user_model()

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def get_employee(request, id):
    try:
        emp = EmployeeProfile.objects.get(id=id, user__company=request.user.company)
        user = emp.user

        if request.method == 'GET':
            # Add access_level to the response data
            data = {
                'id': emp.id,
                'username': user.username,
                'email': user.email,
                'full_name': emp.full_name,
                'dob': emp.dob,
                'address': emp.address,
                'position': emp.position,
                'department': emp.department,
                'role': user.user_role.name if user.user_role else '',
                'role_id': user.user_role.id if user.user_role else None,
                'positional_level': emp.positional_level,
                'date_of_joining': emp.date_of_joining,
                'profile_photo': emp.profile_photo.url if emp.profile_photo else None,
                'aadhaar_card': emp.aadhaar_card.url if emp.aadhaar_card else None,
                'additional_document': emp.additional_document.url if emp.additional_document else None,
                'is_active': user.is_active,
                'access_level': user.access_level if hasattr(user, 'access_level') else 'basic',
                'additional_documents': emp.additional_documents
            }

            return Response({
                'success': 'Employee data retrieved successfully',
                'id': emp.id,
                'username': user.username,
                'email': user.email,
                'full_name': emp.full_name,
                'department': emp.department,
                'position': emp.position,
                'role': emp.role,
                'positional_level': emp.positional_level,
                'access_level': user.access_level if hasattr(user, 'access_level') else 'basic',
                'additional_documents': emp.additional_documents,
                'dob': emp.dob,
                'address': emp.address,
                'date_of_joining': emp.date_of_joining,
                'profile_photo': emp.profile_photo.url if emp.profile_photo else None,
                'aadhaar_card': emp.aadhaar_card.url if emp.aadhaar_card else None,
                'additional_document': emp.additional_document.url if emp.additional_document else None,
                'is_active': user.is_active,
                'role_id': user.user_role.id if user.user_role else None,
            })

        elif request.method == 'PUT':
            # Store original values for activity logging
            original_data = {
                'username': user.username,
                'email': user.email,
                'full_name': emp.full_name,
                'department': emp.department,
                'position': emp.position,
                'role': emp.role,
                'positional_level': emp.positional_level,
                'access_level': getattr(user, 'access_level', 'basic')
            }
            
            # === USER BASIC INFO ===
            username = request.data.get('username')
            email = request.data.get('email')
            password = request.data.get('password')
            
            # Update username if provided
            if username and username != user.username:
                # Check if username is already taken
                if User.objects.filter(username=username).exclude(id=user.id).exists():
                    return Response({'error': 'Username already taken'}, status=400)
                user.username = username

            # Update email if provided
            if email and email != user.email:
                # Check if email is already taken
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    return Response({'error': 'Email already taken'}, status=400)
                user.email = email

            # Update password if provided
            if password:
                user.password = make_password(password)
            
            # === EMPLOYEE PROFILE BASIC ===
            emp.full_name = request.data.get('full_name', emp.full_name)
            emp.dob = request.data.get('dob', emp.dob)
            emp.address = request.data.get('address', emp.address)
            emp.date_of_joining = request.data.get('date_of_joining', emp.date_of_joining)
            
            # Get department, position, role, and positional_level IDs
            department_id = request.data.get('department')
            position_id = request.data.get('position')
            role_id = request.data.get('role')
            positional_level_id = request.data.get('positional_level')
            
            # New: Get access_level
            access_level = request.data.get('access_level')
            
            # Update department if provided
            if department_id:
                try:
                    department = Department.objects.get(id=department_id)
                    emp.department = department.name
                    user.department = department
                except Department.DoesNotExist:
                    pass
            
            # Update position if provided
            if position_id:
                try:
                    position = Position.objects.get(id=position_id)
                    emp.position = position.name
                    user.position = position
                except Position.DoesNotExist:
                    pass
            
            # Update role if provided
            role_changed = False
            if role_id:
                try:
                    role = Role.objects.get(id=role_id)
                    role_changed = (not user.user_role or user.user_role.id != role.id)
                    emp.role = role.name
                    user.user_role = role
                    
                    # If role changed and access_level wasn't explicitly provided,
                    # update access_level from the new role
                    if role_changed and not access_level and hasattr(role, 'access_level'):
                        access_level = role.access_level
                        print(f"Updating access_level to '{access_level}' based on new role")
                    
                    # If user has custom permissions flag wasn't set, 
                    # update user permissions based on role
                    if request.data.get('has_custom_permissions') != 'true':
                        # Clear existing permissions and set to role's permissions
                        user.permissions.clear()
                        for permission in role.permissions.all():
                            user.permissions.add(permission)
                except Role.DoesNotExist:
                    pass
            
            # Update access_level if provided or set from new role
            if access_level:
                user.access_level = access_level
                # Also update in profile if you store it there
                if hasattr(emp, 'access_level'):
                    emp.access_level = access_level
                print(f"Access level updated to: {access_level}")
            
            # Update positional level if provided
            if positional_level_id:
                try:
                    positional_level = PositionLevel.objects.get(id=positional_level_id)
                    emp.positional_level = positional_level.name
                    user.positional_level = positional_level
                except PositionLevel.DoesNotExist:
                    pass
            
            # Handle file uploads if provided
            if 'profile_photo' in request.FILES:
                emp.profile_photo = request.FILES['profile_photo']
            
            if 'aadhaar_card' in request.FILES:
                emp.aadhaar_card = request.FILES['aadhaar_card']
            
            if 'additional_document' in request.FILES:
                emp.additional_document = request.FILES['additional_document']
            
            # === HANDLE DOCUMENT UPLOADS AND DELETIONS ===
            try:
                # Check if there are new documents to process
                has_new_documents = request.data.get('has_new_documents')
                
                # Process document files only if the flag is set
                if has_new_documents == 'true':
                    additional_documents_data = request.data.get('additional_documents')
                    
                    if additional_documents_data:
                        import json
                        from datetime import datetime
                        
                        # Parse the JSON string to get the document data
                        documents_data = json.loads(additional_documents_data) if isinstance(additional_documents_data, str) else additional_documents_data
                        print(f"Processing additional documents: {documents_data}")
                        
                        # Ensure additional_documents exists
                        if not emp.additional_documents:
                            emp.additional_documents = {}
                        
                        # Process each document entry
                        for doc_key, doc_info in documents_data.items():
                            if 'file_key' in doc_info:
                                # Get the file key used in the upload
                                file_key = doc_info['file_key']
                                
                                # Check if this file is in the request.FILES
                                if file_key in request.FILES:
                                    file = request.FILES[file_key]
                                    doc_name = doc_info.get('name', file.name)
                                    
                                    # Generate a unique ID for the document
                                    import uuid
                                    import os
                                    
                                    doc_id = str(uuid.uuid4())
                                    
                                    # Get a safe filename
                                    original_name = file.name
                                    file_ext = os.path.splitext(original_name)[1].lower()
                                    safe_name = f"{uuid.uuid4()}{file_ext}"
                                    
                                    # Set upload path
                                    relative_path = f"documents/employee_{emp.id}/{safe_name}"
                                    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                                    
                                    # Create directory if not exists
                                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                    
                                    # Save file to disk
                                    with open(full_path, 'wb+') as destination:
                                        for chunk in file.chunks():
                                            destination.write(chunk)
                                    
                                    # Add document info to employee's documents
                                    emp.additional_documents[doc_id] = {
                                        'name': doc_name,
                                        'file_path': relative_path,
                                        'url': f"/media/{relative_path}",
                                        'uploaded_at': datetime.now().isoformat()
                                    }
                                    
                                    print(f"Added new document with ID: {doc_id}")
                
                # Process deleted document IDs
                deleted_doc_ids = request.data.get('deleted_document_ids')
                if deleted_doc_ids:
                    import json
                    
                    # Parse JSON if it's a string
                    deleted_ids = json.loads(deleted_doc_ids) if isinstance(deleted_doc_ids, str) else deleted_doc_ids
                    print(f"Deleted document IDs: {deleted_ids}")
                    
                    # Ensure additional_documents exists
                    if not emp.additional_documents:
                        emp.additional_documents = {}
                    
                    # Remove each deleted document
                    for doc_id in deleted_ids:
                        if doc_id in emp.additional_documents:
                            del emp.additional_documents[doc_id]
                            print(f"Deleted document with ID: {doc_id}")
                
            except Exception as doc_error:
                print(f"Error handling additional documents: {doc_error}")
                import traceback
                traceback.print_exc()
            
            # Handle custom permissions if provided
            if request.data.get('has_custom_permissions') == 'true':
                try:
                    # Clear existing permissions first
                    user.permissions.clear()
                    print(f"Cleared existing permissions for user {user.username}")
                    
                    # Track all permission IDs and codes to be added
                    permission_ids = []
                    permission_codes = []
                    
                    # Debug request data
                    print("\n=== PERMISSION DEBUG INFO ===")
                    print(f"has_custom_permissions: {request.data.get('has_custom_permissions')}")
                    print(f"permission_ids: {request.data.get('permission_ids')}")
                    print(f"user_permissions: {request.data.get('user_permissions')}")
                    print(f"permission_codes: {request.data.get('permission_codes')}")
                    print("===========================\n")
                    
                    # Extract permission IDs - Method 1: user_permissions as JSON array
                    user_perms = request.data.get('user_permissions')
                    if user_perms:
                        if isinstance(user_perms, str):
                            import json
                            try:
                                perm_data = json.loads(user_perms)
                                if isinstance(perm_data, list):
                                    for pid in perm_data:
                                        try:
                                            pid_int = int(pid)
                                            if pid_int not in permission_ids:
                                                permission_ids.append(pid_int)
                                        except (ValueError, TypeError):
                                            pass
                                print(f"Added {len(permission_ids)} permission IDs from user_permissions JSON")
                            except json.JSONDecodeError:
                                print("Failed to parse user_permissions as JSON")
                    
                    # Extract permission IDs - Method 2: permission_ids as comma-separated string
                    direct_ids = request.data.get('permission_ids')
                    if direct_ids and isinstance(direct_ids, str):
                        ids_list = [id.strip() for id in direct_ids.split(',') if id.strip()]
                        for pid in ids_list:
                            if pid.isdigit():
                                pid_int = int(pid)
                                if pid_int not in permission_ids:
                                    permission_ids.append(pid_int)
                        print(f"Added {len(ids_list)} permission IDs from comma-separated string")
                    
                    # Extract permission codes
                    perm_codes = request.data.get('permission_codes')
                    if perm_codes:
                        if isinstance(perm_codes, str):
                            import json
                            try:
                                codes_data = json.loads(perm_codes)
                                if isinstance(codes_data, list):
                                    permission_codes.extend([code for code in codes_data if code])
                                print(f"Added {len(permission_codes)} permission codes from JSON")
                            except json.JSONDecodeError:
                                print("Failed to parse permission_codes as JSON")
                    
                    print(f"Will process {len(permission_ids)} permission IDs and {len(permission_codes)} permission codes")
                        
                    # Add permissions by ID
                    from companies.models import Permission
                    added_count = 0
                    for permission_id in permission_ids:
                        try:
                            permission = Permission.objects.get(id=permission_id)
                            user.permissions.add(permission)
                            added_count += 1
                            print(f"Added permission by ID: {permission_id} -> {permission.name}")
                        except Permission.DoesNotExist:
                            print(f"Warning: Permission with ID {permission_id} not found")
                        except Exception as e:
                            print(f"Error adding permission by ID {permission_id}: {str(e)}")
                    
                    # Add permissions by code
                    for code in permission_codes:
                        try:
                            permission = Permission.objects.get(code=code)
                            user.permissions.add(permission)
                            added_count += 1
                            print(f"Added permission by code: {code} -> {permission.name}")
                        except Permission.DoesNotExist:
                            print(f"Warning: Permission with code '{code}' not found")
                        except Exception as e:
                            print(f"Error adding permission by code {code}: {str(e)}")
                    
                    # Final count
                    print(f"Successfully added {added_count} permissions to user {user.username}")
                    
                except Exception as perm_error:
                    print(f"Error updating permissions: {perm_error}")
                    import traceback
                    traceback.print_exc()
            
            # === FINAL SAVE ===
            user.save()
            emp.save()
            
            # After successful update, log the activity
            try:
                from users.services import ActivityLogger
                
                # Identify which fields changed
                changed_fields = []
                if original_data['username'] != user.username:
                    changed_fields.append(f"username: {original_data['username']} → {user.username}")
                if original_data['email'] != user.email:
                    changed_fields.append(f"email: {original_data['email']} → {user.email}")
                if original_data['full_name'] != emp.full_name:
                    changed_fields.append(f"full_name: {original_data['full_name']} → {emp.full_name}")
                if original_data['department'] != emp.department:
                    changed_fields.append(f"department: {original_data['department']} → {emp.department}")
                if original_data['position'] != emp.position:
                    changed_fields.append(f"position: {original_data['position']} → {emp.position}")
                if original_data['role'] != emp.role:
                    changed_fields.append(f"role: {original_data['role']} → {emp.role}")
                if original_data['positional_level'] != emp.positional_level:
                    changed_fields.append(f"positional_level: {original_data['positional_level']} → {emp.positional_level}")
                # Check if access_level changed
                current_access_level = user.access_level if hasattr(user, 'access_level') else 'basic'
                if original_data['access_level'] != current_access_level:
                    changed_fields.append(f"access_level: {original_data['access_level']} → {current_access_level}")
                if request.data.get('password'):
                    changed_fields.append("password: [changed]")
                
                # Check if permissions were updated
                if request.data.get('has_custom_permissions') == 'true':
                    changed_fields.append("permissions: [updated]")
                
                # Only log if something actually changed
                if changed_fields:
                    ActivityLogger.log_activity(
                        action_type='user_updated',
                        performed_by=request.user,
                        company=request.user.company,
                        details={
                            'employee_id': emp.id,
                            'username': user.username,
                            'changes': changed_fields,
                            'updated_by': request.user.username
                        }
                    )
            except Exception as log_error:
                print(f"Error logging employee update: {log_error}")

            # Return the updated employee data including the additional_documents in the response
            return Response({
                'success': 'Employee updated successfully',
                'id': emp.id,
                'username': user.username,
                'email': user.email,
                'full_name': emp.full_name,
                'department': emp.department,
                'position': emp.position,
                'role': emp.role,
                'positional_level': emp.positional_level,
                'access_level': user.access_level if hasattr(user, 'access_level') else 'basic',
                'additional_documents': emp.additional_documents,  # Include the updated documents
                'dob': emp.dob,
                'address': emp.address,
                'date_of_joining': emp.date_of_joining,
                'profile_photo': emp.profile_photo.url if emp.profile_photo else None,
                'aadhaar_card': emp.aadhaar_card.url if emp.aadhaar_card else None,
                'additional_document': emp.additional_document.url if emp.additional_document else None,
                'is_active': user.is_active,
                'role_id': user.user_role.id if user.user_role else None,
            })

    except EmployeeProfile.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)                   
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Department

# views.py
from rest_framework.exceptions import AuthenticationFailed

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from .models import Department


# employees/views.py
# Department CRUD operations with logging
# from .models import Department, Position, Employee  # Import the required models

@api_view(['POST', 'GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def department_view(request, pk=None):
    if request.method == "POST":
        # Ensure the user is authenticated and has a company assigned
        if not request.user.is_authenticated:
            raise AuthenticationFailed("User is not authenticated")

        name = request.data.get("name")
        if not name:
            return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)

        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "Company not assigned to user"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if department already exists with this name in the company
        if Department.objects.filter(name=name, company=company).exists():
            return Response({"error": "A department with this name already exists"}, status=status.HTTP_400_BAD_REQUEST)

        department = Department.objects.create(name=name, company=company)
        
        # Log department creation
        try:
            from users.services import ActivityLogger
            
            ActivityLogger.log_activity(
                action_type='department_created',
                performed_by=request.user,
                company=company,
                details={
                    'department_id': department.id,
                    'department_name': department.name,
                    'created_by': request.user.username
                }
            )
        except Exception as log_error:
            print(f"Error logging department creation: {log_error}")
        
        return Response({
            "message": "Department created", 
            "id": department.id,
            "name": department.name,
            "company_id": company.id
        }, status=status.HTTP_201_CREATED)

    # Update the GET method part in your department_view function:

    elif request.method == "GET":
        # GET handling with more detailed response
        if not request.user.is_authenticated:
            raise AuthenticationFailed("User is not authenticated")
    
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "Company not assigned to user"}, status=status.HTTP_400_BAD_REQUEST)
    
        # Check if specific department_id filter is provided
        filter_department_id = request.query_params.get('department_id')
        
        # If pk is provided, return specific department
        if pk:
            try:
                department = Department.objects.get(id=pk, company=company)
                
                # Get position count for this department
                position_count = Position.objects.filter(department=department).count()
                
                # Try to get employee count safely
                try:
                    employee_count = Employee.objects.filter(department=department).count()
                except Exception as e:
                    print(f"Error counting employees: {e}")
                    employee_count = 0  # Default if Employee model isn't available
                    
                return Response({
                    "id": department.id, 
                    "name": department.name,
                    "company_id": company.id,
                    "position_count": position_count,
                    "employee_count": employee_count
                })
            except Department.DoesNotExist:
                return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Filter departments if department_id is provided
        if filter_department_id:
            try:
                departments = Department.objects.filter(id=filter_department_id, company=company)
            except Exception as e:
                print(f"Error filtering departments: {e}")
                return Response({"error": "Invalid department ID filter"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Otherwise return all departments for the company
            departments = Department.objects.filter(company=company)
        
        # Enhanced department list with additional info
        departments_data = []
        
        for dept in departments:
            position_count = Position.objects.filter(department=dept).count()
            
            # Try to get employee count safely
            try:
                employee_count = Employee.objects.filter(department=dept).count()
            except Exception as e:
                print(f"Error counting employees: {e}")
                employee_count = 0  # Default if Employee model isn't available
            
            departments_data.append({
                "id": dept.id, 
                "name": dept.name,
                "company_id": company.id,
                "position_count": position_count,
                "employee_count": employee_count
            })
            
        return Response(departments_data)
    elif request.method == "PUT":
        if not pk:
            return Response({"error": "Department ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        name = request.data.get("name")
        if not name:
            return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "Company not assigned to user"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            department = Department.objects.get(id=pk, company=company)
            
            # Check if another department with same name already exists
            if Department.objects.filter(name=name, company=company).exclude(id=pk).exists():
                return Response({"error": "Another department with this name already exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            old_name = department.name
            department.name = name
            department.save()
            
            # Get updated counts
            position_count = Position.objects.filter(department=department).count()
            
            # Try to get employee count safely
            try:
                employee_count = Employee.objects.filter(department=department).count()
            except Exception as e:
                print(f"Error counting employees: {e}")
                employee_count = 0  # Default if Employee model isn't available
            
            # Log department update
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type='department_updated',
                    performed_by=request.user,
                    company=company,
                    details={
                        'department_id': department.id,
                        'previous_name': old_name,
                        'new_name': department.name,
                        'updated_by': request.user.username
                    }
                )
            except Exception as log_error:
                print(f"Error logging department update: {log_error}")
            
            return Response({
                "message": "Department updated", 
                "id": department.id,
                "name": department.name,
                "company_id": company.id,
                "position_count": position_count,
                "employee_count": employee_count
            }, status=status.HTTP_200_OK)
        except Department.DoesNotExist:
            return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == "DELETE":
        if not pk:
            return Response({"error": "Department ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "Company not assigned to user"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            department = Department.objects.get(id=pk, company=company)
            
            # Check if department has positions or employees
            position_count = Position.objects.filter(department=department).count()
            
            # Try to get employee count safely
            try:
                employee_count = Employee.objects.filter(department=department).count()
            except Exception as e:
                print(f"Error counting employees: {e}")
                employee_count = 0  # Default if Employee model isn't available
            
            if position_count > 0 or employee_count > 0:
                return Response({
                    "error": "Cannot delete department with associated positions or employees. " +
                    f"This department has {position_count} positions and {employee_count} employees."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            dept_name = department.name
            dept_id = department.id
            department.delete()
            
            # Log department deletion
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type='department_deleted',
                    performed_by=request.user,
                    company=company,
                    details={
                        'department_id': dept_id,
                        'department_name': dept_name,
                        'deleted_by': request.user.username
                    }
                )
            except Exception as log_error:
                print(f"Error logging department deletion: {log_error}")
            
            return Response({
                "message": f"Department '{dept_name}' deleted successfully",
                "id": dept_id,
                "name": dept_name,
                "company_id": company.id
            }, status=status.HTTP_200_OK)
        except Department.DoesNotExist:
            return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)
from .models import Position


# Position management with activity logging
@api_view(["POST", "GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def position_view(request, position_id=None):
    # Get the company_id from the logged-in user
    company = getattr(request.user, 'company', None)
    
    if not company:
        return JsonResponse({"error": "Company not assigned to user"}, status=400)

    # Handle GET request for individual position
    if request.method == "GET" and position_id is not None:
        try:
            position = Position.objects.get(id=position_id, company=company)
            response_data = {
                "id": position.id,
                "name": position.name,
                "company_id": position.company.id
            }
            
            # Include department info if available
            if position.department:
                response_data["department_id"] = position.department.id
                response_data["department_name"] = position.department.name
                
            return JsonResponse(response_data)
        except Position.DoesNotExist:
            return JsonResponse({"error": "Position not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    # Handle GET request for all positions
    elif request.method == "GET":
        try:
            # Check if department_id filter is provided
            department_id = request.query_params.get('department_id')
            team_id = request.query_params.get('team_id')
            user_id = request.query_params.get('user_id')

            # Base query
            query = Position.objects.filter(company=company)

            # Add department filter if provided
            if department_id:
                query = query.filter(department_id=department_id)
                
            # Add team filter if provided
            if team_id:
                query = query.filter(department__teams__id=team_id)
                
            # Add user filter if provided
            if user_id:
                query = query.filter(employees__id=user_id)

            # Get positions with related department info
            positions_data = []
            for position in query:
                position_data = {
                    "id": position.id,
                    "name": position.name,
                    "company_id": position.company.id,
                }
                
                # Add department info if available
                if position.department:
                    position_data["department_id"] = position.department.id
                    position_data["department_name"] = position.department.name
                    
                positions_data.append(position_data)
                
            return JsonResponse(positions_data, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    # Handle POST request to create a new position
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get("name")
            department_id = data.get("department_id")
    
            if not name:
                return JsonResponse({"error": "Name is required"}, status=400)
    
            # Check if department exists if provided
            department = None
            if department_id:
                try:
                    department = Department.objects.get(id=department_id, company=company)
                except Department.DoesNotExist:
                    return JsonResponse({"error": "Department not found"}, status=404)
    
            # Create position
            position = Position.objects.create(
                name=name, 
                company=company,
                department=department
            )
            
            # Log position creation
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type='position_created',
                    performed_by=request.user,
                    company=company,
                    details={
                        'position_id': position.id,
                        'position_name': position.name,
                        'created_by': request.user.username
                    }
                )
            except Exception as log_error:
                print(f"Error logging position creation: {log_error}")
            
            # Prepare response with department info if available
            response_data = {
                "message": "Position created successfully",
                "id": position.id,
                "name": position.name
            }
            
            if department:
                response_data["department_id"] = department.id
                response_data["department_name"] = department.name
                
            return JsonResponse(response_data, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    # Handle PUT request to update a position
    elif request.method == "PUT" and position_id is not None:
        try:
            position = Position.objects.get(id=position_id, company=company)
            data = json.loads(request.body)
            name = data.get("name")
            department_id = data.get("department_id")
            
            if not name:
                return JsonResponse({"error": "Name is required"}, status=400)
            
            # Check if another position with same name already exists in this company
            if Position.objects.filter(name=name, company=company).exclude(id=position_id).exists():
                return JsonResponse({"error": "A position with this name already exists"}, status=400)
            
            old_name = position.name
            position.name = name
            
            # Update department if provided
            department = None
            if department_id:
                try:
                    department = Department.objects.get(id=department_id, company=company)
                    position.department = department
                except Department.DoesNotExist:
                    return JsonResponse({"error": "Department not found"}, status=404)
            
            position.save()
            
            # Log position update
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type='position_updated',
                    performed_by=request.user,
                    company=company,
                    details={
                        'position_id': position.id,
                        'previous_name': old_name,
                        'new_name': position.name,
                        'updated_by': request.user.username
                    }
                )
            except Exception as log_error:
                print(f"Error logging position update: {log_error}")
            
            # Prepare response with department info
            response_data = {
                "message": "Position updated successfully",
                "id": position.id,
                "name": position.name
            }
            
            if position.department:
                response_data["department_id"] = position.department.id
                response_data["department_name"] = position.department.name
                
            return JsonResponse(response_data)
            
        except Position.DoesNotExist:
            return JsonResponse({"error": "Position not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    # Handle DELETE request to delete a position
    elif request.method == "DELETE" and position_id is not None:
        try:
            position = Position.objects.get(id=position_id, company=company)
            position_name = position.name
            position_id = position.id
            
            # Get department info before deletion if available
            department_info = None
            if position.department:
                department_info = {
                    "id": position.department.id,
                    "name": position.department.name
                }
            
            position.delete()
            
            # Log position deletion
            try:
                from users.services import ActivityLogger
                
                ActivityLogger.log_activity(
                    action_type='position_deleted',
                    performed_by=request.user,
                    company=company,
                    details={
                        'position_id': position_id,
                        'position_name': position_name,
                        'deleted_by': request.user.username
                    }
                )
            except Exception as log_error:
                print(f"Error logging position deletion: {log_error}")
            
            response_data = {
                "message": f"Position '{position_name}' deleted successfully"
            }
            
            # Include department info in response if available
            if department_info:
                response_data["department_id"] = department_info["id"]
                response_data["department_name"] = department_info["name"]
                
            return JsonResponse(response_data)
            
        except Position.DoesNotExist:
            return JsonResponse({"error": "Position not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)
    
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Department, Position

@api_view(['GET'])
def get_departments(request):
    departments = Department.objects.all().values('id', 'name')
    return Response(departments)

@api_view(['GET'])
def get_positions(request):
    company_id = request.query_params.get('company_id')
    department_id = request.query_params.get('department_id')
    
    # Start with filtering positions by company
    positions = Position.objects.filter(company_id=company_id)
    
    # If department_id is provided, filter positions for that department
    if department_id:
        positions = positions.filter(department_id=department_id)
    
    # Convert to list of dictionaries
    position_list = list(positions.values('id', 'name', 'department_id'))
    
    return Response(position_list)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_employee_documents(request):
    user_company = request.user.company
    employees = EmployeeProfile.objects.select_related('user').filter(user__company=user_company)

    data = []
    for emp in employees:
        data.append({
            "id": emp.id,
            "full_name": emp.full_name,
            "email": emp.user.email,
            "username": emp.user.username,
            "role": emp.user.role,
            "department": emp.department,
            "position": emp.position,
            "profile_photo": emp.profile_photo.url if emp.profile_photo else None,
            "aadhaar_card": emp.aadhaar_card.url if emp.aadhaar_card else None,
            "additional_document": emp.additional_document.url if emp.additional_document else None,
        })
    
    return Response(data)


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from django.core.exceptions import ValidationError
from .models import PositionLevel, Department, Position
from companies.models import Company, Role
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# views.py with activity logging implementation

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from companies.models import Company
from employees.models import PositionLevel
from users.services import ActivityLogger
import json
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def position_level_view(request, position_level_id=None):
    """
    Handle CRUD operations for PositionLevel with activity logging.

    - GET (with position_level_id): Retrieve one
    - GET (with company_id): List all for a company
    - POST: Create new
    - PUT: Update existing
    - DELETE: Delete one
    """

    if request.method == 'GET':
        if position_level_id:
            try:
                position_level = PositionLevel.objects.get(id=position_level_id)
                
                # Log the activity - viewing a specific position level
                ActivityLogger.log_activity(
                    action_type='position_level_viewed',
                    performed_by=request.user,
                    company=position_level.company,
                    details={
                        'position_level_id': position_level.id,
                        'position_level_name': position_level.name
                    }
                )
                
                return Response({
                    'id': position_level.id,
                    'name': position_level.name,
                    'company_id': position_level.company.id,
                    'department_id': position_level.department.id if position_level.department else None
                }, status=status.HTTP_200_OK)
            except PositionLevel.DoesNotExist:
                return Response({'error': f'Position level with ID {position_level_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({'error': 'company_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=company_id)
            levels = PositionLevel.objects.filter(company=company)
            
            # Log the activity - listing all position levels for a company
            ActivityLogger.log_activity(
                action_type='position_levels_listed',
                performed_by=request.user,
                company=company,
                details={
                    'count': levels.count()
                }
            )
            
            return Response([
                {
                    'id': lvl.id, 
                    'name': lvl.name, 
                    'company_id': lvl.company.id,
                    'department_id': lvl.department.id if lvl.department else None
                }
                for lvl in levels
            ], status=status.HTTP_200_OK)
        except Company.DoesNotExist:
            return Response({'error': f'Company with ID {company_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)


    # POST method
    if request.method == 'POST':
        company_id = data.get('company_id')
        name = data.get('name')
        department_id = data.get('department_id')

        if not company_id or not name:
            return Response({'error': 'Both company_id and name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': f'Company with ID {company_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        if PositionLevel.objects.filter(company=company, name__iexact=name.strip()).exists():
            return Response({'error': f'A position level with name "{name}" already exists in this company.'}, status=status.HTTP_400_BAD_REQUEST)

        # Set department if provided
        department = None
        if department_id:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                return Response({'error': f'Department with ID {department_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        position_level = PositionLevel.objects.create(
            name=name.strip(), 
            company=company,
            department=department
        )
        
        # Log the activity - creating a position level
        ActivityLogger.log_activity(
            action_type='position_level_created',
            performed_by=request.user,
            company=company,
            details={
                'position_level_id': position_level.id,
                'position_level_name': position_level.name,
                'department_id': department.id if department else None
            }
        )
        
        return Response({
            'success': True,
            'id': position_level.id,
            'name': position_level.name,
            'company_id': position_level.company.id,
            'department_id': position_level.department.id if position_level.department else None,
            'message': 'Position level created successfully'
        }, status=status.HTTP_201_CREATED)

    elif request.method == 'PUT':
        if not position_level_id:
            return Response({'error': 'Position level ID is required for update operations.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            position_level = PositionLevel.objects.get(id=position_level_id)
            old_name = position_level.name
        except PositionLevel.DoesNotExist:
            return Response({'error': f'Position level with ID {position_level_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        name = data.get('name')
        company_id = data.get('company_id')

        if not name or not company_id:
            return Response({'error': 'Both name and company_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({'error': f'Company with ID {company_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        if PositionLevel.objects.filter(company=company, name__iexact=name.strip()).exclude(id=position_level_id).exists():
            return Response({'error': f'A position level with name "{name}" already exists in this company.'}, status=status.HTTP_400_BAD_REQUEST)

        # Keep track of changes
        changes = {}
        if position_level.name != name.strip():
            changes['name'] = {'from': position_level.name, 'to': name.strip()}
        
        if position_level.company.id != company.id:
            changes['company'] = {'from': position_level.company.id, 'to': company.id}

        position_level.name = name.strip()
        position_level.company = company
        position_level.save()

        # Log the activity - updating a position level
        ActivityLogger.log_activity(
            action_type='position_level_updated',
            performed_by=request.user,
            company=company,
            details={
                'position_level_id': position_level.id,
                'position_level_name': position_level.name,
                'changes': changes
            }
        )

        return Response({
            'success': True,
            'id': position_level.id,
            'name': position_level.name,
            'company_id': company.id,
            'message': 'Position level updated successfully'
        }, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        if not position_level_id:
            return Response({'error': 'Position level ID is required for delete operations.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            position_level = PositionLevel.objects.get(id=position_level_id)
            company = position_level.company
            position_level_name = position_level.name

            employee_count = getattr(position_level, 'employees', []).count() if hasattr(position_level, 'employees') else 0
            if employee_count > 0:
                return Response({'error': f'Cannot delete position level that is assigned to {employee_count} employees.'}, status=status.HTTP_400_BAD_REQUEST)

            position_level.delete()
            
            # Log the activity - deleting a position level
            ActivityLogger.log_activity(
                action_type='position_level_deleted',
                performed_by=request.user,
                company=company,
                details={
                    'position_level_name': position_level_name
                }
            )
            
            return Response({'success': True, 'message': 'Position level deleted successfully'}, status=status.HTTP_200_OK)

        except PositionLevel.DoesNotExist:
            return Response({'error': f'Position level with ID {position_level_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Error deleting position level: {str(e)}")
            return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_position_levels(request):
    """
    Get all position levels for the current user's company with activity logging
    """
    try:
        # Handle users who don't have an EmployeeProfile
        company = None
        
        if hasattr(request.user, 'employeeprofile'):
            company = request.user.employeeprofile.company
        elif hasattr(request.user, 'company'):
            company = request.user.company
        elif request.GET.get('company_id'):
            # Allow specifying company_id as query parameter
            company_id = request.GET.get('company_id')
            company = Company.objects.get(id=company_id)
        else:
            # If still no company, try to find related companies
            # For admin users who may manage multiple companies
            companies = Company.objects.all()
            if companies.exists():
                company = companies.first()
        
        if not company:
            return Response(
                {"error": "Could not determine company. Please specify a company_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Get all position levels for this company
        position_levels = PositionLevel.objects.filter(company=company)
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='position_levels_viewed',
            performed_by=request.user,
            company=company,
            details={
                'count': position_levels.count()
            }
        )
        
        # Prepare response data
        data = []
        for level in position_levels:
            level_data = {
                'id': level.id,
                'name': level.name,
                'company_id': company.id,
                'company': company.id  # For compatibility with existing code
            }
            data.append(level_data)
            
        return Response(data)
        
    except Exception as e:
        logger.error(f"Error in get_position_levels: {str(e)}")
        return Response(
            {"error": "Failed to fetch position levels.", "details": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from companies.models import Role

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_roles(request):
    """
    Get all roles for a company with activity logging.
    Used by the position level form to populate the role dropdown.
    """
    try:
        # Get the user's company or the specified company_id
        company_id = request.GET.get('company_id')
        
        if not company_id and hasattr(request.user, 'company') and request.user.company:
            company_id = request.user.company.id
        
        if not company_id:
            return JsonResponse({'error': 'No company specified'}, status=400)
            
        # Query roles for the company
        company = Company.objects.get(id=company_id)
        roles = Role.objects.filter(company_id=company_id)
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='roles_viewed',
            performed_by=request.user,
            company=company,
            details={
                'count': roles.count()
            }
        )
        
        # Serialize to JSON
        roles_data = []
        for role in roles:
            roles_data.append({
                'id': role.id,
                'name': role.name,
                'is_default': role.is_default
            })
            
        return JsonResponse(roles_data, safe=False)
        
    except Exception as e:
        logger.error(f"Error in get_roles: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_employee_permissions(request, employee_id):


    """
    Get employee permissions with activity logging
    """
    try:
        # Implementation goes here
        
        # After retrieving the employee permissions
        employee = User.objects.get(id=employee_id)
        company = employee.company
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='employee_permissions_viewed',
            performed_by=request.user,
            company=company,
            details={
                'employee_id': employee_id,
                'employee_name': f"{employee.first_name} {employee.last_name}"
            }
        )
        
        # Return the permissions data
        # ...
        
    except Exception as e:
        logger.error(f"Error getting employee permissions: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



import json
import uuid
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import (
    EmployeeProfile, EmployeeFaceData, Attendance, AttendanceLog,
    EmployeeLocation, Shift, UserShift
)
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.files.base import ContentFile
import json
import base64
import uuid
from datetime import datetime
import face_recognition
import numpy as np
import json
            
from employees.models import EmployeeProfile
from .models import EmployeeFaceData, Attendance, AttendanceLog

# Helper function to convert base64 to file
def base64_to_image(base64_string, file_name=None):
    if base64_string.startswith('data:image'):
        # Strip the data:image/png;base64, part
        format, imgstr = base64_string.split(';base64,')
        ext = format.split('/')[-1]
        if not file_name:
            file_name = f"{uuid.uuid4()}.{ext}"
        return ContentFile(base64.b64decode(imgstr), name=file_name)
    return None

# Check if employee has registered face data
@permission_classes([IsAuthenticated])
def has_face_data(request):
    """Check if the employee has registered face data"""
    try:
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        has_data = EmployeeFaceData.objects.filter(employee=employee).exists()
        
        return JsonResponse({
            'success': True,
            'has_face_data': has_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

from django.core.files.storage import FileSystemStorage
import os
from django.conf import settings

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_face_data(request):
    """Register employee face data"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)
    
    try:
        # Parse JSON data from request
        data = json.loads(request.body)
        face_image_data = data.get('face_image')
        default_latitude = data.get('default_latitude')
        default_longitude = data.get('default_longitude')
        
        # Validate required fields
        if not face_image_data:
            return JsonResponse({'success': False, 'message': 'Face image is required'}, status=400)
        
        # Get employee profile
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        
        # Process face image
        face_image_file = base64_to_image(face_image_data, f"face_{employee.id}_{uuid.uuid4()}.png")
        if not face_image_file:
            return JsonResponse({'success': False, 'message': 'Invalid image data'}, status=400)
        
        # Save image temporarily using FileSystemStorage
        fs = FileSystemStorage()
        image_name = f"face_{employee.id}_{uuid.uuid4()}.png"
        image_path = fs.save(image_name, face_image_file)

        # Get the actual file system path
        full_image_path = os.path.join(settings.MEDIA_ROOT, image_path)

        # Generate face encoding using face_recognition library
        face_encoding_json = None
        try:
            import face_recognition
            import numpy as np
            
            # Load the image file
            image = face_recognition.load_image_file(full_image_path)
            
            # Get face encoding
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                # Clean up the image file if no face is detected
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                return JsonResponse({
                    'success': False, 
                    'message': 'No face detected in the image. Please try again with a clearer image.'
                }, status=400)
            
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                # Clean up the image file if encoding fails
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                return JsonResponse({
                    'success': False, 
                    'message': 'Could not encode face features. Please try again.'
                }, status=400)
            
            # Convert encoding to JSON string for storage
            face_encoding_json = json.dumps(face_encodings[0].tolist())
            
            # Verify the JSON is valid
            if not face_encoding_json:
                raise ValueError("Failed to convert face encoding to JSON")
            
        except ImportError as e:
            # Log the error and return a specific message
            print(f"Error: face_recognition library is not available: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Face recognition system is currently unavailable. Please contact support.'
            }, status=500)
        except ValueError as e:
            print(f"Error with face encoding: {e}")
            # Clean up the image file if processing fails
            if os.path.exists(full_image_path):
                os.remove(full_image_path)
            return JsonResponse({
                'success': False,
                'message': 'Error processing facial features. Please try again.'
            }, status=500)
        except Exception as e:
            print(f"Error generating face encoding: {e}")
            # Clean up the image file if processing fails
            if os.path.exists(full_image_path):
                os.remove(full_image_path)
            return JsonResponse({
                'success': False,
                'message': 'Error processing facial features. Please try again.'
            }, status=500)
        
        # Check that we have a valid face encoding before proceeding
        if not face_encoding_json:
            return JsonResponse({
                'success': False,
                'message': 'Failed to generate facial encoding. Please try again.'
            }, status=500)
        
        try:
            # Create or update face data
            face_data, created = EmployeeFaceData.objects.get_or_create(
                employee=employee,
                defaults={
                    'face_image': face_image_file,
                    'face_encoding': face_encoding_json,
                    'default_latitude': default_latitude,
                    'default_longitude': default_longitude,
                    'allowed_radius': 100  # Default radius in meters
                }
            )
            
            # Update if not created
            if not created:
                face_data.face_image = face_image_file
                # Ensure we have valid encoding before updating
                face_data.face_encoding = face_encoding_json
                if default_latitude is not None:
                    face_data.default_latitude = default_latitude
                if default_longitude is not None:
                    face_data.default_longitude = default_longitude
                face_data.save()
            
            # Verify the data was saved correctly
            refreshed_data = EmployeeFaceData.objects.get(id=face_data.id)
            if not refreshed_data.face_encoding:
                raise ValueError("Face encoding was not saved properly")
            
            return JsonResponse({
                'success': True,
                'message': 'Face data registered successfully',
                'data': {
                    'id': face_data.id,
                    'created_at': face_data.created_at.isoformat(),
                    'updated_at': face_data.updated_at.isoformat(),
                    'has_encoding': bool(refreshed_data.face_encoding)
                }
            })
        
        except ValueError as e:
            print(f"Error saving face data: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to save face data. Please try again.'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"Error in register_face_data: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_face_data(request):
    """Check if employee has registered face data"""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Only GET method allowed'}, status=405)
    
    try:
        # Get employee profile
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        print(f"Found employee: {employee.id} - {employee.user.username}")

        # Check if face data exists with valid encoding
        try:
            face_data = EmployeeFaceData.objects.get(employee=employee)
            print(f"Found face data: {face_data.id}")
            print(f"Face encoding exists: {bool(face_data.face_encoding)}")
            print(f"Face encoding length: {len(face_data.face_encoding) if face_data.face_encoding else 0}")
            has_face_data = bool(face_data.face_encoding)
        except EmployeeFaceData.DoesNotExist:
            print("No face data found for employee")
            has_face_data = False
        
        print(f"Returning has_face_data: {has_face_data}")
        return JsonResponse({
            'success': True,
            'has_face_data': has_face_data
        })
        
    except Exception as e:
        print(f"Error in check_face_data: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import EmployeeProfile, EmployeeFaceData
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_face_image(request):
    """
    Function-based view to get the employee's registered face image and location data.
    """
    try:
        employee = EmployeeProfile.objects.get(user=request.user)
        
        # Try to get employee's face data
        try:
            face_data = EmployeeFaceData.objects.get(employee=employee)
            
            # Return the face image URL and location data
            return Response({
                'success': True,
                'face_image': request.build_absolute_uri(face_data.face_image.url) if face_data.face_image else None,
                'timestamp': face_data.updated_at,
                'default_latitude': face_data.default_latitude,
                'default_longitude': face_data.default_longitude,
                'allowed_radius': face_data.allowed_radius
            })
        
        except EmployeeFaceData.DoesNotExist:
            return Response({
                'success': False,
                'message': 'No face data registered for this employee',
            }, status=status.HTTP_404_NOT_FOUND)
        
    except EmployeeProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Employee profile not found',
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error retrieving face image: {str(e)}")
        return Response({
            'success': False,
            'message': f'An error occurred: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import json
import uuid
import math
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import (
    EmployeeProfile, EmployeeFaceData, EmployeeLocation, 
    Attendance, AttendanceLog, UserShift
)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000  # Radius of Earth in meters
    distance = c * r
    
    return distance

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    """
    Mark employee attendance with face verification, multiple location support, and automatic shift assignment.
    Handles both default location from face registration and additional locations from EmployeeLocation model.
    Updated to automatically check-out if an open record exists, otherwise create a new check-in record.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Only POST method allowed'}, status=405)
    
    try:
        # First, check if the monitoring app is running
        if not request.user.app_running:
            return JsonResponse({
                'success': False, 
                'message': 'Attendance cannot be marked. Please start the monitoring app on your work computer.'
            }, status=400)
            
        # Parse JSON data from request
        data = json.loads(request.body)
        face_image_data = data.get('face_image')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_id = data.get('location_id')  # Get selected location ID
        device_info = data.get('device_info', {})
        blink_detected = data.get('blink_detected', False)  # Get blink detection status
        force_new_record = data.get('force_new_record', False)  # Optional flag to force a new record
        
        # Debug print for location_id
        print(f"Received location_id: {location_id}, type: {type(location_id)}")
        print(f"Force new record: {force_new_record}")
        
        # Validate required fields
        if not face_image_data:
            return JsonResponse({'success': False, 'message': 'Face image is required'}, status=400)
        
        if not latitude or not longitude:
            return JsonResponse({'success': False, 'message': 'Location data is required'}, status=400)
        
        # Get employee profile
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        
        # Get employee face data
        try:
            face_data = EmployeeFaceData.objects.get(employee=employee)
        except EmployeeFaceData.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Face data not registered. Please register your face first.'
            }, status=400)
        
        # Process face image
        current_face_image = base64_to_image(
            face_image_data, 
            f"attendance_{employee.id}_{uuid.uuid4()}.png"
        )
        
        # Initialize location verification variables
        is_location_verified = False
        verified_location_name = None
        location_distance = None
        min_distance = float('inf')  # Track the closest distance for reporting
        
        # Location verification
        # First check if we're using the default location from face_data
        if location_id == 'default' or not location_id:
            print("Using default location from face registration")
            # Check if default location data exists in face_data
            if face_data.default_latitude is not None and face_data.default_longitude is not None:
                # Calculate distance from the default location
                location_distance = calculate_distance(
                    latitude, longitude,
                    face_data.default_latitude, face_data.default_longitude
                )
                
                # Check if within allowed radius
                allowed_radius = face_data.allowed_radius or 100  # Default 100m if not set
                print(f"Checking default location, distance: {location_distance}, allowed radius: {allowed_radius}")
                
                if location_distance <= allowed_radius:
                    is_location_verified = True
                    verified_location_name = "Default Location"
                    min_distance = location_distance
                    print(f"Default location verified, distance: {location_distance}")
                else:
                    print(f"Outside default location radius, distance: {location_distance}, allowed: {allowed_radius}")
                    min_distance = location_distance  # Store this as the minimum for now
            else:
                print("No default location coordinates found in face data")
        else:
            # Handle specific location selection
            if str(location_id).isdigit():
                try:
                    # Convert location_id to integer
                    location_id_int = int(location_id)
                    
                    # Get the location - ensure it belongs to this employee
                    selected_location = EmployeeLocation.objects.get(
                        id=location_id_int,
                        employee=employee,
                        is_active=True
                    )
                    
                    # Calculate distance from the selected location
                    location_distance = calculate_distance(
                        latitude, longitude,
                        selected_location.latitude, selected_location.longitude
                    )
                    
                    print(f"Checking selected location: {selected_location.location_name}, distance: {location_distance}, allowed radius: {selected_location.allowed_radius}")
                    
                    # Check if the employee is within the allowed radius
                    if location_distance <= selected_location.allowed_radius:
                        is_location_verified = True
                        verified_location_name = selected_location.location_name
                        min_distance = location_distance  # Set the minimum distance
                        print(f"Selected location verified: {verified_location_name}, distance: {location_distance}")
                    else:
                        # Location is outside allowed radius
                        is_location_verified = False
                        min_distance = location_distance
                        print(f"Outside selected location radius: {selected_location.location_name}, distance: {location_distance}, allowed: {selected_location.allowed_radius}")
                except EmployeeLocation.DoesNotExist:
                    print(f"Selected location ID {location_id} not found")
                    pass  # Will continue to check all locations
            else:
                print(f"Invalid location ID format: {location_id}")
        
        # If no location is verified yet, check all allowed locations for this employee
        if not is_location_verified:
            print("No location verified yet, checking all allowed locations")
            
            # Check all allowed locations for this specific employee
            allowed_locations = EmployeeLocation.objects.filter(
                employee=employee,
                is_active=True
            )
            
            # Find the nearest location and check if within radius
            for location in allowed_locations:
                distance = calculate_distance(
                    latitude, longitude,
                    location.latitude, location.longitude
                )
                
                print(f"Checking location: {location.location_name}, distance: {distance}, allowed radius: {location.allowed_radius}")
                
                # Update minimum distance if this is closer
                if distance < min_distance:
                    min_distance = distance
                    
                    # Check if within allowed radius
                    if distance <= location.allowed_radius:
                        is_location_verified = True
                        verified_location_name = location.location_name
                        location_distance = distance
                        print(f"Found valid location: {location.location_name}, distance: {distance}")
                        break  # Found a valid location, no need to check others
        
        # Print debug info for location verification
        print(f"Verified location: {verified_location_name}, Distance: {location_distance if location_distance else min_distance}")
        
        # Face verification result from compare-faces endpoint
        # In a production app, we would call the compare-faces function here
        is_face_verified = True  # Placeholder for actual face verification
        
        # Get today's date and time - ensure it's timezone-aware
        now = timezone.localtime()  # Convert to the current timezone
        today = now.date()
        current_time = now.time()
        
        # AUTOMATIC SHIFT ASSIGNMENT
        # Determine which shift the employee should be assigned to based on current time
        assigned_shift = None
        shift_status = 'present'  # Default status
        minutes_late = None  # Initialize minutes_late
        
        # Get all shifts assigned to the employee for today's weekday
        weekday = now.weekday()  # 0 for Monday, 6 for Sunday
        
        # Query to get all shifts assigned to the employee for today using UserShift model
        user_shifts = UserShift.objects.filter(
            user=request.user,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today
        ).select_related('shift')
        
        # Filter shifts by current weekday
        applicable_shifts = []
        for user_shift in user_shifts:
            if weekday in user_shift.shift.get_weekdays():
                applicable_shifts.append(user_shift.shift)
        
        if applicable_shifts:
            # Try to find the shift that the employee is currently in
            current_shifts = []
            for shift in applicable_shifts:
                shift_start = shift.start_time
                shift_end = shift.end_time
                
                # Handle overnight shifts (where end_time is less than start_time)
                if shift_end < shift_start:
                    # For overnight shift, employee is in shift if:
                    # 1. Current time is after shift start (same day)
                    # 2. Current time is before shift end (next day)
                    if current_time >= shift_start or current_time <= shift_end:
                        current_shifts.append(shift)
                elif shift_start <= current_time <= shift_end:
                    # Current time falls within this shift's hours
                    current_shifts.append(shift)
            
            # If employee is currently in a shift
            if current_shifts:
                # If multiple shifts overlap, take the one with earliest start time
                assigned_shift = min(current_shifts, key=lambda s: s.start_time)
                
                # Check if employee is late
                # Get grace period from shift or use default
                grace_period_minutes = getattr(assigned_shift, 'grace_period_minutes', 15)
                
                # Create a timezone-aware datetime for shift start and grace time
                # Combine today's date with shift start time and make it timezone-aware
                shift_start_datetime = timezone.make_aware(
                    datetime.combine(today, assigned_shift.start_time)
                )
                grace_time = shift_start_datetime + timedelta(minutes=grace_period_minutes)
                
                # If current time is after grace period, mark as late
                if now > grace_time:
                    shift_status = 'late'
                    # Calculate how many minutes late
                    minutes_late = (now - shift_start_datetime).total_seconds() / 60
                    print(f"Employee is {minutes_late:.1f} minutes late (grace period: {grace_period_minutes} minutes)")
            else:
                # Employee is not currently in any shift
                # Find the next upcoming shift today
                upcoming_shifts = [s for s in applicable_shifts if s.start_time > current_time]
                
                if upcoming_shifts:
                    # Get the shift with the nearest start time
                    assigned_shift = min(upcoming_shifts, key=lambda s: s.start_time)
                else:
                    # If no upcoming shifts today, find the most recent past shift
                    past_shifts = [s for s in applicable_shifts if s.start_time < current_time]
                                        
                    if past_shifts:
                        # Get the most recent past shift
                        assigned_shift = max(past_shifts, key=lambda s: s.start_time)
                        
                        # Check if employee already marked attendance for this shift today
                        existing_attendance = Attendance.objects.filter(
                            employee=employee,
                            date=today,
                            shift=assigned_shift
                        ).exists()
                        
                        if existing_attendance:
                            # Employee already worked this shift today, mark as overtime
                            shift_status = 'overtime'
                        else:
                            # Employee is logging in after shift ended without prior attendance
                            shift_status = 'late'
                            
                            # Calculate how many minutes late for messaging
                            shift_start_datetime = timezone.make_aware(
                                datetime.combine(today, assigned_shift.start_time)
                            )
                            minutes_late = (now - shift_start_datetime).total_seconds() / 60
                            print(f"Employee is late for shift that already ended: {assigned_shift.name}, {minutes_late:.1f} minutes late")
        
        # Find if there's an open attendance record (no check-out)
        open_attendance = Attendance.objects.filter(
            employee=employee,
            date=today,
            check_out_time__isnull=True
        ).first()
        
        # AUTOMATIC BEHAVIOR: 
        # - If there's an open record and not forcing new record, MARK CHECKOUT
        # - Else, create a new check-in record
        
        if open_attendance and not force_new_record:
            print(f"User has an open attendance record (ID: {open_attendance.id}) - MARKING CHECKOUT")

            # Update the existing record
            attendance = open_attendance

            # Mark the checkout time and location
            attendance.check_out_time = now
            attendance.check_out_latitude = latitude
            attendance.check_out_longitude = longitude
            
            # Other updates that might be needed
            if is_location_verified and verified_location_name and (attendance.location_name != verified_location_name):
                attendance.location_name = verified_location_name
                
            if attendance.is_location_verified != is_location_verified:
                attendance.is_location_verified = is_location_verified
                
            if attendance.is_face_verified != is_face_verified:
                attendance.is_face_verified = is_face_verified
                
            if attendance.is_blink_verified != blink_detected:
                attendance.is_blink_verified = blink_detected

            # Save all changes
            attendance.save()
            print(f"Marked checkout time for attendance record (ID: {attendance.id})")

            # Create an attendance log for this update
            checkout_log_message = "Attendance check-out recorded"
            if verified_location_name:
                checkout_log_message += f" at {verified_location_name}"

            # Create a log entry for this update
            AttendanceLog.objects.create(
                attendance=attendance,
                employee=employee,
                company=employee.company,
                timestamp=now,
                latitude=latitude,
                longitude=longitude,
                face_verification_result=is_face_verified,
                location_verification_result=is_location_verified,
                blink_verification_result=blink_detected,
                device_info=device_info,
                log_message=checkout_log_message
            )

            # Calculate work duration
            work_duration = None
            if attendance.check_in_time:
                duration = now - attendance.check_in_time
                work_duration = int(duration.total_seconds() / 60)  # Duration in minutes

            # Prepare shift info for response
            shift_info = {
                'shift_id': assigned_shift.id if assigned_shift else None,
                'shift_name': assigned_shift.name if assigned_shift else "No Shift",
                'shift_time': f"{assigned_shift.start_time.strftime('%H:%M')} - {assigned_shift.end_time.strftime('%H:%M')}" if assigned_shift else "N/A",
                'status': attendance.status
            }

            # For the distance in the response, use the verified location's distance
            # or the minimum distance if not verified
            response_distance = location_distance if location_distance is not None else min_distance

            # Prepare response message for checkout
            message = f"✅ Check-out successful! Your attendance has been recorded for {work_duration} minutes."
            if verified_location_name:
                message += f" Location verified at {verified_location_name}."

            # Return checkout response
            return JsonResponse({
                'success': True,
                'message': message,
                'data': {
                    'attendance_id': attendance.id,
                    'is_check_in': False,
                    'is_update': True,
                    'timestamp': now.isoformat(),
                    'check_in_time': attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                    'check_out_time': attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                    'is_face_verified': is_face_verified,
                    'is_blink_verified': blink_detected,
                    'is_location_verified': is_location_verified,
                    'location_distance': response_distance,
                    'location_name': verified_location_name or "Unknown",
                    'previous_attendance_closed': False,
                    'shift': shift_info,
                    'status': attendance.status,
                    'already_checked_in': False,
                    'late': attendance.status == 'late',
                    'minutes_late': int(minutes_late) if minutes_late else None,
                    'is_checked_out': True,
                    'attendance_status': 'checked_out',
                    'work_duration': work_duration
                }
            })
        
        else:
            # Either no open attendance record, or user is forcing a new record
            
            # If forcing a new record and there's an open record, close it
            if open_attendance and force_new_record:
                print(f"Closing existing attendance record (ID: {open_attendance.id}) because user is forcing a new record")
                
                # Close the previous open attendance
                open_attendance.check_out_time = now
                open_attendance.check_out_latitude = latitude
                open_attendance.check_out_longitude = longitude
                open_attendance.save()
                
                # Log this checkout
                checkout_log_message = "Automatic check-out before new forced attendance"
                if verified_location_name:
                    checkout_log_message += f" at {verified_location_name}"
                
                # Create checkout log
                AttendanceLog.objects.create(
                    attendance=open_attendance,
                    employee=employee,
                    company=employee.company,
                    timestamp=now,
                    latitude=latitude,
                    longitude=longitude,
                    face_verification_result=is_face_verified,
                    location_verification_result=is_location_verified,
                    blink_verification_result=blink_detected,
                    device_info=device_info,
                    log_message=checkout_log_message
                )
            
            # Create a new attendance record with the assigned shift
            attendance = Attendance.objects.create(
                employee=employee,
                company=employee.company,
                shift=assigned_shift,  # Assign the automatically determined shift
                date=today,
                check_in_time=now,
                check_in_latitude=latitude,
                check_in_longitude=longitude,
                status=shift_status,  # Use the determined status (present or late)
                is_location_verified=is_location_verified,
                is_face_verified=is_face_verified,
                is_blink_verified=blink_detected,
                device_info=device_info,
                face_image=current_face_image,
                location_name=verified_location_name if is_location_verified else None
            )
            
            # Create attendance log
            checkin_log_message = "New attendance check-in recorded"
            if verified_location_name:
                checkin_log_message += f" at {verified_location_name}"
            
            if assigned_shift:
                checkin_log_message += f" for shift: {assigned_shift.name}"
            
            # Add info about forced check-in if applicable
            if open_attendance and force_new_record:
                checkin_log_message += " (forced new check-in)"
            
            # Create check-in log
            AttendanceLog.objects.create(
                attendance=attendance,
                employee=employee,
                company=employee.company,
                timestamp=now,
                latitude=latitude,
                longitude=longitude,
                face_verification_result=is_face_verified,
                location_verification_result=is_location_verified,
                blink_verification_result=blink_detected,
                device_info=device_info,
                log_message=checkin_log_message
            )
            
            # Prepare the response message with better formatting for frontend
            if open_attendance and force_new_record:
                message = '✅ Previous session closed and new attendance recorded!'
            elif shift_status == 'late':
                message = '⚠️ Late Attendance Recorded! You are late for your shift.'
                if assigned_shift and minutes_late:
                    message += f" You are {int(minutes_late)} minutes late for shift: {assigned_shift.name}."
            else:
                message = '✅ Attendance recorded successfully!'
                
                # Add shift information to the message if a shift was assigned
                if assigned_shift:
                    message += f" You're marked present for shift: {assigned_shift.name}."
            
            # For the distance in the response, use the verified location's distance
            # or the minimum distance if not verified
            response_distance = location_distance if location_distance is not None else min_distance
            
            # Prepare shift info for response
            shift_info = None
            if assigned_shift:
                shift_info = {
                    'shift_id': assigned_shift.id,
                    'shift_name': assigned_shift.name,
                    'shift_time': f"{assigned_shift.start_time.strftime('%H:%M')} - {assigned_shift.end_time.strftime('%H:%M')}",
                    'status': shift_status
                }
            
            # Return response for a new attendance record
            return JsonResponse({
                'success': True,
                'message': message,
                'data': {
                    'attendance_id': attendance.id,
                    'is_check_in': True,
                    'is_update': False,            
                    'timestamp': now.isoformat(),
                    'check_in_time': attendance.check_in_time.isoformat() if attendance.check_in_time else now.isoformat(),
                    'check_out_time': None,
                    'is_face_verified': is_face_verified,
                    'is_blink_verified': blink_detected,
                    'is_location_verified': is_location_verified,
                    'location_distance': response_distance,
                    'location_name': verified_location_name or "Unknown",
                    'previous_attendance_closed': open_attendance and force_new_record,  
                    'shift': shift_info,
                    'status': attendance.status,
                    'already_checked_in': False,    
                    'late': attendance.status == 'late',
                    'minutes_late': int(minutes_late) if minutes_late else None,
                    'is_checked_out': False,
                    'attendance_status': 'checked_in'
                }
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@permission_classes([IsAuthenticated])
def last_attendance(request):
    """Get employee's last attendance record - updated for multiple entries per day"""
    try:
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        
        # Get today's date
        today = timezone.now().date()
        
        # Get all attendance records for today, ordered by check-in time (newest first)
        today_records = Attendance.objects.filter(
            employee=employee,
            date=today
        ).order_by('-check_in_time')
        
        # Count how many records exist today
        today_count = today_records.count()
        
        if today_count > 0:
            # Get the latest attendance record
            latest_attendance = today_records.first()
            
            # Check if there are any open attendance records (no check-out)
            has_open_record = Attendance.objects.filter(
                employee=employee,
                date=today,
                check_out_time__isnull=True
            ).exists()
            
            return JsonResponse({
                'success': True,
                'has_attendance': True,
                'data': {
                    'id': latest_attendance.id,
                    'date': latest_attendance.date.isoformat(),
                    'status': latest_attendance.status,
                    'check_in_time': latest_attendance.check_in_time.isoformat() if latest_attendance.check_in_time else None,
                    'check_out_time': latest_attendance.check_out_time.isoformat() if latest_attendance.check_out_time else None,
                    'is_checked_out': latest_attendance.check_out_time is not None,
                    'attendance_count_today': today_count,
                    'has_open_attendance': has_open_record
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'has_attendance': False,
                'attendance_count_today': 0
            })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@permission_classes([IsAuthenticated])
def attendance_history(request):
    """Get employee attendance history with shift support"""
    try:
        # Get query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        employee_id = request.GET.get('employee_id')  # Filter by employee ID
        shift_id = request.GET.get('shift_id')  # Filter by shift ID
        
        # Initialize query
        records = Attendance.objects.all().order_by('-date', '-check_in_time')
        
        # Filter by employee
        if employee_id:
            # If employee_id is provided, filter by that employee
            records = records.filter(employee__user_id=employee_id)
        else:
            # Otherwise, default to the authenticated user's records
            employee = get_object_or_404(EmployeeProfile, user=request.user)
            records = records.filter(employee=employee)
        
        # Filter by shift if provided
        if shift_id:
            records = records.filter(shift_id=shift_id)
        
        # Filter by date range if provided
        if start_date:
            records = records.filter(date__gte=start_date)
        
        if end_date:
            records = records.filter(date__lte=end_date)
        
        # Limit to last 30 days if no dates provided
        if not start_date and not end_date:
            from datetime import timedelta
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            records = records.filter(date__gte=thirty_days_ago)
        
        # Prepare data for response
        attendance_data = []
        for record in records:
            # Calculate duration if both check_in and check_out are available
            duration_minutes = None
            if record.check_in_time and record.check_out_time:
                duration = record.check_out_time - record.check_in_time
                duration_minutes = int(duration.total_seconds() / 60)
            
            # Get employee info for better display
            employee_info = {
                'id': record.employee.id,
                'user_id': record.employee.user.id,
                'username': record.employee.user.username,
                'full_name': getattr(record.employee, 'full_name', record.employee.user.username)
            }
            
            # Get shift info if available
            shift_info = None
            if record.shift:
                shift_info = {
                    'id': record.shift.id,
                    'name': record.shift.name,
                    'start_time': record.shift.start_time,
                    'end_time': record.shift.end_time
                }
            
            attendance_data.append({
                'id': record.id,
                'employee': employee_info,
                'date': record.date.isoformat(),
                'status': record.status,
                'check_in_time': record.check_in_time.isoformat() if record.check_in_time else None,
                'check_out_time': record.check_out_time.isoformat() if record.check_out_time else None,
                'is_location_verified': record.is_location_verified,
                'is_face_verified': record.is_face_verified,
                'duration_minutes': duration_minutes,
                'location_name': getattr(record, 'location_name', None),
                'shift': shift_info
            })
        
        # Group records by employee and date for easy access
        grouped_data = {}
        for record in attendance_data:
            employee_id = record['employee']['user_id']
            date = record['date']
            
            # Create nested structure if not exists
            if employee_id not in grouped_data:
                grouped_data[employee_id] = {}
            
            if date not in grouped_data[employee_id]:
                grouped_data[employee_id][date] = {
                    'date': date,
                    'employee': record['employee'],
                    'records': [],
                    'total_duration_minutes': 0,
                    'record_count': 0,
                    'latest_record': None
                }
            
            # Add record to the group
            grouped_data[employee_id][date]['records'].append(record)
            grouped_data[employee_id][date]['record_count'] += 1
            
            # Update total duration
            if record['duration_minutes']:
                grouped_data[employee_id][date]['total_duration_minutes'] += record['duration_minutes']
            
            # Update latest record
            if not grouped_data[employee_id][date]['latest_record'] or (
                record['check_in_time'] and (
                    not grouped_data[employee_id][date]['latest_record']['check_in_time'] or
                    record['check_in_time'] > grouped_data[employee_id][date]['latest_record']['check_in_time']
                )
            ):
                grouped_data[employee_id][date]['latest_record'] = record
        
        # Flatten the grouped data for response
        employee_date_summary = []
        for employee_data in grouped_data.values():
            for date_data in employee_data.values():
                employee_date_summary.append(date_data)
        
        return JsonResponse({
            'success': True,
            'count': len(attendance_data),
            'data': attendance_data,
            'employee_date_summary': employee_date_summary
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def compare_faces(request):
    """Compare captured face with registered face"""
    try:
        # Parse JSON data from request
        data = json.loads(request.body)
        captured_image_data = data.get('captured_image')
        
        if not captured_image_data:
            return JsonResponse({'success': False, 'message': 'Captured image is required'}, status=400)
        
        # Get employee profile
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        
        # Get employee's registered face data
        try:
            face_data = EmployeeFaceData.objects.get(employee=employee)
        except EmployeeFaceData.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Face data not registered. Please register your face first.'
            }, status=400)
        
        # Process captured image
        captured_image_file = base64_to_image(captured_image_data)
        if not captured_image_file:
            return JsonResponse({'success': False, 'message': 'Invalid image data'}, status=400)
        
        # Save image temporarily
        fs = FileSystemStorage()
        image_name = f"compare_{employee.id}_{uuid.uuid4()}.png"
        image_path = fs.save(image_name, captured_image_file)
        full_image_path = os.path.join(settings.MEDIA_ROOT, image_path)
        
        # Get face encoding from captured image
        try:
            import face_recognition
            import numpy as np
            
            # Load the image file
            image = face_recognition.load_image_file(full_image_path)
            
            # Get face locations
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                # Clean up the image file
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                return JsonResponse({
                    'success': False, 
                    'message': 'No face detected in the image. Please try again with a clearer image.'
                }, status=400)
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                # Clean up the image file
                if os.path.exists(full_image_path):
                    os.remove(full_image_path)
                return JsonResponse({
                    'success': False, 
                    'message': 'Could not encode face features. Please try again.'
                }, status=400)
            
            # Get registered face encoding
            registered_encoding = json.loads(face_data.face_encoding)
            registered_encoding_array = np.array(registered_encoding)
            
            # Compare faces with a stricter tolerance (default is 0.6)
            tolerance = 0.4  # Lower means stricter matching
            matches = face_recognition.compare_faces([registered_encoding_array], face_encodings[0], tolerance=tolerance)
            face_distances = face_recognition.face_distance([registered_encoding_array], face_encodings[0])
            
            # Clean up the image file
            if os.path.exists(full_image_path):
                os.remove(full_image_path)
            
            # Calculate confidence (higher is better)
            match_confidence = 1.0 - face_distances[0]
            
            # Set a confidence threshold (e.g., 0.6 means 60% confident it's the same person)
            confidence_threshold = 0.6
            is_match = matches[0] and match_confidence >= confidence_threshold
            
            return JsonResponse({
                'success': True,
                'is_match': bool(is_match),
                'confidence': float(match_confidence),
                'message': 'Face comparison completed successfully.',
                'debug_info': {
                    'tolerance_used': tolerance,
                    'initial_match': bool(matches[0]),
                    'confidence_threshold': confidence_threshold
                }
            })
            
        except Exception as e:
            # Clean up the image file if it exists
            if 'full_image_path' in locals() and os.path.exists(full_image_path):
                os.remove(full_image_path)
            print(f"Error in face comparison: {str(e)}")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"Error in compare_faces: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json

from .models import EmployeeProfile, EmployeeLocation

# Helper function to convert a location object to dictionary
def location_to_dict(location, include_employee=False):
    location_dict = {
        'id': location.id,
        'location_name': location.location_name,
        'latitude': location.latitude,
        'longitude': location.longitude,
        'allowed_radius': location.allowed_radius,
        'is_active': location.is_active,
        'created_at': location.created_at.isoformat(),
        'updated_at': location.updated_at.isoformat(),
    }
    
    if location.created_by:
        location_dict['created_by_name'] = location.created_by.get_full_name() or location.created_by.username
    
    if include_employee:
        employee = location.employee
        location_dict['employee'] = {
            'id': employee.id,
            'full_name': employee.full_name,  # Changed from get_full_name()
            'email': employee.user.email if hasattr(employee, 'user') else None,
            'employee_id': getattr(employee, 'employee_id', None),
            'designation': getattr(employee, 'designation', None),
            'department': getattr(employee, 'department', None)
        }
    
    return location_dict

# Helper function to convert employee object to dictionary
def employee_to_dict(employee, include_locations=True):
    employee_dict = {
        'id': employee.id,
        'full_name': employee.full_name,  # Changed from get_full_name()
        'email': employee.user.email if hasattr(employee, 'user') else None,
        'employee_id': getattr(employee, 'employee_id', None),
        'designation': getattr(employee, 'designation', None),
        'department': getattr(employee, 'department', None)
    }
    
    if include_locations:
        employee_dict['locations'] = [
            location_to_dict(location) 
            for location in employee.allowed_locations.all()
        ]
    
    return employee_dict

# Function-based view: List/create employee locations (simplified for testing)
@csrf_exempt
@require_http_methods(["GET", "POST"])
def manage_employee_locations(request):
    # GET request - list ALL employees with locations
    if request.method == "GET":
        # Get all employees without department filter
        employees = EmployeeProfile.objects.all().prefetch_related('allowed_locations')
        
        # Convert employees to dictionaries with their locations
        employees_data = [employee_to_dict(employee) for employee in employees]
        
        return JsonResponse(employees_data, safe=False)
    
    # POST request - add new location
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            employee_id = data.get('employee_id')
            
            # Check if employee exists without department check
            try:
                employee = EmployeeProfile.objects.get(id=employee_id)
            except EmployeeProfile.DoesNotExist:
                return JsonResponse({
                    "error": "Employee not found"
                }, status=404)
            
            # Validate required fields
            required_fields = ['location_name', 'latitude', 'longitude']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        "error": f"Missing required field: {field}"
                    }, status=400)
            
            # Create new location
            location = EmployeeLocation.objects.create(
                employee=employee,
                location_name=data['location_name'],
                latitude=float(data['latitude']),
                longitude=float(data['longitude']),
                allowed_radius=int(data.get('allowed_radius', 100)),
                is_active=bool(data.get('is_active', True)),
                created_by=request.user if request.user.is_authenticated else None
            )
            
            return JsonResponse({
                "success": True,
                "message": f"Location '{location.location_name}' added successfully",
                "location": location_to_dict(location)
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "error": f"Failed to add location: {str(e)}"
            }, status=500)

# Function-based view: Retrieve/update/delete specific location (simplified)
@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def manage_employee_location_detail(request, location_id):
    # Get location without permission check
    try:
        location = get_object_or_404(EmployeeLocation, id=location_id)
    except:
        return JsonResponse({
            "error": "Location not found"
        }, status=404)
    
    # GET request - get location details
    if request.method == "GET":
        return JsonResponse(location_to_dict(location, include_employee=True))
    
    # PUT request - update location
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            
            # Update fields if provided
            if 'location_name' in data:
                location.location_name = data['location_name']
            
            if 'latitude' in data:
                location.latitude = float(data['latitude'])
            
            if 'longitude' in data:
                location.longitude = float(data['longitude'])
            
            if 'allowed_radius' in data:
                location.allowed_radius = int(data['allowed_radius'])
            
            if 'is_active' in data:
                location.is_active = bool(data['is_active'])
            
            # Save changes
            location.save()
            
            return JsonResponse({
                "success": True,
                "message": f"Location '{location.location_name}' updated successfully",
                "location": location_to_dict(location)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                "error": "Invalid JSON in request body"
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "error": f"Failed to update location: {str(e)}"
            }, status=500)
    
    # DELETE request - delete location
    elif request.method == "DELETE":
        location_name = location.location_name
        location.delete()
        
        return JsonResponse({
            "success": True,
            "message": f"Location '{location_name}' deleted successfully"
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_allowed_locations(request):
    """Get all allowed locations for the employee, including both EmployeeLocation and default location"""
    try:
        # Get employee profile
        employee = get_object_or_404(EmployeeProfile, user=request.user)
        
        # Initialize locations list
        locations_data = []
        
        # Get locations from EmployeeLocation model
        try:
            location_objects = EmployeeLocation.objects.filter(
                employee=employee,
                is_active=True
            )
            
            # Convert each location to dictionary and add to list
            for location in location_objects:
                locations_data.append({
                    'id': location.id,
                    'location_name': location.location_name,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'allowed_radius': location.allowed_radius,
                    'is_active': True,
                    'created_at': location.created_at.isoformat(),
                    'updated_at': location.updated_at.isoformat(),
                })
        except Exception as loc_error:
            # Log the error but continue to get default location
            print(f"Error fetching employee locations: {str(loc_error)}")
        
        # Get default location from face registration
        try:
            face_data = EmployeeFaceData.objects.get(employee=employee)
            
            # Check if default location data exists
            if face_data.default_latitude and face_data.default_longitude:
                # Add default location from face registration
                default_location = {
                    'id': 'default',  # Special ID to indicate it's the default
                    'location_name': 'Default Location (Face Registration)',
                    'latitude': face_data.default_latitude,
                    'longitude': face_data.default_longitude,
                    'allowed_radius': face_data.allowed_radius or 100,  # Use 100m as fallback
                    'is_active': True,
                    'created_at': face_data.created_at.isoformat(),
                    'updated_at': face_data.updated_at.isoformat(),
                }
                
                # Add default location to the beginning of the list
                locations_data.insert(0, default_location)
        except EmployeeFaceData.DoesNotExist:
            # No face data registered, continue without default location
            pass
        except Exception as face_error:
            # Log the error but continue
            print(f"Error fetching face data location: {str(face_error)}")
        
        return JsonResponse({
            "success": True,
            "allowed_locations": locations_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "success": False,
            "error": f"Failed to get allowed locations: {str(e)}"
        }, status=500)


        
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
import base64
from django.core.files.base import ContentFile
from employees.models import EmployeeProfile, EmployeeScreenshot

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_screenshot(request):
    """API endpoint for PC app to upload screenshots"""
    user = request.user
    
    try:
        # Get the employee profile
        employee = EmployeeProfile.objects.get(user=user)
        
        # Get the base64 screenshot data from request
        screenshot_data = request.data.get('screenshot')
        if not screenshot_data:
            return JsonResponse({'status': 'error', 'message': 'No screenshot data provided'}, status=400)
        
        # Convert base64 to image file
        try:
            # Remove the data:image/png;base64, prefix from base64 if present
            if ';base64,' in screenshot_data:
                format, imgstr = screenshot_data.split(';base64,')
                ext = format.split('/')[-1]
                screenshot_file = ContentFile(
                    base64.b64decode(imgstr), 
                    name=f'screenshot_{user.username}_{timezone.now().strftime("%Y%m%d%H%M%S")}.{ext}'
                )
            else:
                # Handle just base64 string without prefix
                screenshot_file = ContentFile(
                    base64.b64decode(screenshot_data), 
                    name=f'screenshot_{user.username}_{timezone.now().strftime("%Y%m%d%H%M%S")}.png'
                )
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error decoding screenshot: {str(e)}'}, status=400)
        
        # Create and save the screenshot
        screenshot = EmployeeScreenshot.objects.create(
            employee=employee,
            company=user.company,
            screenshot=screenshot_file,
            is_active=request.data.get('is_active', True),
            device_info=request.data.get('device_info', {})
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Screenshot uploaded successfully',
            'screenshot_id': screenshot.id,
            'timestamp': timezone.now().isoformat()
        })
    
    except EmployeeProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Employee profile not found'}, status=404)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_screenshots(request, employee_id=None):
    """API endpoint to retrieve screenshots for an employee"""
    user = request.user
    
    try:
        # If employee_id is provided and user has permission, get that employee's screenshots
        if employee_id and user.access_level in ['company', 'admin', 'manager']:
            try:
                employee = EmployeeProfile.objects.get(id=employee_id, company=user.company)
            except EmployeeProfile.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Employee not found'}, status=404)
        else:
            # Otherwise, get the logged-in user's screenshots
            employee = EmployeeProfile.objects.get(user=user)
        
        # Get date parameters or default to today
        date_str = request.GET.get('date')
        if date_str:
            try:
                date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        else:
            date = timezone.now().date()
        
        # Query screenshots for the specified date
        start_time = timezone.datetime.combine(date, timezone.datetime.min.time())
        end_time = timezone.datetime.combine(date, timezone.datetime.max.time())
        
        screenshots = EmployeeScreenshot.objects.filter(
            employee=employee,
            timestamp__range=(start_time, end_time)
        ).order_by('timestamp')
        
        # Format response data
        result = {
            'status': 'success',
            'employee': {
                'id': employee.id,
                'name': employee.full_name,
                'department': employee.department
            },
            'date': date.strftime('%Y-%m-%d'),
            'screenshots': [
                {
                    'id': ss.id,
                    'timestamp': ss.timestamp.isoformat(),
                    'url': ss.screenshot.url if ss.screenshot else None,
                    'is_active': ss.is_active
                }
                for ss in screenshots
            ],
            'total': screenshots.count()
        }
        
        return JsonResponse(result)
    
    except EmployeeProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Employee profile not found'}, status=404)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



# shift management views

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
import json
import datetime

from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Shift, ShiftAssignment, UserShift
from .utils import create_user_shifts_for_assignment, rotate_shift_assignment
from employees.models import Department
from companies.models import Company, Team, TeamMember
from users.models import User

# Shift API Endpoints
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def shift_list(request):
    """API endpoint to list all shifts for the company"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    shifts = Shift.objects.filter(company=company).order_by('name')
    shifts_data = [{
        'id': shift.id,
        'name': shift.name,
        'start_time': shift.start_time.strftime('%H:%M'),
        'end_time': shift.end_time.strftime('%H:%M'),
        'monday': shift.monday,
        'tuesday': shift.tuesday,
        'wednesday': shift.wednesday,
        'thursday': shift.thursday,
        'friday': shift.friday,
        'saturday': shift.saturday,
        'sunday': shift.sunday,
        'days': shift.get_active_days()
    } for shift in shifts]
    
    return Response(shifts_data, status=status.HTTP_200_OK)


from datetime import datetime
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import UserShift  # Make sure this import is correct

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def filtered_shift_assignments(request):
    """
    API endpoint to get shift assignments filtered by date and type,
    considering rotation patterns and active days.
    
    Query parameters:
    - date: Filter shifts active on this date (YYYY-MM-DD)
    - type: Optional filter by assignment type (department, team, individual)
    - department_id: Optional filter by specific department
    - team_id: Optional filter by specific team
    - user_id: Optional filter by specific user
    """
    # Get the authenticated user's company
    company = request.user.company
    if not company:
        return Response({"error": "You are not associated with any company."}, 
                        status=status.HTTP_400_BAD_REQUEST)

    # Get date parameter
    date_param = request.query_params.get('date', None)
    if not date_param:
        return Response({"error": "Date parameter is required (format: YYYY-MM-DD)."},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        # Parse the date string to a date object
        filter_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        
        # Get day of week (e.g., 'monday')
        day_of_week = filter_date.strftime('%A').lower()
        
        # Build the base query
        filter_kwargs = {
            f'shift__{day_of_week}': True
        }

        assignments = ShiftAssignment.objects.filter(
        company=company,
        start_date__lte=filter_date,
        **filter_kwargs
        ).filter(
            Q(end_date__gte=filter_date) | Q(end_date__isnull=True)
        ).select_related('shift', 'department', 'team', 'user')

        
        # Apply optional filters
        assignment_type = request.query_params.get('type', None)
        if assignment_type:
            if assignment_type not in [choice[0] for choice in ShiftAssignment.ASSIGNMENT_TYPE_CHOICES]:
                return Response({"error": f"Invalid assignment type. Choose from: {', '.join([choice[0] for choice in ShiftAssignment.ASSIGNMENT_TYPE_CHOICES])}"}, 
                              status=status.HTTP_400_BAD_REQUEST)
            assignments = assignments.filter(assignment_type=assignment_type)
            
        department_id = request.query_params.get('department_id', None)
        if department_id:
            assignments = assignments.filter(department_id=department_id)
            
        team_id = request.query_params.get('team_id', None)
        if team_id:
            assignments = assignments.filter(team_id=team_id)
            
        user_id = request.query_params.get('user_id', None)
        if user_id:
            assignments = assignments.filter(user_id=user_id)
        
        # Calculate current shift status
        now = datetime.now().time()
        
        # Format the response data
        result = []
        for assignment in assignments:
            shift = assignment.shift
            
            # Calculate if shift is currently active
            start_time = shift.start_time
            end_time = shift.end_time
            
            # Handle overnight shifts
            if end_time < start_time:
                is_active_now = now >= start_time or now <= end_time
            else:
                is_active_now = start_time <= now <= end_time
                
            # Check if rotation is needed but hasn't been applied
            requires_rotation = False
            if assignment.auto_rotate and assignment.last_rotation_date:
                days_since_rotation = (datetime.now().date() - assignment.last_rotation_date).days
                requires_rotation = days_since_rotation >= assignment.rotation_days
            
            # Build assignment target info
            assignment_target = None
            if assignment.assignment_type == 'department' and assignment.department:
                assignment_target = {
                    'id': assignment.department.id,
                    'name': assignment.department.name,
                    'type': 'department'
                }
            elif assignment.assignment_type == 'team' and assignment.team:
                assignment_target = {
                    'id': assignment.team.id,
                    'name': assignment.team.name,
                    'type': 'team'
                }
            elif assignment.assignment_type == 'individual' and assignment.user:
                assignment_target = {
                    'id': assignment.user.id,
                    'username': assignment.user.username,
                    'first_name': assignment.user.first_name,
                    'last_name': assignment.user.last_name,
                    'email': assignment.user.email,
                    'type': 'individual'
                }
                
            result.append({
                'id': assignment.id,
                'shift': {
                    'id': shift.id,
                    'name': shift.name,
                    'start_time': shift.start_time.strftime('%H:%M'),
                    'end_time': shift.end_time.strftime('%H:%M'),
                    'monday': shift.monday,
                    'tuesday': shift.tuesday,
                    'wednesday': shift.wednesday,
                    'thursday': shift.thursday,
                    'friday': shift.friday,
                    'saturday': shift.saturday,
                    'sunday': shift.sunday,
                },
                'assignment_type': assignment.assignment_type,
                'assignment_target': assignment_target,
                'start_date': assignment.start_date.isoformat(),
                'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
                'auto_rotate': assignment.auto_rotate,
                'rotation_days': assignment.rotation_days,
                'last_rotation_date': assignment.last_rotation_date.isoformat() if assignment.last_rotation_date else None,
                'requires_rotation': requires_rotation,
                'is_currently_active': is_active_now,
                'day_of_week': day_of_week
            })

        return Response(result, status=status.HTTP_200_OK)

    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."},
                      status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
def shift_create(request):
    """API endpoint to create a new shift"""
    user = request.user
    company = getattr(user, 'company', None)

    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    data = request.data
    name = data.get('name')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not name or not start_time or not end_time:
        return Response({"error": "Please provide all required fields."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        shift = Shift.objects.create(
            name=name,
            company=company,
            start_time=start_time,
            end_time=end_time,
            monday=data.get('monday', False),
            tuesday=data.get('tuesday', False),
            wednesday=data.get('wednesday', False),
            thursday=data.get('thursday', False),
            friday=data.get('friday', False),
            saturday=data.get('saturday', False),
            sunday=data.get('sunday', False),
        )
        return Response({
            "id": shift.id,
            "message": f"Shift '{name}' created successfully."
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def shift_detail(request, shift_id):
    """API endpoint to get shift details"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        shift = get_object_or_404(Shift, id=shift_id, company=company)
        shift_data = {
            'id': shift.id,
            'name': shift.name,
            'start_time': shift.start_time.strftime('%H:%M'),
            'end_time': shift.end_time.strftime('%H:%M'),
            'monday': shift.monday,
            'tuesday': shift.tuesday,
            'wednesday': shift.wednesday,
            'thursday': shift.thursday,
            'friday': shift.friday,
            'saturday': shift.saturday,
            'sunday': shift.sunday,
            'days': shift.get_active_days()
        }
        return Response(shift_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthentication])
def shift_update(request, shift_id):
    """API endpoint to update a shift"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        shift = get_object_or_404(Shift, id=shift_id, company=company)
        data = request.data
        
        # Update shift fields
        if 'name' in data:
            shift.name = data['name']
        if 'start_time' in data:
            shift.start_time = data['start_time']
        if 'end_time' in data:
            shift.end_time = data['end_time']
        
        # Update days
        if 'monday' in data:
            shift.monday = data['monday']
        if 'tuesday' in data:
            shift.tuesday = data['tuesday']
        if 'wednesday' in data:
            shift.wednesday = data['wednesday']
        if 'thursday' in data:
            shift.thursday = data['thursday']
        if 'friday' in data:
            shift.friday = data['friday']
        if 'saturday' in data:
            shift.saturday = data['saturday']
        if 'sunday' in data:
            shift.sunday = data['sunday']
        
        shift.save()
        
        return Response({
            "id": shift.id,
            "message": f"Shift '{shift.name}' updated successfully."
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
def shift_delete(request, shift_id):
    """API endpoint to delete a shift"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        shift = get_object_or_404(Shift, id=shift_id, company=company)
        
        # Check if shift has active assignments
        if ShiftAssignment.objects.filter(shift=shift, end_date__gte=timezone.now().date()).exists():
            return Response({"error": "Cannot delete shift with active assignments."}, status=status.HTTP_400_BAD_REQUEST)
        
        shift_name = shift.name
        shift.delete()
        return Response({"message": f"Shift '{shift_name}' deleted successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Shift Assignment API Endpoints
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def shift_assignment_list(request):
    """API endpoint to list all shift assignments"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    assignments = ShiftAssignment.objects.filter(company=company).order_by('-created_at')
    
    # Apply filters if provided
    department_id = request.query_params.get('department')
    team_id = request.query_params.get('team')
    user_id = request.query_params.get('user')
    
    if department_id:
        assignments = assignments.filter(department_id=department_id)
    
    if team_id:
        assignments = assignments.filter(team_id=team_id)
    
    if user_id:
        assignments = assignments.filter(user_id=user_id)
    
    assignments_data = []
    for assignment in assignments:
        data = {
            'id': assignment.id,
            'shift': {
                'id': assignment.shift.id,
                'name': assignment.shift.name
            },
            'assignment_type': assignment.assignment_type,
            'start_date': assignment.start_date.isoformat(),
            'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
            'auto_rotate': assignment.auto_rotate,
            'rotation_days': assignment.rotation_days,
            'created_at': assignment.created_at.isoformat(),
            'updated_at': assignment.updated_at.isoformat() if assignment.updated_at else None
        }
        
        # Add target details based on assignment type
        if assignment.assignment_type == 'department' and assignment.department:
            data['department'] = {
                'id': assignment.department.id,
                'name': assignment.department.name
            }
        elif assignment.assignment_type == 'team' and assignment.team:
            data['team'] = {
                'id': assignment.team.id,
                'name': assignment.team.name
            }
        elif assignment.assignment_type == 'individual' and assignment.user:
            data['user'] = {
                'id': assignment.user.id,
                'username': assignment.user.username,
                'name': f"{assignment.user.first_name} {assignment.user.last_name}".strip() or assignment.user.username
            }
        
        assignments_data.append(data)
    
    return Response(assignments_data, status=status.HTTP_200_OK)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
def shift_assignment_create(request):
    """API endpoint to create a new shift assignment"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    data = request.data
    shift_id = data.get('shift_id')
    assignment_type = data.get('assignment_type')
    department_id = data.get('department_id')
    team_id = data.get('team_id')
    user_id = data.get('user_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    auto_rotate = data.get('auto_rotate', False)
    rotation_days = data.get('rotation_days', 15)
    
    # Debug logging
    print("Received data:", data)
    print("start_date:", start_date, type(start_date))
    print("end_date:", end_date, type(end_date))
    
    # Validate input
    if not shift_id or not assignment_type or not start_date:
        return Response({"error": "Please provide all required fields."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate assignment target based on type
    if assignment_type == 'department' and not department_id:
        return Response({"error": "Please select a department."}, status=status.HTTP_400_BAD_REQUEST)
    elif assignment_type == 'team' and not team_id:
        return Response({"error": "Please select a team."}, status=status.HTTP_400_BAD_REQUEST)
    elif assignment_type == 'individual' and not user_id:
        return Response({"error": "Please select a user."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get related objects
    try:
        shift = get_object_or_404(Shift, id=shift_id, company=company)
        department = get_object_or_404(Department, id=department_id, company=company) if department_id else None
        team = get_object_or_404(Team, id=team_id, company=company) if team_id else None
        user = get_object_or_404(User, id=user_id, company=company) if user_id else None
    except Exception as e:
        return Response({"error": f"Invalid selection: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle date conversion if needed
    from django.utils.dateparse import parse_date
    
    try:
        # If start_date is a string, try to convert it to a date object
        if isinstance(start_date, str):
            start_date = parse_date(start_date)
        
        # If end_date is a string and not empty, try to convert it to a date object
        if end_date and isinstance(end_date, str):
            end_date = parse_date(end_date)
        elif not end_date:
            end_date = None
            
        # Create assignment
        assignment = ShiftAssignment.objects.create(
            shift=shift,
            company=company,
            assignment_type=assignment_type,
            department=department,
            team=team,
            user=user,
            start_date=start_date,
            end_date=end_date,
            auto_rotate=auto_rotate,
            rotation_days=rotation_days
        )
        
        # Create individual user shifts based on this assignment
        try:
            create_user_shifts_for_assignment(assignment)
        except ValidationError as e:
            # If user shift creation fails, provide a more specific error message
            # and roll back the assignment
            assignment.delete()
            return Response({"error": f"Error creating user shifts: {str(e)}"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            "id": assignment.id,
            "message": "Shift assignment created successfully."
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        # Print more detailed error for debugging
        import traceback
        print("Error creating assignment:", str(e))
        print(traceback.format_exc())
        return Response({"error": f"Error creating assignment: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def shift_assignment_detail(request, assignment_id):
    """API endpoint to get assignment details"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, company=company)
        
        data = {
            'id': assignment.id,
            'shift': {
                'id': assignment.shift.id,
                'name': assignment.shift.name
            },
            'assignment_type': assignment.assignment_type,
            'start_date': assignment.start_date.isoformat(),
            'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
            'auto_rotate': assignment.auto_rotate,
            'rotation_days': assignment.rotation_days,
            'created_at': assignment.created_at.isoformat(),
            'updated_at': assignment.updated_at.isoformat() if assignment.updated_at else None
        }
        
        # Add target details based on assignment type
        if assignment.assignment_type == 'department' and assignment.department:
            data['department'] = {
                'id': assignment.department.id,
                'name': assignment.department.name
            }
        elif assignment.assignment_type == 'team' and assignment.team:
            data['team'] = {
                'id': assignment.team.id,
                'name': assignment.team.name
            }
        elif assignment.assignment_type == 'individual' and assignment.user:
            data['user'] = {
                'id': assignment.user.id,
                'username': assignment.user.username,
                'name': f"{assignment.user.first_name} {assignment.user.last_name}".strip() or assignment.user.username
            }
        
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthentication])
def shift_assignment_update(request, assignment_id):
    """API endpoint to update a shift assignment"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, company=company)
        data = request.data
        
        # Update shift if provided
        if 'shift_id' in data:
            old_shift = assignment.shift
            new_shift = get_object_or_404(Shift, id=data['shift_id'], company=company)
            assignment.shift = new_shift
        
        # Update end date if provided
        if 'end_date' in data:
            assignment.end_date = data['end_date'] if data['end_date'] else None
        
        # Update rotation settings if provided
        if 'auto_rotate' in data:
            assignment.auto_rotate = data['auto_rotate']
        if 'rotation_days' in data:
            assignment.rotation_days = data['rotation_days']
        
        assignment.save()
        
        # If shift has changed, update user shifts
        if 'shift_id' in data and old_shift.id != assignment.shift.id:
            today = timezone.now().date()
            
            # Deactivate existing user shifts
            UserShift.objects.filter(
                assignment=assignment,
                is_active=True
            ).update(is_active=False, end_date=today)
            
            # Create new user shifts
            create_user_shifts_for_assignment(assignment)
        
        return Response({
            "id": assignment.id,
            "message": "Shift assignment updated successfully."
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f"Error updating assignment: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
def shift_assignment_delete(request, assignment_id):
    """API endpoint to delete a shift assignment"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, company=company)
        
        # Delete user shifts associated with this assignment
        today = timezone.now().date()
        UserShift.objects.filter(assignment=assignment, is_active=True).update(
            is_active=False,
            end_date=today
        )
        
        # Delete the assignment
        assignment.delete()
        return Response({"message": "Shift assignment deleted successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# User Shift API Endpoints

# views/shift_views.py
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.db.models import Q
from .models import UserShift, Shift  # adjust your import paths
from employees.models import EmployeeProfile  # if needed for extra user info

from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from .models import UserShift, Shift  # adjust import if needed

from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Shift, ShiftAssignment, EmployeeProfile

User = get_user_model()

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def users_by_shift(request, shift_id):
    """API to return all users assigned to a specific shift (ignore date validity)"""

    company = request.user.company
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)

    # Try to get the shift
    try:
        shift = Shift.objects.get(id=shift_id, company=company)
    except Shift.DoesNotExist:
        # Try to treat it as shift assignment ID and get the shift from it
        try:
            shift_assignment = ShiftAssignment.objects.get(id=shift_id, company=company)
            shift = shift_assignment.shift
        except ShiftAssignment.DoesNotExist:
            return Response({"error": "Shift or Shift Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

    # Get all assignments for this shift (NO DATE CHECK)
    shift_assignments = ShiftAssignment.objects.filter(shift=shift, company=company)

    data = []
    processed_users = set()

    for assignment in shift_assignments:
        users = []

        if assignment.assignment_type == 'individual' and assignment.user:
            users = [assignment.user]
        elif assignment.assignment_type == 'department' and assignment.department:
            users = User.objects.filter(department=assignment.department, company=company)
        elif assignment.assignment_type == 'team' and assignment.team:
            users = User.objects.filter(teams=assignment.team, company=company)

        for user in users:
            if user.id in processed_users:
                continue
            processed_users.add(user.id)

            department_name = getattr(user.department, 'name', None)
            position_name = getattr(user.position, 'name', None)

            try:
                profile = EmployeeProfile.objects.get(user=user)
                employee_profile = {
                    'full_name': profile.full_name,
                    'position': profile.position or position_name,
                }
                is_active = True
            except EmployeeProfile.DoesNotExist:
                employee_profile = None
                is_active = user.is_active

            data.append({
                'id': user.id,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'name': f"{user.first_name} {user.last_name}".strip(),
                    'employee_profile': employee_profile,
                    'department': department_name,
                    'position': position_name,
                    'app_running': user.is_monitoring_app_running(),
                },
                'is_active': is_active,
                'assignment_type': assignment.assignment_type  # Add assignment type
            })

    return Response(data, status=status.HTTP_200_OK)



@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def user_shift_list(request):
    """API endpoint to list all user shifts"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get filter parameters
    department_id = request.query_params.get('department')
    team_id = request.query_params.get('team')
    shift_id = request.query_params.get('shift')
    date_str = request.query_params.get('date')
    
    # Default to today if no date provided
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date = timezone.now().date()
    else:
        date = timezone.now().date()
    
    # Base query for active user shifts
    user_shifts = UserShift.objects.filter(
        Q(company=company) &
        Q(is_active=True) &
        Q(start_date__lte=date) &
        (Q(end_date__gte=date) | Q(end_date__isnull=True))
    ).select_related('user', 'shift')

    # Apply filters
    if department_id:
        user_shifts = user_shifts.filter(user__department_id=department_id)
    
    if team_id:
        team_member_user_ids = TeamMember.objects.filter(team_id=team_id).values_list('employee_id', flat=True)
        user_shifts = user_shifts.filter(user_id__in=team_member_user_ids)
    
    if shift_id:
        user_shifts = user_shifts.filter(shift_id=shift_id)
    
    # Format data for API response
    user_shifts_data = []
    for user_shift in user_shifts:
        data = {
            'id': user_shift.id,
            'user': {
                'id': user_shift.user.id,
                'username': user_shift.user.username,
                'name': f"{user_shift.user.first_name} {user_shift.user.last_name}".strip() or user_shift.user.username,
                'department': user_shift.user.department.name if user_shift.user.department else None,
                'position': user_shift.user.position.name if user_shift.user.position else None
            },
            'shift': {
                'id': user_shift.shift.id,
                'name': user_shift.shift.name,
                'start_time': user_shift.shift.start_time.strftime('%H:%M'),
                'end_time': user_shift.shift.end_time.strftime('%H:%M')
            },
            'start_date': user_shift.start_date.isoformat(),
            'end_date': user_shift.end_date.isoformat() if user_shift.end_date else None,
            'is_active': user_shift.is_active,
            'assignment_id': user_shift.assignment_id
        }
        user_shifts_data.append(data)
    
    return Response(user_shifts_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def current_user_shift(request):
    """API endpoint to get the current user's active shift"""
    user = request.user
    company = user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    today = timezone.now().date()
    
    # Get current user shift
    try:
        user_shift = UserShift.objects.filter(
            Q(user=user) &
            Q(company=company) &
            Q(is_active=True) &
            Q(start_date__lte=today) &
            (Q(end_date__gte=today) | Q(end_date__isnull=True))
        ).select_related('shift', 'user').first()
        
        if user_shift:
            # Include user information in the response
            shift_data = {
                'id': user_shift.shift.id,
                'name': user_shift.shift.name,
                'start_time': user_shift.shift.start_time.strftime('%H:%M'),
                'end_time': user_shift.shift.end_time.strftime('%H:%M'),
                'days': user_shift.shift.get_active_days(),
                'assignment_id': user_shift.assignment_id
            }
            # Add user data here
            user_data = {
                'id': user_shift.user.id,
                'username': user_shift.user.username,
                'name': f"{user_shift.user.first_name} {user_shift.user.last_name}".strip() or user_shift.user.username,
                'department': user_shift.user.department.name if hasattr(user_shift.user, 'department') and user_shift.user.department else None,
                'position': user_shift.user.position.name if hasattr(user_shift.user, 'position') and user_shift.user.position else None
            }
            return Response({'shift': shift_data, 'user': user_data}, status=status.HTTP_200_OK)
        else:
            return Response({'shift': None, 'user': None}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
def trigger_shift_rotation(request):
    """API endpoint to manually trigger shift rotation"""
    company = request.user.company
    
    if not company:
        return Response({"error": "You are not associated with any company."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get assignment ID from request
    data = request.data
    assignment_id = data.get('assignment_id')
    
    if not assignment_id:
        return Response({"error": "Assignment ID is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get assignment object
    try:
        assignment = get_object_or_404(ShiftAssignment, id=assignment_id, company=company)
    except:
        return Response({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger rotation
    try:
        rotate_shift_assignment(assignment)
        return Response({
            "success": True, 
            "message": "Shift rotation completed successfully"
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Additional utility endpoints for frontend
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def get_departments(request):
    """API endpoint to get all departments for the company"""
    company = request.user.company
    
    if not company:
        return Response({"error": "User not associated with any company"}, status=status.HTTP_400_BAD_REQUEST)
    
    departments = Department.objects.filter(company=company).order_by('name')
    departments_data = [{
        'id': dept.id,
        'name': dept.name
    } for dept in departments]
    
    return Response(departments_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def get_teams(request):
    """API endpoint to get all teams for the company"""
    company = request.user.company
    
    if not company:
        return Response({"error": "User not associated with any company"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Filter by department if provided
    department_id = request.query_params.get('department')
    teams = Team.objects.filter(company=company)
    
    if department_id:
        teams = teams.filter(department_id=department_id)
    
    teams = teams.order_by('name')
    teams_data = [{
        'id': team.id,
        'name': team.name,
        'department_id': team.department_id
    } for team in teams]
    
    return Response(teams_data, status=status.HTTP_200_OK)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
def get_users(request):
    """API endpoint to get users based on filters"""
    company = request.user.company
    
    if not company:
        return Response({"error": "User not associated with any company"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get filter parameters
    department_id = request.query_params.get('department')
    team_id = request.query_params.get('team')
    
    # Start with all active users in the company
    users = User.objects.filter(company=company, is_active=True, is_active_employee=True)
    
    # Apply filters
    if department_id:
        users = users.filter(department_id=department_id)
    
    if team_id:
        team_member_user_ids = TeamMember.objects.filter(team_id=team_id).values_list('employee_id', flat=True)
        users = users.filter(id__in=team_member_user_ids)
    
    users = users.order_by('username')
    users_data = [{
        'id': user.id,
        'username': user.username,
        'name': f"{user.first_name} {user.last_name}".strip() or user.username,
        'department_id': user.department_id,
        'position': user.position.name if user.position else None
    } for user in users]
    
    return Response(users_data, status=status.HTTP_200_OK)