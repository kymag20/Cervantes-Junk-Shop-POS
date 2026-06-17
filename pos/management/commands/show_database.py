from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Show which database the system is currently using.'

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        engine = db.get('ENGINE', '')
        name = str(db.get('NAME', ''))
        host = db.get('HOST', '')

        if 'sqlite3' in engine:
            self.stdout.write(self.style.WARNING('Using local SQLite database.'))
            self.stdout.write(f'Database file: {name}')
            self.stdout.write('Accounts created here will not appear on Render.')
            return

        self.stdout.write(self.style.SUCCESS('Using shared PostgreSQL database.'))
        self.stdout.write(f'Database: {name}')
        if host:
            self.stdout.write(f'Host: {host}')
        self.stdout.write('Local and deployed accounts should match when both use this database.')
