"""
Converts entities from the Wikibase REST API into V1 commands,
so that they can be edited as text and submitted as a new batch.
"""

import math
import re

GREGORIAN = "http://www.wikidata.org/entity/Q1985727"
JULIAN = "http://www.wikidata.org/entity/Q1985786"
EARTH = "http://www.wikidata.org/entity/Q2"

# Precisions supported by the V1 location syntax, see `parse_value_location`
LOCATION_PRECISIONS = {
    "arcsec": 0.000277777777778,
    "arcsec10": 0.000027777777778,
    "arcsec100": 0.000002777777778,
    "arcsec1000": 0.000000277777778,
    "arcmin": 0.016666666666667,
    "-5": 0.00001,
    "-4": 0.0001,
    "-3": 0.001,
    "-2": 0.01,
    "-1": 0.1,
    "0": 1,
    "1": 10,
}

RANKS = {
    "preferred": "R+",
    "deprecated": "R-",
}


class UnsupportedValue(Exception):
    pass


def _qid_from_iri(iri):
    match = re.search(r"(Q\d+)$", iri or "")
    if not match:
        raise UnsupportedValue(iri)
    return match.group(1)


def _string(text, allow_triple_quotes=True):
    """
    Quotes a text for the V1 syntax.

    A text containing quotes needs triple quotes, which are not supported for
    monolingual texts. Tabs and line breaks cannot be represented at all, and
    typographic quotes would be replaced by the parser.
    """
    if any(c in text for c in "\t\n“”"):
        raise UnsupportedValue(text)
    if '"' not in text:
        return f'"{text}"'
    if allow_triple_quotes and '"""' not in text and text[0] != '"' and text[-1] != '"':
        return f'"""{text}"""'
    raise UnsupportedValue(text)


def _time(content):
    value = f"{content['time']}/{content['precision']}"
    calendar = content.get("calendarmodel", GREGORIAN)
    if calendar == JULIAN:
        value += "/J"
    elif calendar != GREGORIAN:
        value += f"/C{_qid_from_iri(calendar)[1:]}"
    return value


def _location(content):
    value = f"@{content['latitude']}/{content['longitude']}"
    globe = content.get("globe", EARTH)
    if globe != EARTH:
        value += f"/G{_qid_from_iri(globe)[1:]}"
    precision = content.get("precision")
    for name, size in LOCATION_PRECISIONS.items():
        if precision and math.isclose(precision, size, rel_tol=1e-6):
            value += f"/{name}"
            break
    return value


def _amount(amount):
    return amount[1:] if amount.startswith("+") else amount


def _quantity(content):
    value = _amount(content["amount"])
    if "lowerBound" in content and "upperBound" in content:
        lower = _amount(content["lowerBound"])
        upper = _amount(content["upperBound"])
        value += f"[{lower},{upper}]"
    unit = content.get("unit", "1")
    if unit != "1":
        value += f"U{_qid_from_iri(unit)[1:]}"
    return value


def value_to_v1(value, data_type):
    """
    Converts a REST API value into the V1 syntax.

    Raises `UnsupportedValue` if it cannot be represented.
    """
    if value["type"] in ("somevalue", "novalue"):
        return value["type"]
    content = value["content"]
    if data_type in (
        "wikibase-item",
        "wikibase-property",
        "wikibase-lexeme",
        "wikibase-form",
        "wikibase-sense",
    ):
        return content
    if data_type == "monolingualtext":
        return f"{content['language']}:{_string(content['text'], allow_triple_quotes=False)}"
    if data_type == "time":
        return _time(content)
    if data_type == "globe-coordinate":
        return _location(content)
    if data_type == "quantity":
        return _quantity(content)
    if isinstance(content, str):
        return _string(content)
    raise UnsupportedValue(content)


def statement_to_v1(entity_id, statement):
    """
    Converts a REST API statement, with rank, qualifiers and references,
    into a V1 command.
    """
    prop = statement["property"]
    parts = [entity_id, prop["id"], value_to_v1(statement["value"], prop.get("data_type"))]
    rank = RANKS.get(statement.get("rank"))
    if rank:
        parts.append(rank)
    for qualifier in statement.get("qualifiers", []):
        qprop = qualifier["property"]
        parts.append(qprop["id"])
        parts.append(value_to_v1(qualifier["value"], qprop.get("data_type")))
    for i, reference in enumerate(statement.get("references", [])):
        for j, part in enumerate(reference.get("parts", [])):
            rprop = part["property"]
            # "!S" starts a new reference block
            prefix = "!S" if i > 0 and j == 0 else "S"
            parts.append(prefix + rprop["id"][1:])
            parts.append(value_to_v1(part["value"], rprop.get("data_type")))
    return "|".join(parts)


def entity_to_v1(entity):
    """
    Converts a REST API entity into V1 commands: labels, descriptions,
    aliases, sitelinks and statements.

    Returns the commands and a list of what was skipped because it
    cannot be represented in V1 (term names or statement ids).
    """
    entity_id = entity["id"]
    commands = []
    skipped = []

    def add_term(name, command):
        try:
            commands.append(command())
        except UnsupportedValue:
            skipped.append(name)

    for language, label in entity.get("labels", {}).items():
        add_term(f"L{language}", lambda: f"{entity_id}|L{language}|{_string(label)}")
    for language, description in entity.get("descriptions", {}).items():
        add_term(f"D{language}", lambda: f"{entity_id}|D{language}|{_string(description)}")
    for language, aliases in entity.get("aliases", {}).items():
        add_term(
            f"A{language}",
            lambda: "|".join([entity_id, f"A{language}", *map(_string, aliases)]),
        )
    for site, sitelink in entity.get("sitelinks", {}).items():
        add_term(f"S{site}", lambda: f"{entity_id}|S{site}|{_string(sitelink['title'])}")

    for statements in entity.get("statements", {}).values():
        for statement in statements:
            try:
                commands.append(statement_to_v1(entity_id, statement))
            except UnsupportedValue:
                skipped.append(statement.get("id", entity_id))

    return "\n".join(commands), skipped
