"""
Signbank tagging adapter - stable API backed by django-taggit.

This adapter provides a future-proof interface for tagging functionality.
The backend implementation uses django-taggit, but can be swapped out
without changing application code.
"""
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.conf import settings

# Import taggit models directly - this is the implementation layer
# Runtime code should import from signbank.tagging.models instead
from taggit.models import Tag as TaggitTag, TaggedItem as TaggitTaggedItem


def _normalize_tag_name(tag_name):
    """Normalize tag name according to project settings."""
    if not tag_name:
        return tag_name
    tag_name = str(tag_name).strip()
    if getattr(settings, 'FORCE_LOWERCASE_TAGS', False):
        tag_name = tag_name.lower()
    return tag_name


def tags_for_object(obj):
    """
    Get all tags for a given object.
    
    Args:
        obj: Model instance to get tags for
        
    Returns:
        QuerySet of Tag objects
    """
    if obj.pk is None:
        return TaggitTag.objects.none()
    
    content_type = ContentType.objects.get_for_model(obj)
    # Use reverse relation to find tags
    # Taggit uses related_name pattern: taggit_taggeditem_items
    return TaggitTag.objects.filter(
        taggit_taggeditem_items__content_type=content_type,
        taggit_taggeditem_items__object_id=obj.pk
    ).distinct()


def add_tag(obj, tag_name):
    """
    Add a tag to an object.
    
    Args:
        obj: Model instance to tag
        tag_name: String name of the tag to add
    """
    if obj.pk is None:
        raise ValueError("Cannot tag an object that hasn't been saved")
    
    tag_name = _normalize_tag_name(tag_name)
    if not tag_name:
        return
    
    tag, _ = TaggitTag.objects.get_or_create(name=tag_name)
    content_type = ContentType.objects.get_for_model(obj)
    
    TaggitTaggedItem.objects.get_or_create(
        tag=tag,
        content_type=content_type,
        object_id=obj.pk
    )


def remove_tag(obj, tag_name):
    """
    Remove a tag from an object.
    
    Args:
        obj: Model instance to untag
        tag_name: String name of the tag to remove
    """
    if obj.pk is None:
        return
    
    tag_name = _normalize_tag_name(tag_name)
    if not tag_name:
        return
    
    try:
        tag = TaggitTag.objects.get(name=tag_name)
    except TaggitTag.DoesNotExist:
        return
    
    content_type = ContentType.objects.get_for_model(obj)
    TaggitTaggedItem.objects.filter(
        tag=tag,
        content_type=content_type,
        object_id=obj.pk
    ).delete()


def filter_queryset_with_all_tags(queryset, tag_names):
    """
    Filter a queryset to objects that have ALL of the specified tags (intersection).
    
    Args:
        queryset: QuerySet to filter
        tag_names: List of tag names (strings) or Tag objects
        
    Returns:
        Filtered QuerySet
    """
    model = queryset.model
    
    if not tag_names:
        return model._default_manager.none()
    
    # Normalize tag names and get Tag objects
    tag_names = [_normalize_tag_name(name) for name in tag_names if name]
    if not tag_names:
        return model._default_manager.none()
    
    tags = TaggitTag.objects.filter(name__in=tag_names)
    if not tags.exists():
        return model._default_manager.none()
    
    content_type = ContentType.objects.get_for_model(model)
    
    # Get object IDs that have all the tags
    # We need objects that have ALL tags, so we count distinct tags per object
    # and filter to those with count == number of tags
    from django.db.models import Count
    
    tagged_items = TaggitTaggedItem.objects.filter(
        content_type=content_type,
        tag__in=tags
    ).values('object_id').annotate(
        tag_count=Count('tag', distinct=True)
    ).filter(tag_count=len(tags))
    
    object_ids = [item['object_id'] for item in tagged_items]
    
    if object_ids:
        return queryset.filter(pk__in=object_ids)
    else:
        return model._default_manager.none()


def filter_queryset_with_any_tags(queryset, tag_names):
    """
    Filter a queryset to objects that have ANY of the specified tags (union).
    
    Args:
        queryset: QuerySet to filter
        tag_names: List of tag names (strings) or Tag objects
        
    Returns:
        Filtered QuerySet
    """
    model = queryset.model
    
    if not tag_names:
        return model._default_manager.none()
    
    # Normalize tag names and get Tag objects
    tag_names = [_normalize_tag_name(name) for name in tag_names if name]
    if not tag_names:
        return model._default_manager.none()
    
    tags = TaggitTag.objects.filter(name__in=tag_names)
    if not tags.exists():
        return model._default_manager.none()
    
    content_type = ContentType.objects.get_for_model(model)
    
    # Get object IDs that have any of the tags
    object_ids = TaggitTaggedItem.objects.filter(
        content_type=content_type,
        tag__in=tags
    ).values_list('object_id', flat=True).distinct()
    
    if object_ids:
        return queryset.filter(pk__in=object_ids)
    else:
        return model._default_manager.none()


def tags_usage_for_model(model_or_queryset, with_counts=False):
    """
    Get tags used for a model or queryset.
    
    Args:
        model_or_queryset: Model class or QuerySet
        with_counts: If True, include usage count for each tag
        
    Returns:
        List of Tag objects (with .count attribute if with_counts=True)
    """
    if isinstance(model_or_queryset, type) and issubclass(model_or_queryset, models.Model):
        # It's a model class
        queryset = model_or_queryset._default_manager.all()
        model = model_or_queryset
    else:
        # It's a queryset
        queryset = model_or_queryset
        model = queryset.model
    
    content_type = ContentType.objects.get_for_model(model)
    
    # Get base queryset of tags
    tags_qs = TaggitTag.objects.filter(
        taggit_taggeditem_items__content_type=content_type
    ).distinct()
    
    # If we have a filtered queryset, we need to filter by object IDs
    if queryset.query.where:
        # Get object IDs from the queryset
        object_ids = list(queryset.values_list('pk', flat=True))
        if not object_ids:
            return []
        
        tags_qs = tags_qs.filter(
            taggit_taggeditem_items__object_id__in=object_ids
        )
    
    if with_counts:
        from django.db.models import Count
        tags_qs = tags_qs.annotate(
            count=Count('taggit_taggeditem_items')
        )
    
    tags = list(tags_qs)
    
    # If with_counts, ensure each tag has a count attribute
    if with_counts:
        for tag in tags:
            if not hasattr(tag, 'count'):
                tag.count = 0
    
    return tags
