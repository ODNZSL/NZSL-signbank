# Generated by Django 3.2.13 on 2022-06-21 04:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flatpages', '0003_auto_20220509_1618'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='flatpage',
            options={'ordering': ['url'], 'verbose_name': 'flat page', 'verbose_name_plural': 'flat pages'},
        ),
        migrations.AlterField(
            model_name='flatpage',
            name='template_name',
            field=models.CharField(blank=True, help_text='Example: “flatpages/contact_page.html”. If this isn’t provided, the system will use “flatpages/default.html”.', max_length=70, verbose_name='template name'),
        ),
    ]
