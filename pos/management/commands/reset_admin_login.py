from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Reset the default admin login for emergency access.'

    def handle(self, *args, **options):
        call_command('ensure_default_admin', reset_password=True)
        self.stdout.write(self.style.SUCCESS('Admin login reset. Default: admin / admin123 unless env values override it.'))
