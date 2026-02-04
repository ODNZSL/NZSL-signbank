"""
Tagging models module.

Exports Tag and TaggedItem from django-taggit for use throughout the codebase.
This hides the taggit dependency behind our own module.

Also includes legacy models for migration history compatibility.
These legacy models are registered with app_label='tagging' so migrations
can find them via apps.get_model('tagging', 'Tag').
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from django.conf import settings

# Import taggit models with aliases first
from taggit.models import Tag as TaggitTag, TaggedItem as TaggitTaggedItem


# Legacy models for migration compatibility
# These MUST be named Tag/TaggedItem for migrations to find them via
# apps.get_model('tagging', 'Tag'). They are registered with app_label='tagging'.
class Tag(models.Model):
    """Legacy Tag model - exists only for migration compatibility."""
    name = models.CharField(
        _('name'),
        max_length=getattr(settings, 'MAX_TAG_LENGTH', 50),
        unique=True,
        db_index=True
    )

    class Meta:
        ordering = ('name',)
        verbose_name = _('tag')
        verbose_name_plural = _('tags')
        app_label = 'tagging'

    def __str__(self):
        return self.name


class TaggedItem(models.Model):
    """Legacy TaggedItem model - exists only for migration compatibility."""
    tag = models.ForeignKey(
        Tag,
        verbose_name=_('tag'),
        related_name='items',
        on_delete=models.CASCADE
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name=_('content type'),
        on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(
        _('object id'),
        db_index=True
    )
    object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('tag', 'content_type', 'object_id'),)
        verbose_name = _('tagged item')
        verbose_name_plural = _('tagged items')
        app_label = 'tagging'

    def __str__(self):
        return '%s [%s]' % (str(self.object), str(self.tag))


# Override Tag and TaggedItem to export taggit's models for runtime use
# This shadows the legacy models for direct imports, but migrations using
# apps.get_model('tagging', 'Tag') will still find the legacy Tag class via
# Django's app registry (which uses the class definition, not the reassigned name)
Tag = TaggitTag  # noqa: F811
TaggedItem = TaggitTaggedItem  # noqa: F811

__all__ = ['Tag', 'TaggedItem']
