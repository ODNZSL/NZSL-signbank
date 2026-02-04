# Generated migration to migrate AllowedTags M2M from legacy Tag to taggit.Tag

from django.db import migrations, models


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
    TaggitTag = apps.get_model('taggit', 'Tag')
    
    # Store mappings: allowedtags_id -> list of taggit_tag_names
    mappings = {}
    
    # Process each AllowedTags instance
    for allowed_tags in AllowedTags.objects.all():
        # Get legacy tags via the old M2M relationship
        legacy_tags = LegacyTag.objects.filter(
            allowedtags=allowed_tags
        )
        
        # Map to taggit tag names
        taggit_tag_names = []
        for legacy_tag in legacy_tags:
            tag_name = legacy_tag.name
            if force_lowercase:
                tag_name = tag_name.lower()
            
            # Verify tag exists in taggit
            if TaggitTag.objects.filter(name=tag_name).exists():
                taggit_tag_names.append(tag_name)
        
        if taggit_tag_names:
            mappings[allowed_tags.id] = taggit_tag_names
    
    # Store in module-level variable
    _migration_data['mappings'] = mappings


def populate_allowedtags_data(apps, schema_editor):
    """
    Populate new AllowedTags M2M with taggit.Tag after AlterField.
    Uses data stored by read_allowedtags_data.
    """
    AllowedTags = apps.get_model('dictionary', 'AllowedTags')
    TaggitTag = apps.get_model('taggit', 'Tag')
    
    mappings = _migration_data.get('mappings', {})
    
    # Populate new M2M
    for allowedtags_id, tag_names in mappings.items():
        try:
            allowed_tags = AllowedTags.objects.get(id=allowedtags_id)
        except AllowedTags.DoesNotExist:
            continue
        
        for tag_name in tag_names:
            try:
                taggit_tag = TaggitTag.objects.get(name=tag_name)
                # Add to M2M (this will create the through table entry)
                allowed_tags.allowed_tags.add(taggit_tag)
            except TaggitTag.DoesNotExist:
                continue


def reverse_migration(apps, schema_editor):
    """Reverse migration - no-op since we can't restore old M2M."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dictionary', '0051_migrate_tags_to_taggit'),
        ('taggit', '0001_initial'),
    ]

    operations = [
        # Step 1: Read old data before AlterField
        migrations.RunPython(
            read_allowedtags_data,
            reverse_code=migrations.RunPython.noop
        ),
        # Step 2: Alter field to point to taggit.Tag (creates new M2M table)
        migrations.AlterField(
            model_name='allowedtags',
            name='allowed_tags',
            field=models.ManyToManyField(
                to='taggit.Tag',
                verbose_name='Allowed tags'
            ),
        ),
        # Step 3: Populate new M2M table
        migrations.RunPython(
            populate_allowedtags_data,
            reverse_code=reverse_migration
        ),
    ]
