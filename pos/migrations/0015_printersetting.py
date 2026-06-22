from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0014_material_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PrinterSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('print_method', models.CharField(choices=[('browser', 'Browser print'), ('serial', 'USB/Serial thermal printer')], default='browser', max_length=20)),
                ('paper_width', models.CharField(choices=[('58', '58mm'), ('80', '80mm'), ('a4', 'A4')], default='58', max_length=10)),
                ('auto_open_print_dialog', models.BooleanField(default=False)),
                ('receipt_copies', models.PositiveSmallIntegerField(default=1)),
                ('serial_baud_rate', models.PositiveIntegerField(default=9600)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='printer_setting', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
