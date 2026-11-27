from decimal import Decimal

from django.test import TestCase

from core.exporters import entity_to_v1, statement_to_v1, value_to_v1
from core.exporters import UnsupportedValue
from core.parsers.v1 import V1CommandParser

GREGORIAN = "http://www.wikidata.org/entity/Q1985727"


def value(content):
    return {"type": "value", "content": content}


def statement(prop, data_type, content, **kwargs):
    return {
        "id": f"Q42${prop}",
        "rank": "normal",
        "property": {"id": prop, "data_type": data_type},
        "value": value(content),
        "qualifiers": [],
        "references": [],
        **kwargs,
    }


def part(prop, data_type, content):
    return {"property": {"id": prop, "data_type": data_type}, "value": value(content)}


ENTITY = {
    "type": "item",
    "id": "Q42",
    "labels": {"en": "Douglas Adams", "de": "Douglas Adams"},
    "descriptions": {"en": "English writer and humorist"},
    "aliases": {"en": ["Douglas Noel Adams", "DNA"]},
    "sitelinks": {"enwiki": {"title": "Douglas Adams", "badges": [], "url": ""}},
    "statements": {
        "P31": [
            statement(
                "P31",
                "wikibase-item",
                "Q5",
                rank="preferred",
                references=[
                    {"hash": "a", "parts": [part("P248", "wikibase-item", "Q36578")]},
                    {
                        "hash": "b",
                        "parts": [
                            part("P854", "url", "https://example.org/?a=1|b=2"),
                            part(
                                "P813",
                                "time",
                                {
                                    "time": "+2024-01-02T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": GREGORIAN,
                                },
                            ),
                        ],
                    },
                ],
            )
        ],
        "P569": [
            statement(
                "P569",
                "time",
                {
                    "time": "+1952-03-11T00:00:00Z",
                    "precision": 11,
                    "calendarmodel": GREGORIAN,
                },
            )
        ],
        "P1477": [
            statement(
                "P1477",
                "monolingualtext",
                {"text": "Douglas Noël Adams", "language": "en"},
                rank="deprecated",
            )
        ],
        "P2048": [
            statement(
                "P2048",
                "quantity",
                {
                    "amount": "+1.96",
                    "unit": "http://www.wikidata.org/entity/Q11573",
                    "lowerBound": "+1.95",
                    "upperBound": "+1.97",
                },
                qualifiers=[part("P585", "time", {
                    "time": "+1990-00-00T00:00:00Z",
                    "precision": 9,
                    "calendarmodel": GREGORIAN,
                })],
            )
        ],
        "P625": [
            statement(
                "P625",
                "globe-coordinate",
                {
                    "latitude": 52.5,
                    "longitude": -1.25,
                    "precision": 0.016666666666667,
                    "globe": "http://www.wikidata.org/entity/Q2",
                },
            )
        ],
        "P4839": [
            statement("P4839", "external-id", 'Entity["Person", "DouglasAdams::gh8qf"]')
        ],
        "P1050": [
            {
                "id": "Q42$somevalue",
                "rank": "normal",
                "property": {"id": "P1050", "data_type": "wikibase-item"},
                "value": {"type": "somevalue"},
                "qualifiers": [],
                "references": [],
            }
        ],
    },
}


