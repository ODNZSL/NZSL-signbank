# Generated by Django 2.2.11 on 2022-06-20 22:54

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dictionary', '0030_merge_20220610_1148'),
    ]

    operations = [
        migrations.AddField(
            model_name='gloss',
            name='assigned_user',
            field=models.ForeignKey(limit_choices_to={
                                    'is_staff': True},
                                    null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    to=settings.AUTH_USER_MODEL,
                                    related_name='assigned_glosses'),
        ),
    ]
