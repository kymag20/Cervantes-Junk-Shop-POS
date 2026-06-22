from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0015_printersetting'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PrinterSetting',
        ),
    ]
