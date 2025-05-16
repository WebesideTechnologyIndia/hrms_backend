import os
import glob

# List of apps to reset migrations for
apps = ['users', 'companies', 'employees']

# Delete all migration files except __init__.py
for app in apps:
    migration_path = os.path.join(app, 'migrations')
    for file in glob.glob(os.path.join(migration_path, '*.py')):
        if os.path.basename(file) != '__init__.py':
            print(f"Removing {file}")
            os.remove(file)

print("All migration files have been removed.")