from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0009_transaction_cancelled'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(choices=[('cash_out', 'Cash Out'), ('cash_in', 'Cash In')], default='cash_out', max_length=20),
        ),
    ]
