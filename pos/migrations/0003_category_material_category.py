# Generated manually for category management

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_CATEGORIES = [
    ('Plastic', '#16a34a'),
    ('Paper & Cardboard', '#f59e0b'),
    ('Glass', '#0891b2'),
    ('Metals', '#64748b'),
    ('Electronics', '#7c3aed'),
    ('Rubber', '#334155'),
    ('Others', '#94a3b8'),
]


def create_default_categories(apps, schema_editor):
    Category = apps.get_model('pos', 'Category')
    Material = apps.get_model('pos', 'Material')

    categories = {}
    for name, color in DEFAULT_CATEGORIES:
        category, _ = Category.objects.get_or_create(name=name, defaults={'color': color})
        categories[name] = category

    material_keywords = {
        'Plastic': ['plastic', 'pet', 'container'],
        'Paper & Cardboard': ['paper', 'cardboard', 'carton', 'karton', 'dyaryo', 'newspaper'],
        'Glass': ['glass', 'bote', 'bottle'],
        'Metals': ['metal', 'bakal', 'iron', 'steel', 'stainless', 'aluminum', 'aluminio', 'copper', 'tanso', 'bronze', 'brass'],
        'Electronics': ['electronic', 'wire', 'cable', 'battery', 'appliance'],
        'Rubber': ['rubber', 'goma', 'tire'],
    }

    for material in Material.objects.filter(category__isnull=True):
        material_name = material.name.lower()
        matched = 'Others'
        for category_name, keywords in material_keywords.items():
            if any(keyword in material_name for keyword in keywords):
                matched = category_name
                break
        material.category = categories[matched]
        material.save(update_fields=['category'])


def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('pos', 'Category')
    Category.objects.filter(name__in=[name for name, _ in DEFAULT_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0002_customer_rename_price_per_kg_material_price_per_unit_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('color', models.CharField(default='#0891b2', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='material',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials', to='pos.category'),
        ),
        migrations.RunPython(create_default_categories, remove_default_categories),
    ]
