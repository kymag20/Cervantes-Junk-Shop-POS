from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0012_remove_material_cash_in_price_per_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('completed', 'Completed')],
                default='completed',
                max_length=20,
            ),
        ),
    ]
