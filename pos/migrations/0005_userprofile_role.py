from django.db import migrations, models


def assign_existing_roles(apps, schema_editor):
    UserProfile = apps.get_model('pos', 'UserProfile')

    for profile in UserProfile.objects.select_related('user'):
        if profile.user.is_superuser or profile.user.is_staff:
            profile.role = 'developer_admin'
            profile.is_email_verified = True
        else:
            profile.role = 'junkshop_user'
        profile.save(update_fields=['role', 'is_email_verified'])


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0004_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='role',
            field=models.CharField(choices=[('developer_admin', 'Developer/Admin'), ('junkshop_user', 'Junkshop User')], default='junkshop_user', max_length=30),
        ),
        migrations.RunPython(assign_existing_roles, migrations.RunPython.noop),
    ]
