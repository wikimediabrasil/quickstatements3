import math
from decimal import Decimal
import logging
import re

from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import pgettext

from core.models import Wikibase

register = template.Library()
logger = logging.getLogger(__name__)


def render_entity_label(entity_id):
    return (
        f'<span class="wikibase-label" data-entity-id="{entity_id}">{entity_id}</span>'
    )


def render_entity_datavalue(command, value):
    label = render_entity_label(value)
    link = f'<a href="{command.batch.wikibase.url}/entity/{value}">[{value}]</a>'
    return f"{label} {link}"


def render_time_datavalue(command, value):
    pattern = (
        r"(?P<sign>[+-])"
        r"(?P<year>\d+)-"
        r"(?P<month>\d{2})-"
        r"(?P<day>\d{2})T"
        r"(?P<hour>\d{2}):"
        r"(?P<minute>\d{2}):"
        r"(?P<second>\d{2})Z?"
    )
    timestamp = value.get("time")
    precision = value.get("precision")
    m = re.match(pattern, timestamp)
    year = int(m.group("year"))
    if m.group("sign") == "-":
        year = -year
    month = int(m.group("month"))
    day = int(m.group("day"))
    hour = int(m.group("hour"))
    minute = int(m.group("minute"))
    second = int(m.group("second"))

    return {
        14: f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}",
        13: f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
        12: f"{year:04d}-{month:02d}-{day:02d} {hour:02d}",
        11: f"{year:04d}-{month:02d}-{day:02d}",
        10: f"{year}-{month:02d}",
    }.get(precision, f"{year}")


def render_quantity_datavalue(command, value):
    amount = Decimal(value.get("amount") or 0)
    unit = value.get("unit")
    prefixed_unit = unit and unit != "1" and f"Q{unit}" or ""

    return (
        amount
        if not prefixed_unit
        else f"{amount} {render_entity_label(prefixed_unit)}"
    )


def render_globe_datavalue(command, value):
    globe = value.get("globe")

    is_earth = globe == "http://www.wikidata.org/entity/Q2"

    def calculate_degree_minute_seconds(value):
        value = abs(value)
        degrees = int(value)
        minutes_full = (value - degrees) * 60
        minutes = int(minutes_full)
        seconds = round((minutes_full - minutes) * 60)
        return f"{degrees}°{minutes}'{seconds}\""

    lat = value.get("latitude")
    lon = value.get("longitude")

    lat_direction = "N" if lat >= 0 else "S"
    lon_direction = "E" if lon >= 0 else "W"

    lat_dms = calculate_degree_minute_seconds(lat)
    lon_dms = calculate_degree_minute_seconds(lon)

    coordinates = f"{lat_dms}{lat_direction}, {lon_dms}{lon_direction}"
    if not is_earth:
        return f"{coordinates} {render_entity_datavalue(command, globe)}"

    precision = value.get("precision") or None
    level = precision and abs(int(math.floor(math.log10(abs(precision)))) or 5)

    return (
        f'<a href="https://maps.wikimedia.org/#{level}/{lat}/{lon}">{coordinates}</a>'
    )


def render_somevalue_datavalue(command, value):
    return pgettext("batch-command-somevalue", "(Unknown Value)")


def render_novalue_datavalue(command, value):
    return pgettext("batch-command-novalue", "(No Value)")


def render_default_datavalue(command, value):
    return str(value)


@register.simple_tag
def has_multiple_wikibases():
    return Wikibase.objects.all().count() > 1


@register.simple_tag
def label_display(entity_id):
    return mark_safe(render_entity_label(entity_id))


@register.filter
def language_preference(user):
    # FIXME: Preferences need to be moved to core module, so that
    # we can properly catch the RelatedObjectDoesNotExist
    # exception
    preferences = getattr(user, "preferences", None)
    return preferences and preferences.language or "en"


@register.simple_tag
def command_operation_display(command):
    action_display = command.get_action_display()
    text = (
        command.get_operation_display().upper() if command.operation else action_display
    )
    action_class = f"action_{action_display.lower()}"
    return mark_safe(f'<span class="action {action_class}">{text}</span>')


@register.simple_tag
def datavalue_display(command, datavalue):
    logger.info(f"datatype: {datavalue['type']}")
    render_action = {
        "wikibase-entityid": render_entity_datavalue,
        "time": render_time_datavalue,
        "quantity": render_quantity_datavalue,
        # Seems like we have both forms in the database
        "globecoordinate": render_globe_datavalue,
        "globe-coordinate": render_globe_datavalue,
        "somevalue": render_somevalue_datavalue,
        "novalue": render_novalue_datavalue,
    }.get(datavalue["type"], render_default_datavalue)

    return mark_safe(render_action(command, datavalue["value"]))


@register.simple_tag
def entity_display(command, entity_id):
    return mark_safe(render_entity_datavalue(command, entity_id))
