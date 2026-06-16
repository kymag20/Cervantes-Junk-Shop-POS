from django.db import migrations, models


def cashier_encoder_to_owner(apps, schema_editor):
    UserProfile = apps.get_model('pos', 'UserProfile')
    for profile in UserProfile.objects.filter(role__in=['cashier', 'encoder']):
        profile.role = 'owner'
        profile.save(update_fields=['role'])


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0006_update_account_roles'),
    ]

    operations = [
        migrations.RunPython(cashier_encoder_to_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[('admin', 'Admin'), ('owner', 'Owner')],
                default='owner',
                max_length=30,
            ),
        ),
    ]
