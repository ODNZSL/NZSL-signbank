# Generated by Django 2.2.11 on 2022-02-02 02:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0006_auto_20210828_0651'),
    ]

    operations = [
        migrations.CreateModel(
            name='Signer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
            ],
            options={
                'verbose_name': 'Signer',
                'verbose_name_plural': 'Signers',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='gloss',
            name='hint',
            field=models.TextField(blank=True, null=True, verbose_name='Hint'),
        ),
        migrations.AlterField(
            model_name='gloss',
            name='idgloss_mi',
            field=models.CharField(blank=True, help_text='This is the Māori name for the Gloss', max_length=150, null=True, verbose_name='Gloss in Māori'),
        ),
        migrations.AddField(
            model_name='gloss',
            name='signer',
            field=models.ForeignKey(help_text='Signer of the Gloss', null=True, on_delete=django.db.models.deletion.PROTECT, to='dictionary.Signer', verbose_name='Signer'),
        ),
    ]
