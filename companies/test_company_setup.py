# test_company_setup.py
# Run this from Django shell:
# python manage.py shell < test_company_setup.py

from companies.models import Company, Permission, Role
from employees.models import Department, Position, PositionLevel
from django.db import transaction
import sys

def create_test_company():
    """Create a test company and manually set up its structure"""
    print("Creating test company...")
    
    # Create a test company
    try:
        with transaction.atomic():
            company = Company.objects.create(
                name="Test Company " + str(Company.objects.count() + 1),
                type=1,  # Tech company
                user_limit=10,
                status='active',
                subscription_plan='free'
            )
            print(f"Created company: {company.name}")
            
            # Create a test department
            dept = Department.objects.create(
                name="Test Department",
                company=company
            )
            print(f"Created department: {dept.name}")
            
            # Create a test role
            role = Role.objects.create(
                name="Test Role",
                company=company,
                is_default=False
            )
            print(f"Created role: {role.name}")
            
            # Create a test position
            position = Position.objects.create(
                name="Test Position",
                company=company,
                role=role
            )
            print(f"Created position: {position.name}")
            
            # Create a test position level
            level = PositionLevel.objects.create(
                name="Test Level",
                company=company,
                department=dept,
                role=role,
                position=position
            )
            print(f"Created position level: {level.name}")
            
            print(f"Test company setup complete for: {company.name}")
            return company
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    try:
        company = create_test_company()
        if company:
            print("Success!")
        else:
            print("Failed to create test company")
    except Exception as e:
        print(f"Unhandled exception: {str(e)}")
    
    # Exit to prevent shell from hanging
    sys.exit()