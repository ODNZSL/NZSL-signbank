# Generated by Django 3.2.23 on 2024-02-08 02:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0046_remove_unneeded_validation_record_fields'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='validationrecord',
            constraint=models.UniqueConstraint(fields=('gloss', 'response_id'), name='unique_gloss_response_pair'),
        ),
    ]
