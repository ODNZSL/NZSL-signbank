# Generated by Django 2.2.11 on 2022-02-10 22:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0008_auto_20220209_1909'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signer',
            name='name',
            field=models.CharField(max_length=150, unique=True),
        ),
    ]