# Generated by Django 2.2.11 on 2022-06-28 01:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0034_merge_20220623_1200'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gloss',
            name='assigned_user',
            field=models.ForeignKey(blank=True, limit_choices_to={'is_active': True, 'is_staff': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_glosses', to=settings.AUTH_USER_MODEL),
        ),
    ]
