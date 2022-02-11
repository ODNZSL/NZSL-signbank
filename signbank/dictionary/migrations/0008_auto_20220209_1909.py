# Generated by Django 2.2.11 on 2022-02-09 06:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0007_auto_20220202_1542'),
    ]

    operations = [
        migrations.AddField(
            model_name='glosstranslations',
            name='translations_minor',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='glosstranslations',
            name='translations_secondary',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='signer',
            field=models.ForeignKey(help_text='Signer for the Gloss', null=True, on_delete=django.db.models.deletion.PROTECT, to='dictionary.Signer', verbose_name='Signer'),
        ),
    ]
