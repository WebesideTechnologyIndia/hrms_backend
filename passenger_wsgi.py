import sys
import os

# Step 1: Project path set karo
sys.path.insert(0, '/home/mnzsjkt7dkte/hrms.vigyantechnology.com/public_html/hrm')

# Step 2: Activate virtual environment
activate_this = '/home/mnzsjkt7dkte/hrms.vigyantechnology.com/public_html/hrm/venv/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

# Step 3: Django settings set karo
os.environ['DJANGO_SETTINGS_MODULE'] = 'hrm.settings'

# Step 4: Load WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()