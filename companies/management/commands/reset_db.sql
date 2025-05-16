-- Drop tables from your custom apps
DROP TABLE users_user CASCADE CONSTRAINTS;
DROP TABLE users_activitylog CASCADE CONSTRAINTS;
DROP TABLE users_user_permissions CASCADE CONSTRAINTS;
DROP TABLE users_user_groups CASCADE CONSTRAINTS;

DROP TABLE companies_company CASCADE CONSTRAINTS;
DROP TABLE companies_permission CASCADE CONSTRAINTS;
DROP TABLE companies_role CASCADE CONSTRAINTS;
DROP TABLE companies_role_permissions CASCADE CONSTRAINTS;
DROP TABLE companies_team CASCADE CONSTRAINTS;
DROP TABLE companies_teammember CASCADE CONSTRAINTS;
DROP TABLE companies_teamcategory CASCADE CONSTRAINTS;

DROP TABLE employees_department CASCADE CONSTRAINTS;
DROP TABLE employees_position CASCADE CONSTRAINTS;
DROP TABLE employees_positionlevel CASCADE CONSTRAINTS;
DROP TABLE employees_employeeprofile CASCADE CONSTRAINTS;
DROP TABLE employees_employeefacedata CASCADE CONSTRAINTS;
DROP TABLE employees_employeelocation CASCADE CONSTRAINTS;
DROP TABLE employees_employeescreenshot CASCADE CONSTRAINTS;
DROP TABLE employees_attendance CASCADE CONSTRAINTS;
DROP TABLE employees_attendancelog CASCADE CONSTRAINTS;
DROP TABLE employees_shift CASCADE CONSTRAINTS;
DROP TABLE employees_shiftassignment CASCADE CONSTRAINTS;
DROP TABLE employees_usershift CASCADE CONSTRAINTS;

-- Reset migration records
DELETE FROM django_migrations WHERE app IN ('users', 'companies', 'employees');