"""
Template tags for tagging - compatible with django-tagging's tagging_tags API.

Provides the same template tag interface but backed by signbank.tagging.adapter.
"""
from django import template
from django.apps import apps
from django.utils.translation import gettext as _

from signbank.tagging.adapter import filter_queryset_with_all_tags, tags_usage_for_model
from signbank.tagging.adapter import tags_for_object as adapter_tags_for_object

register = template.Library()


class TagsForObjectNode(template.Node):
    def __init__(self, obj, context_var):
        self.obj = template.Variable(obj)
        self.context_var = context_var

    def render(self, context):
        try:
            obj = self.obj.resolve(context)
            context[self.context_var] = adapter_tags_for_object(obj)
        except template.VariableDoesNotExist:
            context[self.context_var] = []
        return ''


class TagsForModelNode(template.Node):
    def __init__(self, model, context_var, counts):
        self.model = model
        self.context_var = context_var
        self.counts = counts

    def render(self, context):
        try:
            model = apps.get_model(*self.model.split('.'))
            if model is None:
                raise template.TemplateSyntaxError(
                    _('tags_for_model tag was given an invalid model: %s') % self.model)
            context[self.context_var] = tags_usage_for_model(model, with_counts=self.counts)
        except (LookupError, ValueError):
            context[self.context_var] = []
        return ''


class TaggedObjectsNode(template.Node):
    def __init__(self, tag, model, context_var):
        self.tag = template.Variable(tag)
        self.model = model
        self.context_var = context_var

    def render(self, context):
        try:
            model = apps.get_model(*self.model.split('.'))
            if model is None:
                raise template.TemplateSyntaxError(
                    _('tagged_objects tag was given an invalid model: %s') % self.model)
            tag = self.tag.resolve(context)
            tag_name = tag.name if hasattr(tag, 'name') else str(tag)
            context[self.context_var] = filter_queryset_with_all_tags(model, [tag_name])
        except (template.VariableDoesNotExist, LookupError, ValueError):
            context[self.context_var] = []
        return ''


@register.tag
def tags_for_object(parser, token):
    """
    Retrieves a list of Tag objects associated with an object and stores them in a context variable.

    Usage::
        {% tags_for_object [object] as [varname] %}

    Example::
        {% tags_for_object foo_object as tag_list %}
    """
    bits = token.contents.split()
    if len(bits) != 4:
        raise template.TemplateSyntaxError(
            _('%s tag requires exactly three arguments') % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError(
            _("second argument to %s tag must be 'as'") % bits[0])
    return TagsForObjectNode(bits[1], bits[3])


@register.tag
def tags_for_model(parser, token):
    """
    Retrieves a list of Tag objects associated with a given model and stores them in a context variable.

    Usage::
        {% tags_for_model [model] as [varname] %}
        {% tags_for_model [model] as [varname] with counts %}

    The model is specified in [appname].[modelname] format.
    """
    bits = token.contents.split()
    len_bits = len(bits)
    if len_bits not in (4, 6):
        raise template.TemplateSyntaxError(
            _('%s tag requires either three or five arguments') % bits[0])
    if bits[2] != 'as':
        raise template.TemplateSyntaxError(
            _("second argument to %s tag must be 'as'") % bits[0])
    counts = False
    if len_bits == 6:
        if bits[4] != 'with':
            raise template.TemplateSyntaxError(
                _("if given, fourth argument to %s tag must be 'with'") % bits[0])
        if bits[5] != 'counts':
            raise template.TemplateSyntaxError(
                _("if given, fifth argument to %s tag must be 'counts'") % bits[0])
        counts = True
    return TagsForModelNode(bits[1], bits[3], counts)


@register.tag
def tagged_objects(parser, token):
    """
    Retrieves a list of instances of a given model which are tagged with a given tag.

    Usage::
        {% tagged_objects [tag] in [model] as [varname] %}

    The model is specified in [appname].[modelname] format.

    Example::
        {% tagged_objects comedy_tag in tv.Show as comedies %}
    """
    bits = token.contents.split()
    if len(bits) != 5:
        raise template.TemplateSyntaxError(
            _('%s tag requires exactly four arguments') % bits[0])
    if bits[2] != 'in':
        raise template.TemplateSyntaxError(
            _("second argument to %s tag must be 'in'") % bits[0])
    if bits[4] != 'as':
        raise template.TemplateSyntaxError(
            _("fourth argument to %s tag must be 'as'") % bits[0])
    return TaggedObjectsNode(bits[1], bits[3], bits[5])
