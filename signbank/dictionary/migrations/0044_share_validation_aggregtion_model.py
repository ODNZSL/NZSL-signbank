# Generated by Django 3.2.23 on 2024-01-30 06:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0043_new_tag_and_share_import_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShareValidationAggregation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agrees', models.PositiveIntegerField()),
                ('disagrees', models.PositiveIntegerField()),
                ('gloss', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='share_validation_aggregations', to='dictionary.gloss')),
            ],
        ),
    ]