import os
import sys

# Change YOUR_USERNAME to your PythonAnywhere username.
path = '/home/YOUR_USERNAME/junkshop_pos'

if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'junkshop_pos.settings')

# Set production values here if you did not add them to PythonAnywhere environment variables.
os.environ.setdefault('DEBUG', 'False')
os.environ.setdefault('ALLOWED_HOSTS', 'YOUR_USERNAME.pythonanywhere.com')
os.environ.setdefault('CSRF_TRUSTED_ORIGINS', 'https://YOUR_USERNAME.pythonanywhere.com')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
