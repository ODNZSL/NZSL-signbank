# Add TaggableManager fields to Gloss and GlossRelation.
# No database schema change: tags already live in taggit_taggeditem from 0051.

from django.db import migrations, models
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0001_initial'),
        ('dictionary', '0052_migrate_allowedtags_to_taggit'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='gloss',
                    name='tags',
                    field=taggit.managers.TaggableManager(
                        blank=True,
                        help_text='A comma-separated list of tags.',
                        through='taggit.TaggedItem',
                        to='taggit.Tag',
                        verbose_name='Tags',
                    ),
                ),
                migrations.AddField(
                    model_name='glossrelation',
                    name='tags',
                    field=taggit.managers.TaggableManager(
                        blank=True,
                        help_text='A comma-separated list of tags.',
                        through='taggit.TaggedItem',
                        to='taggit.Tag',
                        verbose_name='Tags',
                    ),
                ),
                migrations.AlterField(
                    model_name='allowedtags',
                    name='allowed_tags',
                    field=models.ManyToManyField(
                        to='taggit.Tag',
                        verbose_name='Allowed tags',
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
