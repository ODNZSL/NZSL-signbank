# Generated migration to migrate AllowedTags M2M from legacy Tag to taggit.Tag

from django.db import migrations, models
from taggit.models import Tag as TaggitTag

# Module-level storage for migration data (used to pass data between operations)
_migration_data = {}


def read_allowedtags_data(apps, schema_editor):
    """
    Read AllowedTags M2M data from legacy Tag before AlterField.
    Stores mappings for later use.
    """
    from django.conf import settings
    force_lowercase = getattr(settings, 'FORCE_LOWERCASE_TAGS', False)

    # Get models using historical apps registry
    LegacyTag = apps.get_model('tagging', 'Tag')
    AllowedTags = apps.get_model('dictionary', 'AllowedTags')

    # Store mappings: allowedtags_id -> list of taggit_tag_names
    mappings = {}

    # Process each AllowedTags instance
    for allowed_tags in AllowedTags.objects.all():
        # Get legacy tags via the old M2M relationship
        legacy_tags = LegacyTag.objects.filter(
            allowedtags=allowed_tags
        )

        # Map to taggit tag names
        # Normalize tag names exactly as migration 0051 does
        taggit_tag_names = []
        for legacy_tag in legacy_tags:
            tag_name = legacy_tag.name
            if tag_name:
                tag_name = str(tag_name).strip()
            if force_lowercase and tag_name:
                tag_name = tag_name.lower()

            # Skip empty tags (matching migration 0051 behavior)
            if not tag_name:
                continue

            # Verify tag exists in taggit
            if TaggitTag.objects.filter(name=tag_name).exists():
                taggit_tag_names.append(tag_name)

        if taggit_tag_names:
            mappings[allowed_tags.id] = taggit_tag_names

    # Store in module-level variable
    _migration_data['mappings'] = mappings


def clear_old_allowedtags_m2m(apps, schema_editor):
    """
    Clear the old M2M relationships before AlterField runs.
    This prevents foreign key violations when Django creates the new M2M table.
    """
    AllowedTags = apps.get_model('dictionary', 'AllowedTags')

    # Clear all old M2M relationships
    # This removes rows from the old through table that reference tagging.Tag
    for allowed_tags in AllowedTags.objects.all():
        # Clear the old M2M relationship (points to tagging.Tag)
        allowed_tags.allowed_tags.clear()


def populate_allowedtags_data(apps, schema_editor):
    """
    Populate new AllowedTags M2M with taggit.Tag after AlterField.
    Uses data stored by read_allowedtags_data.

    Note: After AlterField, the historical model still has the old field definition
    cached, so we work directly with the database using raw SQL to avoid type mismatches.
    """
    from django.conf import settings
    from django.db import connection

    AllowedTags = apps.get_model('dictionary', 'AllowedTags')
    # Use historical taggit.Tag model to get tag IDs
    TaggitTagHistorical = apps.get_model('taggit', 'Tag')
    mappings = _migration_data.get('mappings', {})
    force_lowercase = getattr(settings, 'FORCE_LOWERCASE_TAGS', False)

    # Django creates M2M through tables with the pattern: {model_table}_{field_name}
    # Get the model's table name dynamically
    model_table = AllowedTags._meta.db_table
    # Construct the through table name
    through_table = f'{model_table}_allowed_tags'
    # Field names follow: {model_name}_id and {related_model_name}_id
    allowedtags_field = 'allowedtags_id'
    tag_field = 'tag_id'

    # Work directly with the through table to avoid model type mismatches
    for allowedtags_id, tag_names in mappings.items():
        # Verify AllowedTags instance exists
        if not AllowedTags.objects.filter(id=allowedtags_id).exists():
            continue

        # Collect tag IDs to add
        tag_ids_to_add = []
        for tag_name in tag_names:
            # Normalize tag name (should match migration 0051)
            normalized_name = tag_name
            if force_lowercase and normalized_name:
                normalized_name = normalized_name.lower()
            normalized_name = str(normalized_name).strip() if normalized_name else None

            if not normalized_name:
                continue

            # Get tag ID using historical model
            try:
                taggit_tag = TaggitTagHistorical.objects.get(name=normalized_name)
                tag_ids_to_add.append(taggit_tag.id)
            except TaggitTagHistorical.DoesNotExist:
                continue

        # Insert directly into the through table using raw SQL
        if tag_ids_to_add:
            with connection.cursor() as cursor:
                # Insert relationships, ignoring duplicates
                # Use PostgreSQL's ON CONFLICT or try/except for other databases
                for tag_id in tag_ids_to_add:
                    # Check if relationship already exists
                    cursor.execute(
                        f"""
                        SELECT 1 FROM {through_table}
                        WHERE {allowedtags_field} = %s AND {tag_field} = %s
                        """,
                        [allowedtags_id, tag_id]
                    )
                    if not cursor.fetchone():
                        # Insert if it doesn't exist
                        cursor.execute(
                            f"""
                            INSERT INTO {through_table} ({allowedtags_field}, {tag_field})
                            VALUES (%s, %s)
                            """,
                            [allowedtags_id, tag_id]
                        )


def reverse_migration(apps, schema_editor):
    """Reverse migration - no-op since we can't restore old M2M."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0051_migrate_tags_to_taggit'),
        ('taggit', '0001_initial'),
    ]

    operations = [
        # Step 1: Read old data before clearing
        migrations.RunPython(
            read_allowedtags_data,
            reverse_code=migrations.RunPython.noop
        ),
        # Step 2: Clear old M2M relationships (removes foreign keys to tagging.Tag)
        migrations.RunPython(
            clear_old_allowedtags_m2m,
            reverse_code=migrations.RunPython.noop
        ),
        # Step 3: Alter field to point to taggit.Tag (creates new M2M table)
        migrations.AlterField(
            model_name='allowedtags',
            name='allowed_tags',
            field=models.ManyToManyField(
                to='taggit.Tag',
                verbose_name='Allowed tags'
            ),
        ),
        # Step 4: Populate new M2M table with migrated data
        migrations.RunPython(
            populate_allowedtags_data,
            reverse_code=reverse_migration
        ),
    ]
