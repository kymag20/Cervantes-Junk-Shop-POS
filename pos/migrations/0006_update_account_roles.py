from django.db import migrations, models


def normalize_roles(apps, schema_editor):
    UserProfile = apps.get_model('pos', 'UserProfile')

    for profile in UserProfile.objects.select_related('user'):
        if profile.role == 'developer_admin' or profile.user.is_superuser or profile.user.is_staff:
            profile.role = 'admin'
            profile.is_email_verified = True
        elif profile.role == 'junkshop_user':
            profile.role = 'cashier'
        profile.save(update_fields=['role', 'is_email_verified'])


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0005_userprofile_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('owner', 'Owner'), ('cashier', 'Cashier'), ('encoder', 'Encoder')], default='cashier', max_length=30),
        ),
        migrations.RunPython(normalize_roles, migrations.RunPython.noop),
    ]
