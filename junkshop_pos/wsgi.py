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
    call_command('ensure_default_admin', verbosity=0)
except DatabaseError as exc:
    print(f'Could not ensure default admin account: {exc}')
