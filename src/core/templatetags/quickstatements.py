from django import template

from core.models import Wikibase

register = template.Library()


@register.simple_tag
def has_multiple_wikibases():
    return Wikibase.objects.all().count() > 1
