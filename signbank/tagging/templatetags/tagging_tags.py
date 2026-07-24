"""
Template tags for tagging objects that do not have a TaggableManager
(primarily django_comments.Comment).

Gloss / GlossRelation templates should use obj.tags.all instead.
"""
from django import template

from signbank.tagging.utils import tags_for_object as get_tags_for_object

register = template.Library()


class TagsForObjectNode(template.Node):
    def __init__(self, obj, context_var):
        self.obj = template.Variable(obj)
        self.context_var = context_var

    def render(self, context):
        try:
            obj = self.obj.resolve(context)
            context[self.context_var] = get_tags_for_object(obj)
        except template.VariableDoesNotExist:
            context[self.context_var] = []
        return ''


@register.tag
def tags_for_object(parser, token):
    """
    Retrieves Tag objects associated with an object and stores them in a context variable.

    Usage::
        {% tags_for_object [object] as [varname] %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise template.TemplateSyntaxError(
            '%s tag requires exactly three arguments' % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError(
            "second argument to %s tag must be 'as'" % bits[0])
    return TagsForObjectNode(bits[1], bits[3])
