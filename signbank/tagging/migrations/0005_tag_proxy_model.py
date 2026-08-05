from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0001_initial'),
        ('tagging', '0004_delete_legacy_tagging_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[],
            options={
                'ordering': ('name',),
                'proxy': True,
            },
            bases=('taggit.tag',),
        ),
    ]
