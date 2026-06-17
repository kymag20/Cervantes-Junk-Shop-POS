from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Fail production deploys that would use temporary local SQLite storage.'

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        engine = db.get('ENGINE', '')

        if 'sqlite3' not in engine:
            self.stdout.write(self.style.SUCCESS('Persistent database configured.'))
            return

        db_path = Path(str(db.get('NAME', ''))).resolve()
        base_dir = Path(settings.BASE_DIR).resolve()
        debug = bool(getattr(settings, 'DEBUG', False))

        if debug:
            self.stdout.write(self.style.WARNING(f'Local SQLite database: {db_path}'))
            return

        try:
            db_path.relative_to(base_dir)
        except ValueError:
            self.stdout.write(self.style.WARNING(f'Production SQLite database outside app folder: {db_path}'))
            return

        raise CommandError(
            'Unsafe production database: SQLite is inside the app folder and can reset on redeploy. '
            'Set DATABASE_URL to a Render PostgreSQL database before deploying.'
        )
