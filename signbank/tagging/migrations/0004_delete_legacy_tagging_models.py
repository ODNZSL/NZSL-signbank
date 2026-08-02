# Drop legacy django-tagging tables after data has been copied to taggit (dictionary.0051/0052).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tagging', '0003_adapt_max_tag_length'),
        ('dictionary', '0053_add_taggable_managers'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TaggedItem',
        ),
        migrations.DeleteModel(
            name='Tag',
        ),
    ]
