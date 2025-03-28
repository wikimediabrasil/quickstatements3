from django.test import TestCase

from core.parsers.csv import CSVCommandParser


class TestCSVParser(TestCase):
    def test_parse_header(self):
        parser = CSVCommandParser()
        self.assertTrue(parser.check_header(["qid", "P31", "-P31"]))
        self.assertTrue(parser.check_header(["qid", "Lpt"]))
        self.assertTrue(parser.check_header(["qid", "Lpt", "#"]))
        self.assertTrue(parser.check_header(["qid", "-Lpt", "#"]))
        self.assertTrue(parser.check_header(["qid", "Dpt"]))
        self.assertTrue(parser.check_header(["qid", "Dpt", "#"]))
        self.assertTrue(parser.check_header(["qid", "-Dpt", "#"]))
        self.assertTrue(parser.check_header(["qid", "Apt"]))
        self.assertTrue(parser.check_header(["qid", "Apt", "#"]))
        self.assertTrue(parser.check_header(["qid", "-Apt", "#"]))
        self.assertTrue(parser.check_header(["qid", "Swiki"]))
        self.assertTrue(parser.check_header(["qid", "Swiki", "#"]))
        self.assertTrue(parser.check_header(["qid", "-Swiki", "#"]))
        self.assertTrue(parser.check_header(["qid", "P31", "Len", "Den", "P18"]))
        self.assertTrue(
            parser.check_header(
                [
                    "qid",
                    "Len",
                    "Den",
                    "Aen",
                    "P31",
                    "-P31",
                    "P21",
                    "P735",
                    "qal1545",
                    "S248",
                    "s214",
                    "S143",
                    "Senwiki",
                ]
            )
        )

    def test_parse_header_no_qid(self):
        parser = CSVCommandParser()
        with self.assertRaises(Exception) as context:
            parser.check_header(["", "qid", "P31", "-P31"])
        self.assertEqual(
            context.exception.message, "CSV header first element must be qid"
        )

    def test_parse_header_comment_before_property(self):
        parser = CSVCommandParser()
        with self.assertRaises(Exception) as context:
            parser.check_header(["qid", "#", "P31"])
        self.assertEqual(
            context.exception.message, "A valid property must precede a comment"
        )

    def test_parse_header_qal_before_property(self):
        parser = CSVCommandParser()
        with self.assertRaises(Exception) as context:
            parser.check_header(["qid", "qal", "P31"])
        self.assertEqual(
            context.exception.message, "A valid property must precede a qualifier"
        )

    def test_parse_header_source_before_property(self):
        parser = CSVCommandParser()
        with self.assertRaises(Exception) as context:
            parser.check_header(["qid", "S1234", "P31"])
        self.assertEqual(
            context.exception.message, "A valid property must precede a source"
        )
        with self.assertRaises(Exception) as context:
            parser.check_header(["qid", "s1234", "P31"])
        self.assertEqual(
            context.exception.message, "A valid property must precede a source"
        )

    def test_parse_item(self):
        parser = CSVCommandParser()

        # ADD / REMOVE
        self.assertEqual(
            parser.parse_line(["Q4115189", "Q5", "Q5"], ["qid", "P31", "-P31"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P31",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
                {
                    "action": "remove",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P31",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
            ],
        )

        # ITEM
        self.assertEqual(
            parser.parse_line(["Q4115189", "Q5"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P369",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
            ],
        )

        # SOMEVALUE
        self.assertEqual(
            parser.parse_line(["Q4115189", "somevalue"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P369",
                    "value": {"type": "somevalue", "value": "somevalue"},
                    "what": "statement",
                },
            ],
        )

        # NOVALUE
        self.assertEqual(
            parser.parse_line(["Q4115189", "novalue"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P369",
                    "value": {"type": "novalue", "value": "novalue"},
                    "what": "statement",
                },
            ],
        )

        # LEXEME
        self.assertEqual(
            parser.parse_line(["L123", "Q5"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "L123", "type": "lexeme"},
                    "property": "P369",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["L123-S1", "Q5"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "L123-S1", "type": "sense"},
                    "property": "P369",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["L123-F1", "Q5"], ["qid", "P369"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "L123-F1", "type": "form"},
                    "property": "P369",
                    "value": {"type": "wikibase-entityid", "value": "Q5"},
                    "what": "statement",
                },
            ],
        )

    def test_parse_references(self):
        parser = CSVCommandParser()
        parsed_line = parser.parse_line(
            [
                "Q22124656",
                "Q6581097",
                "comment to claim adding edit",
                "Q24731821",
                "+2017-10-04T00:00:00Z/11",
            ],
            ["qid", "P21", "#", "S143", "s813"],
        )

        desired_result = [
            {
                "action": "add",
                "entity": {"id": "Q22124656", "type": "item"},
                "property": "P21",
                "value": {"type": "wikibase-entityid", "value": "Q6581097"},
                "what": "statement",
                "summary": "comment to claim adding edit",
                "references": [
                    [
                        {
                            "property": "P143",
                            "value": {
                                "type": "wikibase-entityid",
                                "value": "Q24731821",
                            },
                        },
                        {
                            "property": "P813",
                            "value": {
                                "type": "time",
                                "value": {
                                    "time": "+2017-10-04T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                            },
                        },
                    ],
                ],
            }
        ]

        self.assertEqual(parsed_line, desired_result)

    def test_parse_qualifiers(self):
        parser = CSVCommandParser()
        parsed_line = parser.parse_line(
            ["Q22124656", "Q6581097", "comment to claim adding edit", "1"],
            ["qid", "P21", "#", "qal1545"],
        )

        desired_result = [
            {
                "action": "add",
                "entity": {"id": "Q22124656", "type": "item"},
                "property": "P21",
                "value": {"type": "wikibase-entityid", "value": "Q6581097"},
                "what": "statement",
                "summary": "comment to claim adding edit",
                "qualifiers": [
                    {
                        "property": "P1545",
                        "value": {
                            "type": "quantity",
                            "value": {"amount": "+1", "unit": "1"},
                        },
                    },
                ],
            }
        ]

        self.assertEqual(parsed_line, desired_result)

    def test_parse_multiple_item(self):
        parser = CSVCommandParser()

        parsed_line = parser.parse_line(
            [
                "",
                "Q3305213",
                "Mona Lisa",
                "oil painting by Leonardo da Vinci",
                '"""Mona Lisa - the Louvre.jpg"""',
            ],
            ["qid", "P31", "Len", "Den", "P18"],
        )

        desired_result = [
            {"action": "create", "type": "item"},
            {
                "action": "add",
                "entity": {"id": "LAST", "type": "item"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q3305213"},
                "what": "statement",
            },
            {
                "action": "add",
                "item": "LAST",
                "value": {"type": "string", "value": "Mona Lisa"},
                "what": "label",
                "language": "en",
            },
            {
                "action": "add",
                "item": "LAST",
                "value": {
                    "type": "string",
                    "value": "oil painting by Leonardo da Vinci",
                },
                "what": "description",
                "language": "en",
            },
            {
                "action": "add",
                "entity": {"id": "LAST", "type": "item"},
                "property": "P18",
                "value": {"type": "string", "value": "Mona Lisa - the Louvre.jpg"},
                "what": "statement",
            },
        ]

        # ADD / REMOVE
        self.assertEqual(parsed_line, desired_result)

    def test_parse_coordinates(self):
        parser = CSVCommandParser()

        self.assertEqual(
            parser.parse_line(["Q4115189", "@43.26193/10.92708"], ["qid", "P625"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P625",
                    "value": {
                        "type": "globecoordinate",
                        "value": {
                            "globe": "http://www.wikidata.org/entity/Q2",
                            "latitude": 43.26193,
                            "longitude": 10.92708,
                            "precision": 0.000001,
                        },
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_datetime(self):
        parser = CSVCommandParser()
        self.assertEqual(
            parser.parse_line(["Q4115189", "+1856-01-01T00:00:00Z/9"], ["qid", "P577"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P577",
                    "value": {
                        "type": "time",
                        "value": {
                            "time": "+1856-01-01T00:00:00Z",
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_external_identifier(self):
        parser = CSVCommandParser()
        self.assertEqual(
            parser.parse_line(["Q4115189", '"""Sandbox"""'], ["qid", "P370"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "Sandbox",
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(
                ["Q4115189", '"""Patterns, Predictors, and Outcome"""'], ["qid", "P370"]
            ),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "Patterns, Predictors, and Outcome",
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_url(self):
        parser = CSVCommandParser()
        self.assertEqual(
            parser.parse_line(
                ["Q4115189", '"""https://wiki.com.br"""'], ["qid", "P370"]
            ),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "https://wiki.com.br",
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", '"""http://wiki.com"""'], ["qid", "P370"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "http://wiki.com",
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_commons(self):
        parser = CSVCommandParser()
        self.assertEqual(
            parser.parse_line(
                ["Q4115189", '"""Frans Breydel - A merry company.jpg"""'],
                ["qid", "P370"],
            ),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "Frans Breydel - A merry company.jpg",
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(
                [
                    "Q4115189",
                    '"""\'Girl Reading\' by Mary Colman Wheeler, El Paso Museum of Art.JPG"""',
                ],
                ["qid", "P370"],
            ),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P370",
                    "value": {
                        "type": "string",
                        "value": "'Girl Reading' by Mary Colman Wheeler, El Paso Museum of Art.JPG",
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_quantity(self):
        parser = CSVCommandParser()

        self.assertEqual(
            parser.parse_line(["Q4115189", "10"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {"amount": "+10", "unit": "1"},
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "+20"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {"amount": "+20", "unit": "1"},
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "+3.1415926"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {"amount": "+3.1415926", "unit": "1"},
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "-40"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {"amount": "-40", "unit": "1"},
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "-80~1.5"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {
                            "amount": "-80",
                            "lowerBound": "-81.5",
                            "upperBound": "-78.5",
                            "unit": "1",
                        },
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "2.2~0.3"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {
                            "amount": "+2.2",
                            "lowerBound": "+1.9",
                            "upperBound": "+2.5",
                            "unit": "1",
                        },
                    },
                    "what": "statement",
                },
            ],
        )

        self.assertEqual(
            parser.parse_line(["Q4115189", "+1.2~0.3"], ["qid", "P1114"]),
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "property": "P1114",
                    "value": {
                        "type": "quantity",
                        "value": {
                            "amount": "+1.2",
                            "lowerBound": "+0.9",
                            "upperBound": "+1.5",
                            "unit": "1",
                        },
                    },
                    "what": "statement",
                },
            ],
        )

    def test_parse_label(self):
        parser = CSVCommandParser()
        result = parser.parse_line(["Q4115189", "Regina Phalange"], ["qid", "Lpt-br"])
        self.assertEqual(
            result,
            [
                {
                    "action": "add",
                    "item": "Q4115189",
                    "value": {"type": "string", "value": "Regina Phalange"},
                    "what": "label",
                    "language": "pt-br",
                },
            ],
        )

    def test_parse_description(self):
        parser = CSVCommandParser()
        result = parser.parse_line(["Q4115189", "Ma maison"], ["qid", "Dmul"])
        self.assertEqual(
            result,
            [
                {
                    "action": "add",
                    "item": "Q4115189",
                    "value": {"type": "string", "value": "Ma maison"},
                    "what": "description",
                    "language": "mul",
                },
            ],
        )

    def test_parse_alias(self):
        parser = CSVCommandParser()
        result = parser.parse_line(
            ["Q4115189", "Chacara Santo Antonio"], ["qid", "Apt"]
        )
        self.assertEqual(
            result,
            [
                {
                    "action": "add",
                    "item": "Q4115189",
                    "value": {"type": "aliases", "value": ["Chacara Santo Antonio"]},
                    "what": "alias",
                    "language": "pt",
                },
            ],
        )

    def test_parse_sitelink(self):
        parser = CSVCommandParser()
        result = parser.parse_line(["Q4115189", "wiki.com.br"], ["qid", "Swiki"])
        self.assertEqual(
            result,
            [
                {
                    "action": "add",
                    "item": "Q4115189",
                    "value": {"type": "string", "value": "wiki.com.br"},
                    "what": "sitelink",
                    "site": "wiki",
                },
            ],
        )

    def test_parse_monolingualtext(self):
        parser = CSVCommandParser()
        result = parser.parse_line(
            ["Q4115189", 'en:"Thats an english, text"'], ["qid", "P31"]
        )
        self.assertEqual(
            result,
            [
                {
                    "action": "add",
                    "entity": {"id": "Q4115189", "type": "item"},
                    "value": {
                        "type": "monolingualtext",
                        "value": {"language": "en", "text": "Thats an english, text"},
                    },
                    "what": "statement",
                    "property": "P31",
                },
            ],
        )

    def test_create(self):
        parser = CSVCommandParser()
        result = parser.parse_line(
            ["", "Regina Phalange", "fictional character", "Q95074"],
            ["qid", "Len", "Den", "P31"],
        )
        self.assertEqual(
            result,
            [
                {"action": "create", "type": "item"},
                {
                    "action": "add",
                    "what": "label",
                    "item": "LAST",
                    "language": "en",
                    "value": {"type": "string", "value": "Regina Phalange"},
                },
                {
                    "action": "add",
                    "what": "description",
                    "item": "LAST",
                    "language": "en",
                    "value": {"type": "string", "value": "fictional character"},
                },
                {
                    "action": "add",
                    "what": "statement",
                    "entity": {"type": "item", "id": "LAST"},
                    "property": "P31",
                    "value": {"type": "wikibase-entityid", "value": "Q95074"},
                },
            ],
        )
