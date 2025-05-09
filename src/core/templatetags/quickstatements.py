from django import template

from core.models import Wikibase, Label

register = template.Library()


@register.simple_tag
def has_multiple_wikibases():
    return Wikibase.objects.all().count() > 1


@register.filter
def label_display(entity_id, user):
    # FIXME: Preferences need to be moved to core module, so that
    # we can properly catch the RelatedObjectDoesNotExist
    # exception
    preferences = getattr(user, "preferences", None)
    lang = preferences and preferences.language

    label = lang and Label.objects.filter(entity_id=entity_id, language=lang).first()

    if not label:
        label = Label.objects.filter(entity_id=entity_id, language="en").first()

    return label and label.value