class ValueToV1Tests(TestCase):
    def test_entity(self):
        self.assertEqual(value_to_v1(value("Q5"), "wikibase-item"), "Q5")
        self.assertEqual(value_to_v1(value("P31"), "wikibase-property"), "P31")
        self.assertEqual(value_to_v1(value("L1-F2"), "wikibase-form"), "L1-F2")

    def test_somevalue_novalue(self):
        self.assertEqual(value_to_v1({"type": "somevalue"}, "string"), "somevalue")
        self.assertEqual(value_to_v1({"type": "novalue"}, "time"), "novalue")

    def test_strings(self):
        self.assertEqual(value_to_v1(value("abc"), "string"), '"abc"')
        self.assertEqual(value_to_v1(value("a|b"), "external-id"), '"a|b"')
        self.assertEqual(value_to_v1(value("Earth.jpg"), "commonsMedia"), '"Earth.jpg"')
        self.assertEqual(value_to_v1(value('a "b" c'), "string"), '"""a "b" c"""')

    def test_unsupported_strings(self):
        for text in ['"quoted"', 'a """b""" c', "a\tb", "a\nb", "“curly”"]:
            with self.assertRaises(UnsupportedValue):
                value_to_v1(value(text), "string")

    def test_monolingualtext(self):
        content = {"text": "Douglas Adams", "language": "en"}
        self.assertEqual(value_to_v1(value(content), "monolingualtext"), 'en:"Douglas Adams"')
        with self.assertRaises(UnsupportedValue):
            content = {"text": 'a "b" c', "language": "en"}
            value_to_v1(value(content), "monolingualtext")

    def test_time(self):
        content = {"time": "+1952-03-11T00:00:00Z", "precision": 11, "calendarmodel": GREGORIAN}
        self.assertEqual(value_to_v1(value(content), "time"), "+1952-03-11T00:00:00Z/11")
        content["calendarmodel"] = "http://www.wikidata.org/entity/Q1985786"
        self.assertEqual(value_to_v1(value(content), "time"), "+1952-03-11T00:00:00Z/11/J")
        content["calendarmodel"] = "http://www.wikidata.org/entity/Q12345"
        self.assertEqual(value_to_v1(value(content), "time"), "+1952-03-11T00:00:00Z/11/C12345")

    def test_location(self):
        content = {
            "latitude": 52.5,
            "longitude": -1.25,
            "precision": 0.000001,
            "globe": "http://www.wikidata.org/entity/Q2",
        }
        self.assertEqual(value_to_v1(value(content), "globe-coordinate"), "@52.5/-1.25")
        content["precision"] = 0.016666666666667
        self.assertEqual(value_to_v1(value(content), "globe-coordinate"), "@52.5/-1.25/arcmin")
        content["precision"] = 0.001
        content["globe"] = "http://www.wikidata.org/entity/Q405"
        self.assertEqual(value_to_v1(value(content), "globe-coordinate"), "@52.5/-1.25/G405/-3")

    def test_quantity(self):
        self.assertEqual(value_to_v1(value({"amount": "+42", "unit": "1"}), "quantity"), "42")
        self.assertEqual(value_to_v1(value({"amount": "-1.5", "unit": "1"}), "quantity"), "-1.5")
        content = {"amount": "+1.96", "unit": "http://www.wikidata.org/entity/Q11573"}
        self.assertEqual(value_to_v1(value(content), "quantity"), "1.96U11573")
        content.update(lowerBound="+1.95", upperBound="+1.97")
        self.assertEqual(value_to_v1(value(content), "quantity"), "1.96[1.95,1.97]U11573")


class StatementToV1Tests(TestCase):
    def test_rank_qualifiers_and_references(self):
        self.assertEqual(
            statement_to_v1("Q42", ENTITY["statements"]["P31"][0]),
            'Q42|P31|Q5|R+|S248|Q36578|!S854|"https://example.org/?a=1|b=2"'
            "|S813|+2024-01-02T00:00:00Z/11",
        )
        self.assertEqual(
            statement_to_v1("Q42", ENTITY["statements"]["P2048"][0]),
            "Q42|P2048|1.96[1.95,1.97]U11573|P585|+1990-00-00T00:00:00Z/9",
        )
        self.assertEqual(
            statement_to_v1("Q42", ENTITY["statements"]["P1477"][0]),
            'Q42|P1477|en:"Douglas Noël Adams"|R-',
        )


