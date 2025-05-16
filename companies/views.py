from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import date
from .models import Company
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate, login, logout, get_user_model
from users.services import ActivityLogger
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()  # Use the custom User model

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def check_subscription_status(request):
    user = request.user
    
    # Superadmin check
    if getattr(user, 'role', None) == 'superadmin':
        # Log this activity
        ActivityLogger.log_activity(
            action_type='subscription_check',
            performed_by=user,
            details={
                'user_type': 'superadmin',
                'result': 'full_access'
            }
        )
        
        return Response({
            'message': 'SuperAdmin has full access. No subscription required.',
            'is_expired': False,
            'subscription_end': None,
            'subscription_plan': None
        })

    company = getattr(user, 'company', None)

    if not company:
        return Response({'error': 'No company assigned to user'}, status=404)

    # Free plan is always active
    if company.subscription_plan == 'free':
        # Log this activity
        ActivityLogger.log_activity(
            action_type='subscription_check',
            performed_by=user,
            company=company,
            details={
                'subscription_plan': 'free',
                'result': 'active'
            }
        )
        
        return Response({
            'is_expired': False,
            'subscription_end': None,
            'subscription_plan': 'free'
        })

    # Paid plan — check if subscription expired
    expired = company.subscription_end and company.subscription_end < date.today()
    
    # Log this activity
    ActivityLogger.log_activity(
        action_type='subscription_check',
        performed_by=user,
        company=company,
        details={
            'subscription_plan': 'paid',
            'subscription_end': str(company.subscription_end) if company.subscription_end else None,
            'is_expired': expired
        }
    )

    return Response({
        'is_expired': expired,
        'subscription_end': company.subscription_end,
        'subscription_plan': 'paid'
    })
# ------------------- COMPANY VIEWS -------------------
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

