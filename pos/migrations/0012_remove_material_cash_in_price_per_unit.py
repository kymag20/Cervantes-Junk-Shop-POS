from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0011_material_cash_in_price_per_unit'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='material',
            name='cash_in_price_per_unit',
        ),
    ]
