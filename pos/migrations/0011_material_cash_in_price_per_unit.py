from django.db import migrations, models


def copy_cash_out_prices(apps, schema_editor):
    Material = apps.get_model('pos', 'Material')
    for material in Material.objects.all():
        material.cash_in_price_per_unit = material.price_per_unit
        material.save(update_fields=['cash_in_price_per_unit'])


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0010_transaction_transaction_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='cash_in_price_per_unit',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.RunPython(copy_cash_out_prices, migrations.RunPython.noop),
    ]
