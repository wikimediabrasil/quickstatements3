from django import template
from django.utils.safestring import mark_safe

from core.models import Wikibase

register = template.Library()


@register.simple_tag
def has_multiple_wikibases():
    return Wikibase.objects.all().count() > 1


@register.simple_tag(takes_context=True)
def label_display(context, entity_id):
    return mark_safe(
        f'<span class="wikibase-label" data-entity-id="{entity_id}">{entity_id}</span>'
    )


@register.filter
def language_preference(user):
    # FIXME: Preferences need to be moved to core module, so that
    # we can properly catch the RelatedObjectDoesNotExist
    # exception
    preferences = getattr(user, "preferences", None)
    return preferences and preferences.language or "en"
