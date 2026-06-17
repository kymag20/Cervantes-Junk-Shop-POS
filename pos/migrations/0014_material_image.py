from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0013_transaction_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='image_data',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='material',
            name='image_content_type',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