class EntityToV1Tests(TestCase):
    def test_entity(self):
        commands, skipped = entity_to_v1(ENTITY)
        self.assertEqual(skipped, [])
        self.assertEqual(
            commands.splitlines()[:6],
            [
                'Q42|Len|"Douglas Adams"',
                'Q42|Lde|"Douglas Adams"',
                'Q42|Den|"English writer and humorist"',
                'Q42|Aen|"Douglas Noel Adams"|"DNA"',
                'Q42|Senwiki|"Douglas Adams"',
                'Q42|P31|Q5|R+|S248|Q36578|!S854|"https://example.org/?a=1|b=2"'
                "|S813|+2024-01-02T00:00:00Z/11",
            ],
        )
        self.assertIn('Q42|P4839|"""Entity["Person", "DouglasAdams::gh8qf"]"""', commands)
        self.assertIn("Q42|P1050|somevalue", commands)

    def test_skipped(self):
        entity = {
            "id": "Q1",
            "labels": {"en": "a\tb"},
            "statements": {
                "P1": [statement("P1", "monolingualtext", {"text": '"x"', "language": "en"})],
                "P2": [statement("P2", "string", "ok")],
            },
        }
        commands, skipped = entity_to_v1(entity)
        self.assertEqual(commands, 'Q1|P2|"ok"')
        self.assertEqual(skipped, ["Len", "Q42$P1"])

    def test_round_trip(self):
        """
        The commands parse back to the same terms and statements.
        """
        commands, _ = entity_to_v1(ENTITY)
        parsed = [command.json for command in V1CommandParser().parse(commands)]
        self.assertEqual(
            parsed[:5],
            [
                {
                    "action": "add",
                    "what": "label",
                    "item": "Q42",
                    "language": "en",
                    "value": {"type": "string", "value": "Douglas Adams"},
                },
                {
                    "action": "add",
                    "what": "label",
                    "item": "Q42",
                    "language": "de",
                    "value": {"type": "string", "value": "Douglas Adams"},
                },
                {
                    "action": "add",
                    "what": "description",
                    "item": "Q42",
                    "language": "en",
                    "value": {"type": "string", "value": "English writer and humorist"},
                },
                {
                    "action": "add",
                    "what": "alias",
                    "item": "Q42",
                    "language": "en",
                    "value": {"type": "aliases", "value": ["Douglas Noel Adams", "DNA"]},
                },
                {
                    "action": "add",
                    "what": "sitelink",
                    "item": "Q42",
                    "site": "enwiki",
                    "value": {"type": "string", "value": "Douglas Adams"},
                },
            ],
        )
        statements = [s for s in ENTITY["statements"].values() for s in s]
        parsed_statements = parsed[5:]
        self.assertEqual(len(parsed_statements), len(statements))
        for original, command in zip(statements, parsed_statements):
            self.assertEqual(command["property"], original["property"]["id"])
            self.assertEqual(command.get("rank", "normal"), original["rank"])
            self.assertValueEqual(command["value"], original["value"])
            self.assertEqual(len(command.get("qualifiers", [])), len(original["qualifiers"]))
            for qualifier, original_qualifier in zip(
                command.get("qualifiers", []), original["qualifiers"]
            ):
                self.assertValueEqual(qualifier["value"], original_qualifier["value"])
            references = [r for r in command.get("references", []) if r]
            self.assertEqual(len(references), len(original["references"]))
            for reference, original_reference in zip(references, original["references"]):
                self.assertEqual(len(reference), len(original_reference["parts"]))
                for p, original_part in zip(reference, original_reference["parts"]):
                    self.assertEqual(p["property"], original_part["property"]["id"])
                    self.assertValueEqual(p["value"], original_part["value"])

    def assertValueEqual(self, parser_value, api_value):
        if api_value["type"] != "value":
            self.assertEqual(parser_value["type"], api_value["type"])
            return
        parsed = parser_value["value"]
        content = api_value["content"]
        if isinstance(content, dict) and "amount" in content:
            for key in ("amount", "lowerBound", "upperBound"):
                if key in content:
                    self.assertEqual(Decimal(parsed[key]), Decimal(content[key]))
            self.assertTrue(content["unit"].endswith(f"Q{parsed['unit']}"))
        elif isinstance(content, dict) and "latitude" in content:
            for key in ("latitude", "longitude", "globe"):
                self.assertEqual(parsed[key], content[key])
            self.assertAlmostEqual(parsed["precision"], content["precision"])
        else:
            self.assertEqual(parsed, content)
