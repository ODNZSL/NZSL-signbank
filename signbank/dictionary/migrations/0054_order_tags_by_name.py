# Point tag fields at the project Tag proxy and order TaggableManager by name.

from django.db import migrations, models
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('tagging', '0005_tag_proxy_model'),
        ('dictionary', '0053_add_taggable_managers'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='gloss',
                    name='tags',
                    field=taggit.managers.TaggableManager(
                        blank=True,
                        help_text='A comma-separated list of tags.',
                        ordering=['name'],
                        through='taggit.TaggedItem',
                        to='tagging.tag',
                        verbose_name='Tags',
                    ),
                ),
                migrations.AlterField(
                    model_name='glossrelation',
                    name='tags',
                    field=taggit.managers.TaggableManager(
                        blank=True,
                        help_text='A comma-separated list of tags.',
                        ordering=['name'],
                        through='taggit.TaggedItem',
                        to='tagging.tag',
                        verbose_name='Tags',
                    ),
                ),
                migrations.AlterField(
                    model_name='allowedtags',
                    name='allowed_tags',
                    field=models.ManyToManyField(
                        to='tagging.tag',
                        verbose_name='Allowed tags',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