import json
from django.http import JsonResponse
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt  # if needed
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from .models import Company

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_company(request):
    try:
        # Access Control: Only superuser or role=superadmin can create companies.
        role = getattr(request.user, 'role', '').lower()
        if not request.user.is_superuser and role != 'superadmin':
            # Log unauthorized attempt
            ActivityLogger.log_activity(
                action_type='unauthorized_access',
                performed_by=request.user,
                details={
                    'action': 'create_company',
                    'role': role,
                    'reason': 'Only superadmin can create companies'
                }
            )
            return JsonResponse({'error': 'Only superadmin can create companies'}, status=403)

        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=405)

        data = json.loads(request.body)
        name = data.get('name')
        address = data.get('address', '')  # maps to address_line in model
        pincode = data.get('pincode', '')
        domain = data.get('domain', '')
        company_type = data.get('type', 1)  # default to IT (1)
        user_limit = data.get('user_limit')
        subscription_plan = data.get('subscription_plan', 'free').lower()
        subscription_start = data.get('subscription_start')
        subscription_end = data.get('subscription_end')

        # Validate required fields
        if not name or user_limit is None:
            return JsonResponse({'error': 'Company name and user limit are required'}, status=400)

        if Company.objects.filter(name__iexact=name).exists():
            return JsonResponse({'error': 'Company with this name already exists.'}, status=400)

        # Parse and validate subscription dates based on plan
        start_date = None
        end_date = None
        if subscription_plan == 'paid':
            try:
                if subscription_start:
                    start_date = datetime.strptime(subscription_start, "%Y-%m-%d").date()
                if subscription_end:
                    end_date = datetime.strptime(subscription_end, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            if not start_date or not end_date:
                return JsonResponse({'error': 'Paid plan requires both subscription start and end dates'}, status=400)

            if end_date <= start_date:
                return JsonResponse({'error': 'Subscription end date must be after start date'}, status=400)

        # For free plan, the subscription dates remain None.

        company = Company.objects.create(
            name=name,
            address_line=address,
            user_limit=user_limit,
            type=company_type,
            pincode=pincode,
            domain=domain,
            subscription_plan=subscription_plan,
            subscription_start=start_date,
            subscription_end=end_date,
        )
        
        # Log company creation
        ActivityLogger.log_company_created(
            performed_by=request.user,
            company=company,
            details={
                'name': name,
                'type': company_type,
                'user_limit': user_limit,
                'subscription_plan': subscription_plan,
                'subscription_start': subscription_start,
                'subscription_end': subscription_end
            }
        )

        return JsonResponse({'message': 'Company created', 'company_id': company.id})

    except IntegrityError:
        return JsonResponse({'error': 'Integrity error: Company name must be unique.'}, status=400)

    except Exception as e:
        logger.error(f"Internal Server Error in create_company: {e}")
        return JsonResponse({'error': str(e)}, status=500)
from users.models import User  # Make sure this import is at top

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_company_list(request):
    if not request.user.is_superuser and request.user.role != 'superadmin':
        # Log unauthorized attempt
        ActivityLogger.log_activity(
            action_type='unauthorized_access',
            performed_by=request.user,
            details={
                'action': 'get_company_list',
                'role': request.user.role,
                'reason': 'Only superadmin can view companies'
            }
        )
        return JsonResponse({'error': 'Only superadmin can view companies'}, status=403)

    companies = Company.objects.all()
    
    # Log activity only if:
    # 1. User is not a superadmin, AND
    # 2. This is a direct page navigation (not a component refresh within dashboard)
    
    # Check HTTP referer to determine if this is a direct navigation or a component refresh
    referer = request.META.get('HTTP_REFERER', '')
    is_direct_navigation = 'all-companies' in referer or not referer
    
    # Only log for non-superadmins on direct navigation
    if not (request.user.is_superuser or request.user.role == 'superadmin') and is_direct_navigation:
        ActivityLogger.log_activity(
            action_type='companies_listed',
            performed_by=request.user,
            details={
                'count': companies.count()
            }
        )

    company_list = []
    for company in companies:
        # Try to get Company Admin user for this company
        admin_user = User.objects.filter(company=company, role='companyadmin').first()
        company_list.append({
            'id': company.id,
            'name': company.name,
            'type': dict(Company.COMPANY_TYPES).get(company.type, 'Unknown'),
            'status': company.status,
            'user_limit': company.user_limit,
            'address_line': company.address_line,
            'pincode': company.pincode,
            'domain': company.domain,
            'subscription_plan': company.subscription_plan,
            'subscription_start': company.subscription_start.strftime('%Y-%m-%d') if company.subscription_start else None,
            'subscription_end': company.subscription_end.strftime('%Y-%m-%d') if company.subscription_end else None,
            'remaining_days': company.remaining_days,
            'is_subscription_active': company.is_subscription_active,
            # Admin user details (password is dummy)
            'admin_email': admin_user.email if admin_user else 'Not assigned',
            'admin_username': admin_user.username if admin_user else '-',
            'admin_password': '********' if admin_user else '-',
        })

    return JsonResponse({'companies': company_list})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_company_admin(request):
    try:
        if not request.user.is_superuser and request.user.role != 'superadmin':
            # Log unauthorized attempt
            ActivityLogger.log_activity(
                action_type='unauthorized_access',
                performed_by=request.user,
                details={
                    'action': 'create_company_admin',
                    'role': request.user.role,
                    'reason': 'Only superadmin can create company admins'
                }
            )
            return JsonResponse({'error': 'Only superadmin can create company admins'}, status=403)

        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        company_id = data.get('company_id')
        selected_role = data.get('role')

        # Check both field names for permissions
        permission_ids = data.get('permission_ids', data.get('permissions', []))

        logger.info(f"Received data: username={username}, email={email}, company_id={company_id}, role={selected_role}")

        if not username or not password or not selected_role:
            return JsonResponse({'error': 'Username, password, and role are required'}, status=400)

        selected_role = selected_role.replace(" ", "").lower()

        if selected_role != 'superadmin' and not company_id:
            return JsonResponse({'error': 'Company is required for non-superadmin users'}, status=400)

        # Create the user
        user = User.objects.create_user(username=username, password=password, email=email)
        user.role = selected_role

        company = None
        if selected_role != 'superadmin':
            try:
                company = Company.objects.get(id=company_id)
                user.company = company
            except Company.DoesNotExist:
                user.delete()
                return JsonResponse({'error': 'Invalid company selected'}, status=404)

        user.save()

        valid_permissions = []
        if permission_ids:
            try:
                from companies.models import Permission
                valid_permissions = Permission.objects.filter(id__in=permission_ids)
                user.permissions.clear()
                user.permissions.set(valid_permissions)
                user.save()
            except Exception as perm_error:
                logger.error(f"Error setting permissions: {perm_error}")

        # Log creation
        ActivityLogger.log_activity(
            action_type='user_created',
            performed_by=request.user,
            details={
                'new_user_id': user.id,
                'username': username,
                'email': email,
                'role': selected_role,
                'company_id': company.id if company else None,
                'permissions_count': len(valid_permissions),
                'permission_ids': [p.id for p in valid_permissions] if valid_permissions else []
            }
        )

        final_permissions = list(user.permissions.all())

        return JsonResponse({
            'message': f'{selected_role} created successfully',
            'user_id': user.id,
            'permissions_added': len(final_permissions)
        })

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

        



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_company(request, id):
    if request.method == 'DELETE':
        if not request.user.is_superuser and request.user.role != 'superadmin':
            # Log unauthorized attempt
            ActivityLogger.log_activity(
                action_type='unauthorized_access',
                performed_by=request.user,
                details={
                    'action': 'delete_company',
                    'company_id': id,
                    'role': request.user.role,
                    'reason': 'Only superadmin can delete companies'
                }
            )
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            company = Company.objects.get(id=id)
            company_name = company.name  # Store for logging
            
            # Log company deletion
            ActivityLogger.log_activity(
                action_type='company_deleted',
                performed_by=request.user,
                details={
                    'company_id': id,
                    'company_name': company_name
                }
            )
            
            company.delete()
            return JsonResponse({'message': 'Company deleted successfully'})
        except Company.DoesNotExist:
            return JsonResponse({'error': 'Company not found'}, status=404)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


from django.http import JsonResponse
from .models import Company

from django.http import JsonResponse
from .models import Company

from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import model_to_dict
def get_company(request, id):
    try:
        company = Company.objects.get(id=id)
        data = model_to_dict(company)  # 👈 all fields as dict
        return JsonResponse(data, safe=False)
    except Company.DoesNotExist:
        return JsonResponse({"error": "Company not found"}, status=404)





import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from users.models import User  # Import your custom User model


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_company(request, id):
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    if not request.user.is_superuser and request.user.role != 'superadmin':
        # Log unauthorized attempt
        ActivityLogger.log_activity(
            action_type='unauthorized_access',
            performed_by=request.user,
            details={
                'action': 'update_company',
                'company_id': id,
                'role': request.user.role,
                'reason': 'Only superadmin can update companies'
            }
        )
        return JsonResponse({'error': 'Only superadmin can update companies'}, status=403)

    try:
        company = Company.objects.get(id=id)
    except Company.DoesNotExist:
        return JsonResponse({'error': 'Company not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    # Track changes for logging
    changes = {}
    
    # Update company fields
    if data.get('name') and data.get('name') != company.name:
        changes['name'] = {'from': company.name, 'to': data.get('name')}
        company.name = data.get('name')
        
    if data.get('address_line') is not None and data.get('address_line') != company.address_line:
        changes['address_line'] = {'from': company.address_line, 'to': data.get('address_line')}
        company.address_line = data.get('address_line')

    if data.get('user_limit') is not None and data.get('user_limit') != company.user_limit:
        changes['user_limit'] = {'from': company.user_limit, 'to': data.get('user_limit')}
        company.user_limit = data.get('user_limit')
        
    if data.get('type') is not None and data.get('type') != company.type:
        changes['type'] = {'from': company.type, 'to': data.get('type')}
        company.type = data.get('type')
        
    if data.get('pincode') is not None and data.get('pincode') != company.pincode:
        changes['pincode'] = {'from': company.pincode, 'to': data.get('pincode')}
        company.pincode = data.get('pincode')
        
    if data.get('status') is not None and data.get('status') != company.status:
        changes['status'] = {'from': company.status, 'to': data.get('status')}
        company.status = data.get('status')
        
        # Log status change separately
        ActivityLogger.log_company_status_changed(
            performed_by=request.user,
            company=company,
            old_status=changes['status']['from'],
            new_status=changes['status']['to']
        )

    if data.get('domain') and data.get('domain') != company.domain:
        changes['domain'] = {'from': company.domain, 'to': data.get('domain')}
        company.domain = data.get('domain')

    if data.get('subscription_plan') and data.get('subscription_plan') != company.subscription_plan:
        changes['subscription_plan'] = {'from': company.subscription_plan, 'to': data.get('subscription_plan')}
        company.subscription_plan = data.get('subscription_plan')

    # Date parsing for subscription_start and subscription_end
    subscription_start = data.get('subscription_start')
    old_start = company.subscription_start.strftime("%Y-%m-%d") if company.subscription_start else None
    if subscription_start and subscription_start != old_start:
        try:
            new_start_date = datetime.strptime(subscription_start, "%Y-%m-%d").date()
            changes['subscription_start'] = {'from': old_start, 'to': subscription_start}
            company.subscription_start = new_start_date
        except ValueError:
            return JsonResponse({'error': 'Invalid subscription_start format. Use YYYY-MM-DD.'}, status=400)

    subscription_end = data.get('subscription_end')
    old_end = company.subscription_end.strftime("%Y-%m-%d") if company.subscription_end else None
    if subscription_end and subscription_end != old_end:
        try:
            new_end_date = datetime.strptime(subscription_end, "%Y-%m-%d").date()
            changes['subscription_end'] = {'from': old_end, 'to': subscription_end}
            company.subscription_end = new_end_date
        except ValueError:
            return JsonResponse({'error': 'Invalid subscription_end format. Use YYYY-MM-DD.'}, status=400)

    # Update password for admin user if provided
    new_password = data.get('password')
    if new_password and hasattr(company, 'admin_user'):
        admin_user = company.admin_user
        admin_user.set_password(new_password)
        admin_user.save()
        changes['admin_password'] = {'changed': True}

    # Update email for admin user if provided
    new_email = data.get('email')
    if new_email and hasattr(company, 'admin_user'):
        admin_user = company.admin_user
        old_email = admin_user.email
        if new_email != old_email:
            changes['admin_email'] = {'from': old_email, 'to': new_email}
            admin_user.email = new_email
            admin_user.save()

    company.save()
    
    # Log company update
    ActivityLogger.log_company_updated(
        performed_by=request.user,
        company=company,
        changed_fields=changes
    )
    
    return JsonResponse({'message': 'Company updated successfully', 'company_id': company.id})

from django.http import JsonResponse
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.response import Response
import pprint
from django.forms.models import model_to_dict

User = get_user_model()

@api_view(['GET'])
def get_company_admin(request, company_id):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admin_user = User.objects.get(company__id=company_id, role='companyadmin')
        
        # Get permissions
        permissions = [
            {'id': perm.id, 'name': str(perm)}
            for perm in admin_user.permissions.all()
        ]
        
        # Log the activity
        company = getattr(admin_user, 'company', None)
        ActivityLogger.log_activity(
            action_type='company_admin_viewed',
            performed_by=request.user,
            company=company,
            details={
                'company_id': company_id,
                'admin_id': admin_user.id,
                'admin_username': admin_user.username
            }
        )

        return Response({
            'id': admin_user.id,
            'username': admin_user.username,
            'email': admin_user.email,
            'role': admin_user.role,
            'permissions': permissions
        })
    except User.DoesNotExist:
        logger.error(f"No admin user found for company ID {company_id}")
        return Response({'error': 'No admin user found for this company'}, status=404)
    except Exception as e:
        logger.error(f"Error getting company admin: {str(e)}")
        return Response({'error': str(e)}, status=500)



from companies.models import Permission
# Get all permissions with activity logging
@api_view(['GET'])
def get_all_permissions(request):
    try:
        permissions = Permission.objects.all()
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='all_permissions_viewed',
            performed_by=request.user,
            company=getattr(request.user, 'company', None),
            details={
                'permissions_count': permissions.count()
            }
        )
        
        return Response([
            {'id': perm.id, 'name': perm.name, 'code': perm.code}
            for perm in permissions
        ])
    except Exception as e:
        logger.error(f"Error getting all permissions: {str(e)}")
        return Response({'error': str(e)}, status=500)

# companies/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from django.db import transaction
import json

from .models import Role, Permission
from employees.models import Position
from django.contrib.auth.decorators import login_required

# Helper function to convert model to dict with related objects
def model_to_dict_with_related(instance, related_fields=None):
    data = model_to_dict(instance)
    if related_fields:
        for field in related_fields:
            if hasattr(instance, field):
                related_obj = getattr(instance, field)
                if hasattr(related_obj, 'all'):  # M2M or reverse FK
                    data[field] = [model_to_dict(item) for item in related_obj.all()]
                else:  # FK
                    data[field] = model_to_dict(related_obj) if related_obj else None
    return data

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from companies.models import Role, Permission
from django.forms.models import model_to_dict
from django.db import transaction

# Role API Endpoints with Access Level Support
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def role_list_create(request):
    if request.method == "GET":
        roles = Role.objects.filter(company=request.user.company)
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='roles_listed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'count': roles.count()
            }
        )
        
        roles_data = []
        for role in roles:
            role_dict = model_to_dict(role)
            role_dict['permissions'] = [model_to_dict(p) for p in role.permissions.all()]
            roles_data.append(role_dict)
        return Response(roles_data)

    elif request.method == "POST":
        try:
            data = request.data
            name = data.get('name')
            is_default = data.get('is_default', False)
            permission_identifiers = data.get('permission_ids', [])
            
            # Get the additional fields
            department_id = data.get('department_id')
            position_id = data.get('position_id')
            position_level_id = data.get('position_level_id')
            
            # Get the new access_level field
            access_level = data.get('access_level', 'department')  # Default to department level
            
            # Validate access level
            valid_access_levels = ['self', 'department', 'team', 'company']
            if access_level not in valid_access_levels:
                return Response(
                    {'error': f"Invalid access level. Must be one of: {', '.join(valid_access_levels)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            role_kwargs = {
                'name': name,
                'company': request.user.company,
                'is_default': is_default,
                'access_level': access_level  # Add access level to role creation
            }
            
            # Add these fields if they're provided
            if department_id:
                role_kwargs['department_id'] = department_id
            if position_id:
                role_kwargs['position_id'] = position_id
            if position_level_id:
                role_kwargs['position_level_id'] = position_level_id

            with transaction.atomic():
                role = Role.objects.create(**role_kwargs)
                
                # Set permissions
                permissions = []
                if permission_identifiers:
                    # Try to handle both numeric IDs and string identifiers
                    numeric_ids = []
                    string_identifiers = []
                    
                    for identifier in permission_identifiers:
                        try:
                            numeric_ids.append(int(identifier))
                        except (ValueError, TypeError):
                            string_identifiers.append(identifier)
                    
                    # Query permissions by ID
                    if numeric_ids:
                        id_permissions = Permission.objects.filter(id__in=numeric_ids)
                        permissions.extend(id_permissions)
                    
                    # Query permissions by codename
                    if string_identifiers:
                        # Try codename field first
                        code_permissions = Permission.objects.filter(code__in=string_identifiers)
                        permissions.extend(code_permissions)
                        
                        # If no permissions found by codename, try with name field
                        if not code_permissions.exists():
                            name_permissions = Permission.objects.filter(name__in=string_identifiers)
                            permissions.extend(name_permissions)
                    
                    # Set the permissions
                    role.permissions.set(permissions)

                if is_default:
                    Role.objects.filter(company=request.user.company).exclude(id=role.id).update(is_default=False)

                # Log role creation with access level
                ActivityLogger.log_activity(
                    action_type='role_created',
                    performed_by=request.user,
                    company=request.user.company,
                    details={
                        'role_id': role.id,
                        'role_name': role.name,
                        'is_default': is_default,
                        'department_id': department_id,
                        'position_id': position_id,
                        'position_level_id': position_level_id,
                        'access_level': access_level,
                        'permission_count': len(permissions),
                        'permission_ids': [p.id for p in permissions]
                    }
                )
                
                # Create response
                role_dict = model_to_dict(role)
                role_dict['permissions'] = [model_to_dict(p) for p in role.permissions.all()]
                
                return Response(role_dict, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Position and Role Detail Views with Activity Logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from employees.models import Position

@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
@login_required
def role_detail(request, role_id):
    role = get_object_or_404(Role, id=role_id, company=request.user.company)
    
    if request.method == "GET":
        role_dict = model_to_dict(role)
        role_dict['permissions'] = [model_to_dict(p) for p in role.permissions.all()]
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='role_viewed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'role_id': role.id,
                'role_name': role.name
            }
        )
        
        return JsonResponse(role_dict)
    
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            name = data.get('name')
            is_default = data.get('is_default', False)
            permission_ids = data.get('permission_ids', None)
            
            # Track changes for logging
            changes = {}
            if name and name != role.name:
                changes['name'] = {'from': role.name, 'to': name}
            
            if is_default != role.is_default:
                changes['is_default'] = {'from': role.is_default, 'to': is_default}
            
            old_permission_ids = [p.id for p in role.permissions.all()]
            
            with transaction.atomic():
                # Update role
                if name:
                    role.name = name
                role.is_default = is_default
                role.save()
                
                # Update permissions if provided
                if permission_ids is not None:
                    permissions = Permission.objects.filter(id__in=permission_ids)
                    role.permissions.set(permissions)
                    changes['permissions'] = {
                        'from': old_permission_ids,
                        'to': permission_ids
                    }
                
                # If this role is set as default, unset other defaults
                if is_default:
                    Role.objects.filter(company=request.user.company).exclude(id=role.id).update(is_default=False)
                
                # Log the activity
                ActivityLogger.log_activity(
                    action_type='role_updated',
                    performed_by=request.user,
                    company=request.user.company,
                    details={
                        'role_id': role.id,
                        'role_name': name or role.name,
                        'changes': changes
                    }
                )
                
                # Prepare response
                role_dict = model_to_dict(role)
                role_dict['permissions'] = [model_to_dict(p) for p in role.permissions.all()]
                
                return JsonResponse(role_dict)
        except Exception as e:
            logger.error(f"Error updating role: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == "DELETE":
        try:
            role_name = role.name  # Store for logging
            
            # Check if this role is used by any positions
            if role.positions.exists():
                return JsonResponse({'error': 'Cannot delete role that is assigned to positions'}, status=400)
            
            # Log before deletion
            ActivityLogger.log_activity(
                action_type='role_deleted',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'role_id': role.id,
                    'role_name': role_name
                }
            )
            
            role.delete()
            return JsonResponse({'message': 'Role deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting role: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
# Position API endpoints
@csrf_exempt
@require_http_methods(["GET", "POST"])
@login_required
def position_list_create(request):
    if request.method == "GET":
        positions = Position.objects.filter(company=request.user.company)
        positions_data = []
        for position in positions:
            position_dict = model_to_dict(position)
            if position.role:
                position_dict['role_name'] = position.role.name
            else:
                position_dict['role_name'] = None
            positions_data.append(position_dict)
        return JsonResponse(positions_data, safe=False)
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get('name')
            role_id = data.get('role')
            
            # Validate role belongs to company
            if role_id:
                role = get_object_or_404(Role, id=role_id, company=request.user.company)
            else:
                role = None
            
            # Create position
            position = Position.objects.create(
                name=name,
                company=request.user.company,
                role=role
            )
            
            # Prepare response
            position_dict = model_to_dict(position)
            position_dict['role_name'] = role.name if role else None
            
            return JsonResponse(position_dict, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
@login_required
def position_detail(request, position_id):
    position = get_object_or_404(Position, id=position_id, company=request.user.company)
    
    if request.method == "GET":
        position_dict = model_to_dict(position)
        position_dict['role_name'] = position.role.name if position.role else None
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='position_viewed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'position_id': position.id,
                'position_name': position.name
            }
        )
        
        return JsonResponse(position_dict)
    
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            name = data.get('name')
            role_id = data.get('role')
            
            # Track changes for logging
            changes = {}
            if name and name != position.name:
                changes['name'] = {'from': position.name, 'to': name}
            
            old_role_id = position.role.id if position.role else None
            old_role_name = position.role.name if position.role else None
            
            # Validate role belongs to company
            role = None
            if role_id:
                role = get_object_or_404(Role, id=role_id, company=request.user.company)
                if old_role_id != role_id:
                    changes['role'] = {
                        'from': {'id': old_role_id, 'name': old_role_name},
                        'to': {'id': role_id, 'name': role.name}
                    }
            elif old_role_id is not None:
                # Role was removed
                changes['role'] = {
                    'from': {'id': old_role_id, 'name': old_role_name},
                    'to': None
                }
            
            # Update position
            if name:
                position.name = name
            position.role = role
            position.save()
            
            # Log the activity
            ActivityLogger.log_activity(
                action_type='position_updated',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'position_id': position.id,
                    'position_name': name or position.name,
                    'changes': changes
                }
            )
            
            # Prepare response
            position_dict = model_to_dict(position)
            position_dict['role_name'] = role.name if role else None
            
            return JsonResponse(position_dict)
        except Exception as e:
            logger.error(f"Error updating position: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == "DELETE":
        try:
            position_name = position.name  # Store for logging
            
            # Check if this position is used by any users
            if position.users.exists():
                return JsonResponse({'error': 'Cannot delete position that is assigned to users'}, status=400)
            
            # Log before deletion
            ActivityLogger.log_activity(
                action_type='position_deleted',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'position_id': position.id,
                    'position_name': position_name
                }
            )
            
            position.delete()
            return JsonResponse({'message': 'Position deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting position: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

# Get permissions for roles with activity logging
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_permissions(request):
    try:
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "User does not have a company assigned."}, status=400)
        
        company_type = "tech" if company.type == 1 else "educational"
        permissions = Permission.objects.filter(company_type=company_type)
        permissions_data = [model_to_dict(p) for p in permissions]
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='permissions_listed',
            performed_by=request.user,
            company=company,
            details={
                'company_type': company_type,
                'permissions_count': len(permissions_data)
            }
        )
        
        return Response(permissions_data)
    except Exception as e:
        logger.error(f"Error getting permissions: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# ts permissions for a specific role
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def role_permissions(request, role_id):
    logger.info(f"Fetching permissions for role_id: {role_id}")
    
    try:
        from django.shortcuts import get_object_or_404
        from django.forms.models import model_to_dict
        
        role = get_object_or_404(Role, id=role_id, company=request.user.company)
        logger.info(f"Found role: {role.name}")
        
        permissions = role.permissions.all()
        logger.info(f"Number of permissions found: {permissions.count()}")
        
        for p in permissions:
            logger.info(f"  - Permission: {p.id}, {p.name}, {p.code}")
        
        permissions_data = [model_to_dict(p) for p in permissions]
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='role_permissions_viewed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'role_id': role_id,
                'role_name': role.name,
                'permission_count': permissions.count()
            }
        )
        
        return JsonResponse(permissions_data, safe=False)
    except Role.DoesNotExist:
        logger.error(f"Role with ID {role_id} not found")
        return JsonResponse({"error": "Role not found"}, status=404)
    except Exception as e:
        logger.error(f"Error fetching role permissions: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from users.services import ActivityLogger
from companies.models import Role, Permission
from django.forms.models import model_to_dict
from django.db import transaction
import json
import logging

logger = logging.getLogger(__name__)

# Assigns permissions to a role
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_permissions(request, role_id):
    try:
        from django.shortcuts import get_object_or_404
        
        role = get_object_or_404(Role, id=role_id, company=request.user.company)
        
        try:
            data = json.loads(request.body)
            permission_ids = data.get('permission_ids', [])
            
            # Get old permissions for logging
            old_permissions = list(role.permissions.all())
            old_permission_ids = [p.id for p in old_permissions]
            
            # Set new permissions
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
            
            # Log the activity
            ActivityLogger.log_activity(
                action_type='role_permissions_updated',
                performed_by=request.user,
                company=request.user.company,
                details={
                    'role_id': role_id,
                    'role_name': role.name,
                    'old_permission_ids': old_permission_ids,
                    'new_permission_ids': permission_ids,
                    'old_permission_count': len(old_permissions),
                    'new_permission_count': len(permissions)
                }
            )
            
            return JsonResponse({'status': 'Permissions assigned successfully'})
        except Exception as e:
            logger.error(f"Error assigning permissions to role: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    except Role.DoesNotExist:
        return JsonResponse({'error': 'Role not found'}, status=404)


# Gets permissions for a user
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from users.services import ActivityLogger
from companies.models import Role, Permission
import json
import logging

logger = logging.getLogger(__name__)

# Gets permissions for a user
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_permissions(request):
    user = request.user
    permission_code = request.query_params.get("permission_code")  # <- Capture code here
    permissions_list = []
    
    logger.info(f"Getting permissions for user: {user.username}, role: {user.role}")
    
    # Direct permissions
    if hasattr(user, 'permissions'):
        try:
            user_permissions = user.permissions.all()
            permissions_list = [{"code": p.code, "name": p.name, "category": p.category or "Other"} for p in user_permissions]
        except Exception as e:
            logger.error(f"Error getting user permissions: {str(e)}")

    # Superadmin override
    if user.role == 'superadmin':
        try:
            all_permissions = Permission.objects.all()
            for p in all_permissions:
                if not any(perm['code'] == p.code for perm in permissions_list):
                    permissions_list.append({"code": p.code, "name": p.name, "category": p.category or "Other"})
        except Exception as e:
            logger.error(f"Error getting all permissions for superadmin: {str(e)}")

    # Filter if permission_code provided
    if permission_code:
        has_permission = any(p['code'] == permission_code for p in permissions_list)
        return Response({"has_permission": has_permission})

    # Log activity
    ActivityLogger.log_activity(
        action_type='permissions_viewed',
        performed_by=user,
        company=getattr(user, 'company', None),
        details={'permission_count': len(permissions_list)}
    )

    return Response({"permissions": permissions_list})

#  Checks if a user has a specific permission
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_permission(request):
    user = request.user
    permission_code = request.GET.get('code', '')
    
    if not permission_code:
        return JsonResponse({'error': 'Permission code is required'}, status=400)
    
    has_permission = user.has_permission(permission_code)
    
    # Log the activity
    ActivityLogger.log_activity(
        action_type='permission_check',
        performed_by=user,
        company=getattr(user, 'company', None),
        details={
            'permission_code': permission_code,
            'has_permission': has_permission
        }
    )
    
    return JsonResponse({'has_permission': has_permission})

# Add to companies/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Dashboard stats with activity logging
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    # Get stats
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        from employees.models import Department
        
        company = getattr(request.user, 'company', None)
        if not company:
            return Response(
                {"error": "User does not have a company assigned"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate stats
        total_employees = User.objects.filter(company=company).count()
        active_employees = User.objects.filter(company=company, is_active=True, is_active_employee=True).count()
        departments = Department.objects.filter(company=company).count()
        # You would need to adjust the leaves_pending query based on your model structure
        leaves_pending = 0  # This should be replaced with actual query
        
        stats = {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "departments": departments,
            "leaves_pending": leaves_pending,
        }
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='dashboard_viewed',
            performed_by=request.user,
            company=company,
            details={
                'stats_snapshot': stats
            }
        )
        
        return Response(stats)
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return Response(
            {"error": "Failed to fetch dashboard stats", "details": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# companies/views.py (add this function)

# Get roles for form with activity logging
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_roles_for_form(request):
    """Get roles with department, position, and position level names for forms."""
    try:
        # Get roles for the user's company
        company = getattr(request.user, 'company', None)
        if not company:
            return Response(
                {"error": "User does not have a company assigned"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        roles = Role.objects.filter(company=company)
        
        # Create an enriched response with related entity names
        enriched_roles = []
        for role in roles:
            role_data = {
                'id': role.id,
                'name': role.name,
                'is_default': role.is_default,
                'department': role.department_id if role.department else None,
                'position': role.position_id if role.position else None,
                'position_level': role.position_level_id if role.position_level else None,
            }
            
            # Add names of related entities
            if role.department:
                role_data['department_name'] = role.department.name
            else:
                role_data['department_name'] = None
                
            if role.position:
                role_data['position_name'] = role.position.name
            else:
                role_data['position_name'] = None
                
            if role.position_level:
                role_data['position_level_name'] = role.position_level.name
            else:
                role_data['position_level_name'] = None
                
            enriched_roles.append(role_data)
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='roles_form_data_viewed',
            performed_by=request.user,
            company=company,
            details={
                'roles_count': len(enriched_roles)
            }
        )
            
        return Response(enriched_roles)
    except Exception as e:
        logger.error(f"Error getting roles for form: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
# Get permissions for a specific user by ID
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_permissions(request, user_id): 
    """Get permissions for a specific user by ID."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get the user
        user = User.objects.get(id=user_id)
        
        # Get the user's permissions
        permissions_list = []
        
        # Check for directly assigned permissions to the user
        if hasattr(user, 'permissions'):
            try:
                # Get permissions directly assigned to the user
                user_permissions = user.permissions.all()
                permissions_list = [
                    {"id": p.id, "name": p.name, "code": p.code} 
                    for p in user_permissions
                ]
                logger.info(f"Found {len(permissions_list)} direct permissions for user {user.username}")
            except Exception as e:
                logger.error(f"Error getting user permissions: {str(e)}")
        
        # Log the activity
        ActivityLogger.log_activity(
            action_type='user_permissions_viewed',
            performed_by=request.user,
            company=getattr(request.user, 'company', None),
            details={
                'target_user_id': user_id,
                'target_username': user.username,
                'permission_count': len(permissions_list)
            }
        )
        
        return Response({"permissions": permissions_list})
    
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching user permissions: {str(e)}")
        return Response({"error": str(e)}, status=500)


# teams/views.py (updated)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .models import Team, TeamMember, TeamCategory
from django.contrib.auth import get_user_model
from users.services import ActivityLogger
import json
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_team_category(request):
    try:
        data = json.loads(request.body)
        name = data.get('name')
        
        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)
            
        # Check if category already exists for this company
        if TeamCategory.objects.filter(name=name, company=request.user.company).exists():
            return JsonResponse({'error': 'A category with this name already exists'}, status=400)
            
        # Create category
        category = TeamCategory.objects.create(
            name=name,
            company=request.user.company
        )
        
        ActivityLogger.log_activity(
            action_type='team_category_created',
            performed_by=request.user,
            company=request.user.company,
            details={
                'category_id': category.id,
                'category_name': name
            }
        )
        
        return JsonResponse({
            'id': category.id,
            'name': category.name,
            'created_at': category.created_at.strftime('%Y-%m-%d %H:%M')
        }, status=201)
            
    except Exception as e:
        logger.error(f"Error creating team category: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_team_categories(request):
    try:
        categories = TeamCategory.objects.filter(company=request.user.company)
        categories_data = []
        
        for category in categories:
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'created_at': category.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return JsonResponse({'categories': categories_data})
        
    except Exception as e:
        logger.error(f"Error listing team categories: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_team(request):
    # Check permission
    if not request.user.has_permission('tech_create_team'):
        ActivityLogger.log_activity(
            action_type='unauthorized_access',
            performed_by=request.user,
            details={
                'action': 'create_team',
                'reason': 'User does not have team_create permission'
            }
        )
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        name = data.get('name')
        category_id = data.get('category_id')
        department_id = data.get('department_id')
        director_id = data.get('director_id')
        manager_id = data.get('manager_id')
        team_leader_id = data.get('team_leader_id')  # Added team leader ID
        employee_ids = data.get('employee_ids', [])
        
        # Validate required fields
        if not name or not department_id:
            return JsonResponse({'error': 'Team name and department are required'}, status=400)
            
        # Create team
        team = Team.objects.create(
            name=name,
            category_id=category_id,
            company=request.user.company,
            department_id=department_id,
            director_id=director_id,
            manager_id=manager_id,
            team_leader_id=team_leader_id  # Added team leader ID
        )
        
        # Add team members
        for employee_id in employee_ids:
            # Make sure team leader is not added as a regular member
            if team_leader_id and int(employee_id) == int(team_leader_id):
                continue
                
            TeamMember.objects.create(
                team=team,
                employee_id=employee_id
            )
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='team_created',
            performed_by=request.user,
            company=request.user.company,
            details={
                'team_id': team.id,
                'team_name': name,
                'category_id': category_id,
                'department_id': department_id,
                'director_id': director_id,
                'manager_id': manager_id,
                'team_leader_id': team_leader_id,  # Added team leader ID
                'employee_count': len(employee_ids)
            }
        )
        
        return JsonResponse({
            'message': 'Team created successfully',
            'team_id': team.id
        }, status=201)
            
    except Exception as e:
        logger.error(f"Error creating team: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_team(request, team_id):
    try:
        team = Team.objects.get(id=team_id, company=request.user.company)
        
        data = json.loads(request.body)
        name = data.get('name')
        category_id = data.get('category_id')
        department_id = data.get('department_id')
        director_id = data.get('director_id')
        manager_id = data.get('manager_id')
        team_leader_id = data.get('team_leader_id')  # Added team leader ID
        employee_ids = data.get('employee_ids', [])
        
        # Validate required fields
        if not name or not department_id:
            return JsonResponse({'error': 'Team name and department are required'}, status=400)
            
        # Update team
        team.name = name
        team.category_id = category_id
        team.department_id = department_id
        team.director_id = director_id
        team.manager_id = manager_id
        team.team_leader_id = team_leader_id  # Added team leader ID
        team.save()
        
        # Remove existing team members
        TeamMember.objects.filter(team=team).delete()
        
        # Add team members
        for employee_id in employee_ids:
            # Make sure team leader is not added as a regular member
            if team_leader_id and int(employee_id) == int(team_leader_id):
                continue
                
            TeamMember.objects.create(
                team=team,
                employee_id=employee_id
            )
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='team_updated',
            performed_by=request.user,
            company=request.user.company,
            details={
                'team_id': team.id,
                'team_name': name,
                'category_id': category_id,
                'department_id': department_id,
                'director_id': director_id,
                'manager_id': manager_id,
                'team_leader_id': team_leader_id,  # Added team leader ID
                'employee_count': len(employee_ids)
            }
        )
        
        return JsonResponse({
            'message': 'Team updated successfully',
            'team_id': team.id
        })
            
    except Team.DoesNotExist:
        return JsonResponse({'error': 'Team not found'}, status=404)
    except Exception as e:
        logger.error(f"Error updating team: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_team(request, team_id):
    try:
        team = Team.objects.get(id=team_id, company=request.user.company)
        team_name = team.name
        
        # Delete team
        team.delete()
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='team_deleted',
            performed_by=request.user,
            company=request.user.company,
            details={
                'team_id': team_id,
                'team_name': team_name
            }
        )
        
        return JsonResponse({
            'message': 'Team deleted successfully'
        })
            
    except Team.DoesNotExist:
        return JsonResponse({'error': 'Team not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting team: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_teams(request):
    try:
        # Handle filtering teams by department if department_id is provided
        department_id = request.GET.get('department_id')
        
        teams_query = Team.objects.filter(company=request.user.company)
        if department_id:
            teams_query = teams_query.filter(department_id=department_id)
        
        teams = teams_query.all()
        teams_data = []
        
        for team in teams:
            members = TeamMember.objects.filter(team=team)
            
            team_data = {
                'id': team.id,
                'name': team.name,
                'category': {
                    'id': team.category.id,
                    'name': team.category.name
                } if team.category else None,
                'department': {
                    'id': team.department.id,
                    'name': team.department.name
                } if team.department else None,
                'director': {
                    'id': team.director.id,
                    'name': f"{team.director.first_name} {team.director.last_name}".strip() or team.director.username
                } if team.director else None,
                'manager': {
                    'id': team.manager.id,
                    'name': f"{team.manager.first_name} {team.manager.last_name}".strip() or team.manager.username
                } if team.manager else None,
                'team_leader': {  # Added team leader
                    'id': team.team_leader.id,
                    'name': f"{team.team_leader.first_name} {team.team_leader.last_name}".strip() or team.team_leader.username
                } if hasattr(team, 'team_leader') and team.team_leader else None,
                'member_count': members.count(),
                'created_at': team.created_at.strftime('%Y-%m-%d %H:%M')
            }
            
            teams_data.append(team_data)
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='teams_listed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'team_count': len(teams_data)
            }
        )
        
        return JsonResponse({'teams': teams_data})
        
    except Exception as e:
        logger.error(f"Error listing teams: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_team_details(request, team_id):
    try:
        team = Team.objects.get(id=team_id, company=request.user.company)
        members = TeamMember.objects.filter(team=team)
        
        # Get all employees in the team's department
        department_employees = []
        if team.department:
            employees = User.objects.filter(company=request.user.company, department=team.department)
            for employee in employees:
                is_member = TeamMember.objects.filter(team=team, employee=employee).exists()
                # Check if employee is the team leader
                is_team_leader = hasattr(team, 'team_leader') and team.team_leader and team.team_leader.id == employee.id
                
                department_employees.append({
                    'id': employee.id,
                    'name': f"{employee.first_name} {employee.last_name}".strip() or employee.username,
                    'position': employee.position.name if hasattr(employee, 'position') and employee.position else None,
                    'is_member': is_member,
                    'is_team_leader': is_team_leader  # Added team leader flag
                })
        
        # Get current team members
        member_data = []
        for member in members:
            employee = member.employee
            member_data.append({
                'id': employee.id,
                'name': f"{employee.first_name} {employee.last_name}".strip() or employee.username,
                'position': employee.position.name if hasattr(employee, 'position') and employee.position else None,
                'added_at': member.added_at.strftime('%Y-%m-%d')
            })
        
        team_data = {
            'id': team.id,
            'name': team.name,
            'category': {
                'id': team.category.id,
                'name': team.category.name
            } if team.category else None,
            'department': {
                'id': team.department.id,
                'name': team.department.name
            } if team.department else None,
            'director': {
                'id': team.director.id,
                'name': f"{team.director.first_name} {team.director.last_name}".strip() or team.director.username
            } if team.director else None,
            'manager': {
                'id': team.manager.id,
                'name': f"{team.manager.first_name} {team.manager.last_name}".strip() or team.manager.username
            } if team.manager else None,
            'team_leader': {  # Added team leader
                'id': team.team_leader.id,
                'name': f"{team.team_leader.first_name} {team.team_leader.last_name}".strip() or team.team_leader.username
            } if hasattr(team, 'team_leader') and team.team_leader else None,
            'members': member_data,
            'department_employees': department_employees,
            'created_at': team.created_at.strftime('%Y-%m-%d %H:%M')
        }
        
        # Log activity
        ActivityLogger.log_activity(
            action_type='team_viewed',
            performed_by=request.user,
            company=request.user.company,
            details={
                'team_id': team.id,
                'team_name': team.name
            }
        )
        
        return JsonResponse(team_data)
        
    except Team.DoesNotExist:
        return JsonResponse({'error': 'Team not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting team details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_personnel(request, department_id):
    try:
        department_id = int(department_id)
        
        # Get all employees in this department
        employees = User.objects.filter(
            company=request.user.company,
            department_id=department_id
        )
        
        # Filter by user_role instead of role
        directors = []
        managers = []
        team_leaders = []  # Added team leaders list
        regular_employees = []
        
        for employee in employees:
            # Get the employee's full name or username
            full_name = f"{employee.first_name} {employee.last_name}".strip() or employee.username
            
            # Check user_role instead of role attribute
            if employee.user_role and 'director' in employee.user_role.name.lower():
                directors.append({
                    'id': employee.id,
                    'name': full_name
                })
            elif employee.user_role and 'manager' in employee.user_role.name.lower():
                managers.append({
                    'id': employee.id,
                    'name': full_name
                })
            elif employee.user_role and 'team leader' in employee.user_role.name.lower():
                team_leaders.append({  # Added team leaders
                    'id': employee.id,
                    'name': full_name
                })
            else:
                regular_employees.append({
                    'id': employee.id,
                    'name': full_name
                })
        
        return JsonResponse({
            'directors': directors,
            'managers': managers,
            'team_leaders': team_leaders,  # Added team leaders
            'employees': regular_employees
        })
    except Exception as e:
        logger.error(f"Error getting department personnel: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from companies.models import Role

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_role_access_level(request, role_id):
    """
    API endpoint to get a role's access level.
    """
    try:
        # Get the role by ID
        role = Role.objects.get(id=role_id)
        
        # Check if the role belongs to the user's company
        if role.company != request.user.company:
            return Response({'error': 'You do not have access to this role'}, status=403)
        
        # Return the role details with access level
        return Response({
            'id': role.id,
            'name': role.name,
            'access_level': role.access_level,
            'department': role.department_id,
            'position': role.position_id,
            'position_level': role.position_level_id,
            'department_name': role.department.name if role.department else None,
            'position_name': role.position.name if role.position else None,
            'position_level_name': role.position_level.name if role.position_level else None
        })
    except Role.DoesNotExist:
        return Response({'error': 'Role not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
# Alternative implementation if you prefer not to use DRF decorators
@login_required
@require_http_methods(["GET"])
def get_role_access_level_simple(request, role_id):
    """
    Simple Django view to get a role's access level.
    """
    try:
        # Get the role by ID
        role = Role.objects.get(id=role_id)
        
        # Return the role details with access level
        return JsonResponse({
            'id': role.id,
            'name': role.name,
            'access_level': role.access_level
        })
    except Role.DoesNotExist:
        return JsonResponse({'error': 'Role not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)