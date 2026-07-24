"""
Small tagging helpers for models that cannot host a TaggableManager
(e.g. django_comments.Comment) and shared tag-name normalization.
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from taggit.models import Tag, TaggedItem


def normalize_tag_name(tag_name):
    """Normalize tag name according to project settings."""
    if not tag_name:
        return tag_name
    tag_name = str(tag_name).strip()
    if getattr(settings, 'FORCE_LOWERCASE_TAGS', False):
        tag_name = tag_name.lower()
    return tag_name


def tags_for_object(obj):
    """Return a QuerySet of tags for an object via taggit's GFK."""
    if obj.pk is None:
        return Tag.objects.none()

    content_type = ContentType.objects.get_for_model(obj)
    return Tag.objects.filter(
        taggit_taggeditem_items__content_type=content_type,
        taggit_taggeditem_items__object_id=obj.pk,
    ).distinct()


def add_tag(obj, tag_name):
    """Add a tag to an object via taggit's GFK."""
    if obj.pk is None:
        raise ValueError("Cannot tag an object that hasn't been saved")

    tag_name = normalize_tag_name(tag_name)
    if not tag_name:
        return

    tag, _ = Tag.objects.get_or_create(name=tag_name)
    content_type = ContentType.objects.get_for_model(obj)
    TaggedItem.objects.get_or_create(
        tag=tag,
        content_type=content_type,
        object_id=obj.pk,
    )


def remove_tag(obj, tag_name):
    """Remove a tag from an object via taggit's GFK."""
    if obj.pk is None:
        return

    tag_name = normalize_tag_name(tag_name)
    if not tag_name:
        return

    try:
        tag = Tag.objects.get(name=tag_name)
    except Tag.DoesNotExist:
        return

    content_type = ContentType.objects.get_for_model(obj)
    TaggedItem.objects.filter(
        tag=tag,
        content_type=content_type,
        object_id=obj.pk,
    ).delete()


def filter_queryset_with_all_tags(queryset, tag_names):
    """
    Filter a queryset to objects that have ALL of the specified tags.

    Works via taggit's GFK (TaggedItem). Prefer Model.objects.filter(tags__name=...)
    for models that have a TaggableManager.
    """
    model = queryset.model

    if not tag_names:
        return model._default_manager.none()

    tag_names = [normalize_tag_name(name) for name in tag_names if name]
    if not tag_names:
        return model._default_manager.none()

    tags = Tag.objects.filter(name__in=tag_names)
    if tags.count() != len(set(tag_names)):
        return model._default_manager.none()

    content_type = ContentType.objects.get_for_model(model)
    tagged_items = TaggedItem.objects.filter(
        content_type=content_type,
        tag__in=tags,
    ).values('object_id').annotate(
        tag_count=Count('tag', distinct=True)
    ).filter(tag_count=len(set(tag_names)))

    object_ids = [item['object_id'] for item in tagged_items]
    if object_ids:
        return queryset.filter(pk__in=object_ids)
    return model._default_manager.none()


def tags_used_for_model(model):
    """Return distinct tags used on instances of the given model."""
    content_type = ContentType.objects.get_for_model(model)
    return Tag.objects.filter(
        taggit_taggeditem_items__content_type=content_type
    ).distinct()
