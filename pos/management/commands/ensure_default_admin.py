import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from pos.models import UserProfile


class Command(BaseCommand):
    help = 'Create or update the default admin account used after deployment.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default=os.getenv('DEFAULT_ADMIN_USERNAME', 'admin'),
            help='Admin username to create or update.',
        )
        parser.add_argument(
            '--password',
            default=os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123'),
            help='Admin password to set.',
        )
        parser.add_argument(
            '--email',
            default=os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@example.com'),
            help='Admin email address.',
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            default=os.getenv('RESET_DEFAULT_ADMIN_PASSWORD', '').lower() in ['1', 'true', 'yes', 'on'],
            help='Reset the admin password even if the account already exists.',
        )

    def handle(self, *args, **options):
        username = options['username'].strip()
        password = options['password']
        email = options['email'].strip()

        if not username or not password:
            self.stderr.write(self.style.ERROR('Username and password are required.'))
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )

        changed_fields = []
        if user.email != email:
            user.email = email
            changed_fields.append('email')
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append('is_superuser')
        if not user.is_active:
            user.is_active = True
            changed_fields.append('is_active')

        if created or options['reset_password'] or not user.has_usable_password():
            user.set_password(password)
            changed_fields.append('password')
        user.save()

        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': 'Default Admin',
                'role': UserProfile.ROLE_ADMIN,
                'is_email_verified': True,
            },
        )

        profile_changed = []
        if profile.role != UserProfile.ROLE_ADMIN:
            profile.role = UserProfile.ROLE_ADMIN
            profile_changed.append('role')
        if not profile.full_name:
            profile.full_name = 'Default Admin'
            profile_changed.append('full_name')
        if not profile.is_email_verified:
            profile.is_email_verified = True
            profile_changed.append('is_email_verified')
        if profile_changed:
            profile.save(update_fields=profile_changed)

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created default admin user: {username}'))
        else:
            detail = ', '.join(changed_fields) or 'no user fields'
            self.stdout.write(self.style.SUCCESS(f'Updated default admin user: {username} ({detail})'))

        if profile_created:
            self.stdout.write(self.style.SUCCESS('Created admin profile.'))
        elif profile_changed:
            self.stdout.write(self.style.SUCCESS(f'Updated admin profile: {", ".join(profile_changed)}'))
