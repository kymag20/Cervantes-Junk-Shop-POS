import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def assign_existing_setup_to_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Category = apps.get_model('pos', 'Category')
    Material = apps.get_model('pos', 'Material')

    admin_user = (
        User.objects.filter(is_superuser=True).order_by('id').first()
        or User.objects.filter(profile__role='admin').order_by('id').first()
        or User.objects.order_by('id').first()
    )
    if not admin_user:
        return

    Category.objects.filter(owner__isnull=True).update(owner=admin_user)
    Material.objects.filter(owner__isnull=True).update(owner=admin_user)

    for material in Material.objects.select_related('category').filter(category__isnull=False):
        if material.category.owner_id != material.owner_id:
            material.category = None
            material.save(update_fields=['category'])


def clear_setup_owner(apps, schema_editor):
    Category = apps.get_model('pos', 'Category')
    Material = apps.get_model('pos', 'Material')
    Category.objects.update(owner=None)
    Material.objects.update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('pos', '0007_remove_cashier_encoder_roles'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='categories', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='material',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(assign_existing_setup_to_admin, clear_setup_owner),
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(fields=('owner', 'name'), name='unique_category_name_per_owner'),
        ),
    ]
