from django import template

from core.models import Wikibase

register = template.Library()


@register.simple_tag
def has_multiple_wikibases():
    return Wikibase.objects.all().count() > 1


@register.filter
def get(dictionary, key):
    if type(key) is not str or not type(dictionary) is dict:
        return ""
    return dictionary.get(key, "")