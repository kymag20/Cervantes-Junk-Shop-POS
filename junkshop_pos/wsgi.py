"""
WSGI config for junkshop_pos project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.core.management import call_command
from django.db import DatabaseError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'junkshop_pos.settings')

application = get_wsgi_application()

try:
    if os.getenv('RUN_MIGRATIONS_ON_STARTUP', 'true').lower() in ['1', 'true', 'yes', 'on']:
        call_command('migrate', interactive=False, verbosity=1)
    call_command('ensure_default_admin', verbosity=0)
except Exception as exc:
    print(f'Could not prepare database during startup: {exc}')
