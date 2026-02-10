# Generated migration to copy tags from legacy tagging tables to django-taggit

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import connection, migrations

# Import taggit models directly to get real models
# (apps.get_model() may return historical models without custom methods)
from taggit.models import Tag as TaggitTag
from taggit.models import TaggedItem as TaggitTaggedItem


def migrate_tags_to_taggit(apps, schema_editor):
    """
    Copy tags from legacy tagging tables to django-taggit tables.

    This migration handles both:
    - Existing databases: copies data from legacy tables
    - Fresh installs: does nothing (legacy tables don't exist yet)
    """
    # Check if legacy tagging tables exist
    db_table_names = connection.introspection.table_names()
    legacy_tag_table = 'tagging_tag'
    legacy_taggeditem_table = 'tagging_taggeditem'

    if legacy_tag_table not in db_table_names or legacy_taggeditem_table not in db_table_names:
        # Fresh install - no legacy tables, nothing to migrate
        return

    # Get models using historical apps registry (for legacy models)
    LegacyTag = apps.get_model('tagging', 'Tag')
    LegacyTaggedItem = apps.get_model('tagging', 'TaggedItem')

    # Use real taggit models (imported at top) so save() methods work correctly
    # Copy tags
    # Normalize tag names (lowercase if FORCE_LOWERCASE_TAGS is set)
    force_lowercase = getattr(settings, 'FORCE_LOWERCASE_TAGS', False)

    tag_mapping = {}  # old_tag_id -> new_tag_object

    # Migrate all tags from LegacyTag (this includes tags used in TaggedItem and AllowedTags)
    for legacy_tag in LegacyTag.objects.all():
        tag_name = legacy_tag.name
        if tag_name:
            tag_name = str(tag_name).strip()
        if force_lowercase and tag_name:
            tag_name = tag_name.lower()

        # Skip tags with empty names (after normalization) to avoid empty slug conflicts
        if not tag_name:
            continue

        # Get or create taggit tag - using real TaggitTag model so save() auto-generates slug
        taggit_tag, created = TaggitTag.objects.get_or_create(name=tag_name)
        tag_mapping[legacy_tag.id] = taggit_tag
    
    # Note: All tags used in AllowedTags are already migrated above since we migrate
    # all LegacyTag objects. Migration 0052 handles migrating the AllowedTags M2M
    # relationships themselves.

    # Copy tagged items
    tagged_items_to_create = []
    for legacy_item in LegacyTaggedItem.objects.select_related('tag', 'content_type').all():
        if legacy_item.tag_id not in tag_mapping:
            continue  # Skip if tag wasn't migrated

        taggit_tag = tag_mapping[legacy_item.tag_id]
         # Convert historical ContentType to current ContentType instance
        # Historical ContentType instances can't be used with real models
        legacy_content_type = legacy_item.content_type
        content_type = ContentType.objects.get(
            app_label=legacy_content_type.app_label,
            model=legacy_content_type.model
        )


        # Check if this tagged item already exists
        if not TaggitTaggedItem.objects.filter(
            tag=taggit_tag,
            content_type=content_type,
            object_id=legacy_item.object_id
        ).exists():
            tagged_items_to_create.append(
                TaggitTaggedItem(
                    tag=taggit_tag,
                    content_type=content_type,
                    object_id=legacy_item.object_id
                )
            )

    # Bulk create tagged items (ignore conflicts for idempotency)
    if tagged_items_to_create:
        TaggitTaggedItem.objects.bulk_create(
            tagged_items_to_create,
            ignore_conflicts=True
        )


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - no-op since we can't restore deleted legacy data.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0050_alter_fieldchoice_options'),
        ('tagging', '0003_adapt_max_tag_length'),
        ('taggit', '0001_initial'),  # Initial taggit migration
    ]

    operations = [
        migrations.RunPython(
            migrate_tags_to_taggit,
            reverse_code=reverse_migration
        ),
    ]
