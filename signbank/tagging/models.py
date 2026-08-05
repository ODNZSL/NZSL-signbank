from taggit.models import Tag as TaggitTag
from taggit.models import TaggedItem

__all__ = ['Tag', 'TaggedItem']


class Tag(TaggitTag):
    """Project Tag model with the same default ordering as legacy django-tagging."""

    class Meta:
        proxy = True
        ordering = ('name',)
