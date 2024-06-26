# Generated by Django 3.2.13 on 2022-06-21 01:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0030_merge_20220610_1148'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gloss',
            name='signer',
            field=models.ForeignKey(blank=True, help_text='Signer for the Gloss', limit_choices_to={'field': 'signer'}, null=True, on_delete=django.db.models.deletion.PROTECT, to='dictionary.fieldchoice', to_field='machine_value', verbose_name='Signer'),
        ),
    ]
