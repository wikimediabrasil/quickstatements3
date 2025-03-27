from django.test import TestCase

from core.parsers.v1 import V1CommandParser


class TestV1ParserCommand(TestCase):
    def test_v1_correct_create_command(self):
        parser = V1CommandParser()
        data = parser.parse_command("CREATE")
        self.assertEqual(data, {"action": "create", "type": "item"})
        data = parser.parse_command("CREATE ")
        self.assertEqual(data, {"action": "create", "type": "item"})
        data = parser.parse_command(" CREATE ")
        self.assertEqual(data, {"action": "create", "type": "item"})

    def test_v1_bad_create_command(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("CREATE\tQ123\t")
            self.assertEqual(
                context.exception.message, "CREATE command can have only 1 column"
            )

    def test_v1_correct_merge_command(self):
        parser = V1CommandParser()
        data = parser.parse_command("MERGE\tQ2\tQ1")
        self.assertEqual(
            data, {"action": "merge", "type": "item", "item1": "Q1", "item2": "Q2"}
        )
        data = parser.parse_command("MERGE \tQ1 \tQ2 ")
        self.assertEqual(
            data, {"action": "merge", "type": "item", "item1": "Q1", "item2": "Q2"}
        )

    def test_v1_bad_merge_command(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("MERGE")
            self.assertEqual(context.exception.message, "MERGE command must have 3 columns")
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("MERGE\tQ1")
            self.assertEqual(context.exception.message, "MERGE command must have 3 columns")
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("MERGE\tQ1\t")
            self.assertEqual(context.exception.message, "MERGE command must have 3 columns")
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("MERGE\tQ1\tQ2\tQ3")
            self.assertEqual(context.exception.message, "MERGE command must have 3 columns")

    def test_v1_remove_item(self):
        parser = V1CommandParser()
        data = parser.parse_command("-Q1234\tP2\tQ1")
        self.assertEqual(
            data,
            {
                "action": "remove",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "what": "statement",
            },
        )

    def test_v1_create_property(self):
        parser = V1CommandParser()
        for datatype in parser.CREATE_PROPERTY_ALLOWED_DATATYPES:
            data = parser.parse_command(f"CREATE_PROPERTY\t{datatype}")
            self.assertEqual(
                data,
                {"action": "create", "type": "property", "data": datatype},
            )

    def test_v1_bad_create_property(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("CREATE_PROPERTY")
            self.assertEqual(
                context.exception.message, "CREATE PROPERTY command must have 2 columns"
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("CREATE_PROPERTY\tP1\t12")
            self.assertEqual(
                context.exception.message, "CREATE PROPERTY command must have 2 columns"
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("CREATE_PROPERTY\tmy_datatype")
            self.assertEqual(
                context.exception.message,
                "CREATE PROPERTY datatype allowed values: ['commonsMedia', 'globe-coordinate', 'wikibase-item', 'wikibase-property', 'string', 'monolingualtext', 'external-id', 'quantity', 'time', 'url', 'math', 'geo-shape', 'musical-notation', 'tabular-data', 'wikibase-lexeme', 'wikibase-form', 'wikibase-sense']",
            )

    def test_v1_remove_statement_by_id(self):
        parser = V1CommandParser()
        data = parser.parse_command(
            "-STATEMENT\tQ4115189$0d52b2b4-4fa4-3bfa-8eda-cfe87ea23c34"
        )
        self.assertEqual(
            data,
            {
                "action": "remove",
                "entity": {"id": "Q4115189"},
                "id": "Q4115189$0d52b2b4-4fa4-3bfa-8eda-cfe87ea23c34",
                "what": "statement",
            },
        )

    def test_v1_bad_remove_statement_by_id(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("-STATEMENT")
            self.assertEqual(
                context.exception.message,
                "remove statement by ID command must have 2 columns",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("-STATEMENT\tP1\t12")
            self.assertEqual(
                context.exception.message,
                "remove statement by ID command must have 2 columns",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("-STATEMENT\tQ1")
            self.assertEqual(
                context.exception.message,
                "ITEM ID format in REMOVE STATEMENT must be Q1234$UUID",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("STATEMENT\tQ1234$abcdefg-huijk")
            self.assertEqual(
                context.exception.message,
                "STATEMENT must contain at least entity, property and value",
            )

    def test_v1_remove_quantity(self):
        parser = V1CommandParser()
        data = parser.parse_command("-Q1234\tP1\t12")
        self.assertEqual(
            data,
            {
                "action": "remove",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"type": "quantity", "value": {"amount": "+12", "unit": "1"}},
                "what": "statement",
            },
        )

        data = parser.parse_command("-Q1234\tP3\t12U11573")
        self.assertEqual(
            data,
            {
                "action": "remove",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P3",
                "value": {
                    "type": "quantity",
                    "value": {"amount": "+12", "unit": "11573"},
                },
                "what": "statement",
            },
        )

        data = parser.parse_command("-Q1234\tP4\t9~0.1")
        self.assertEqual(
            data,
            {
                "action": "remove",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P4",
                "value": {
                    "type": "quantity",
                    "value": {
                        "amount": "+9",
                        "upperBound": "+9.1",
                        "lowerBound": "+8.9",
                        "unit": "1",
                    },
                },
                "what": "statement",
            },
        )

    def test_v1_add_item(self):
        parser = V1CommandParser()
        data = parser.parse_command("Q1234\tP2\tQ1")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "what": "statement",
            },
        )

    def test_v1_add_quantity(self):
        parser = V1CommandParser()
        data = parser.parse_command("Q1234\tP1\t12")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"type": "quantity", "value": {"amount": "+12", "unit": "1"}},
                "what": "statement",
            },
        )

        data = parser.parse_command("Q1234\tP3\t12U11573")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P3",
                "value": {
                    "type": "quantity",
                    "value": {"amount": "+12", "unit": "11573"},
                },
                "what": "statement",
            },
        )

        data = parser.parse_command("Q1234\tP4\t9~0.1")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P4",
                "value": {
                    "type": "quantity",
                    "value": {
                        "amount": "+9",
                        "upperBound": "+9.1",
                        "lowerBound": "+8.9",
                        "unit": "1",
                    },
                },
                "what": "statement",
            },
        )

    def test_v1_add_alias(self):
        parser = V1CommandParser()

        data = parser.parse_command('Q1234\tApt\t"Texto brasileiro"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "what": "alias",
                "item": "Q1234",
                "language": "pt",
                "value": {"type": "aliases", "value": ["Texto brasileiro"]},
            },
        )

    def test_v1_add_description(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tDen\t"Item description"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "what": "description",
                "item": "Q1234",
                "language": "en",
                "value": {"type": "string", "value": "Item description"},
            },
        )

    def test_v1_add_label(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tLfr\t"Note en français"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "what": "label",
                "item": "Q1234",
                "language": "fr",
                "value": {"type": "string", "value": "Note en français"},
            },
        )

    def test_v1_add_site(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tSmysite\t"Site mysite"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "what": "sitelink",
                "item": "Q1234",
                "site": "mysite",
                "value": {"type": "string", "value": "Site mysite"},
            },
        )

    def test_v1_add_somevalue_novalue(self):
        parser = V1CommandParser()
        data = parser.parse_command("Q1234\tP1\tsomevalue")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"value": "somevalue", "type": "somevalue"},
                "what": "statement",
            },
        )

        data = parser.parse_command("Q1234\tP1\tnovalue")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"value": "novalue", "type": "novalue"},
                "what": "statement",
            },
        )

    def test_v1_add_string(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tP1\t"this is a string"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"type": "string", "value": "this is a string"},
                "what": "statement",
            },
        )

    def test_v1_add_monolingualstring(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tP10\ten:"this is a string in english"')
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P10",
                "value": {
                    "type": "monolingualtext",
                    "value": {
                        "language": "en",
                        "text": "this is a string in english",
                    },
                },
                "what": "statement",
            },
        )

    def test_v1_add_location(self):
        parser = V1CommandParser()
        data = parser.parse_command("Q1234\tP10\t@43.26193/10.92708")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P10",
                "value": {
                    "type": "globecoordinate",
                    "value": {
                        "latitude": 43.26193,
                        "longitude": 10.92708,
                        "precision": 0.000001,
                        "globe": "http://www.wikidata.org/entity/Q2",
                    },
                },
                "what": "statement",
            },
        )

    def test_v1_add_time(self):
        parser = V1CommandParser()
        data = parser.parse_command("Q1234\tP10\t+1967-01-17T00:00:00Z/11")
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P10",
                "value": {
                    "type": "time",
                    "value": {
                        "time": "+1967-01-17T00:00:00Z",
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
                "what": "statement",
            },
        )

    def test_v1_add_item_with_references(self):
        parser = V1CommandParser()
        data = parser.parse_command(
            'Q1234\tP2\tQ1\tS1\t"source text"\tS2\t+1967-01-17T00:00:00Z/11'
        )
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "references": [
                    [
                        {
                            "property": "P1",
                            "value": {"type": "string", "value": "source text"},
                        },
                        {
                            "property": "P2",
                            "value": {
                                "type": "time",
                                "value": {
                                    "time": "+1967-01-17T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                            },
                        },
                    ]
                ],
                "what": "statement",
            },
        )

    def test_v1_add_item_with_references_multiple_blocks(self):
        parser = V1CommandParser()
        data = parser.parse_command(
            'Q1234\tP2\tQ1\tS1\t"source text"\t!S2\t+1967-01-17T00:00:00Z/11'
        )
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "references": [
                    [
                        {
                            "property": "P1",
                            "value": {"type": "string", "value": "source text"},
                        },
                    ],
                    [
                        {
                            "property": "P2",
                            "value": {
                                "type": "time",
                                "value": {
                                    "time": "+1967-01-17T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                            },
                        }
                    ],
                ],
                "what": "statement",
            },
        )

    def test_v1_add_item_with_qualifiers(self):
        parser = V1CommandParser()
        data = parser.parse_command(
            'Q1234\tP2\tQ1\tP1\t"qualifier text"\tP2\t+1970-01-17T00:00:00Z/11'
        )
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "qualifiers": [
                    {
                        "property": "P1",
                        "value": {"type": "string", "value": "qualifier text"},
                    },
                    {
                        "property": "P2",
                        "value": {
                            "type": "time",
                            "value": {
                                "time": "+1970-01-17T00:00:00Z",
                                "precision": 11,
                                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                            },
                        },
                    },
                ],
                "what": "statement",
            },
        )

    def test_v1_add_item_with_qualifiers_and_references(self):
        parser = V1CommandParser()
        data = parser.parse_command(
            'Q1234\tP2\tQ1\tS1\t"source text"\tP1\t"qualifier text"\tP2\t+1970-01-17T00:00:00Z/11\tS2\t+1967-01-17T00:00:00Z/11'
        )
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P2",
                "value": {"type": "wikibase-entityid", "value": "Q1"},
                "qualifiers": [
                    {
                        "property": "P1",
                        "value": {"type": "string", "value": "qualifier text"},
                    },
                    {
                        "property": "P2",
                        "value": {
                            "type": "time",
                            "value": {
                                "time": "+1970-01-17T00:00:00Z",
                                "precision": 11,
                                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                            },
                        },
                    },
                ],
                "references": [
                    [
                        {
                            "property": "P1",
                            "value": {"type": "string", "value": "source text"},
                        },
                        {
                            "property": "P2",
                            "value": {
                                "type": "time",
                                "value": {
                                    "time": "+1967-01-17T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                            },
                        },
                    ]
                ],
                "what": "statement",
            },
        )

    def test_v1_command_with_comment(self):
        parser = V1CommandParser()
        data = parser.parse_command("CREATE /* This is a comment. */")
        self.assertEqual(
            data,
            {
                "action": "create",
                "type": "item",
                "summary": "This is a comment.",
            },
        )

        data = parser.parse_command("MERGE\tQ1\tQ2 /* This is a comment. */")
        self.assertEqual(
            data,
            {
                "action": "merge",
                "type": "item",
                "item1": "Q1",
                "item2": "Q2",
                "summary": "This is a comment.",
            },
        )

    def test_v1_statement_rank(self):
        parser = V1CommandParser()
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tR+')
        self.assertEqual(
            data,
            {
                "action": "add",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "rank": "preferred",
                "value": {"type": "string", "value": "this is a string"},
                "what": "statement",
            },
        )
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tR0')
        self.assertEqual(data["rank"], "normal")
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tR-')
        self.assertEqual(data["rank"], "deprecated")
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tRpreferred')
        self.assertEqual(data["rank"], "preferred")
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tRnormal')
        self.assertEqual(data["rank"], "normal")
        data = parser.parse_command('Q1234\tP1\t"this is a string"\tRdeprecated')
        self.assertEqual(data["rank"], "deprecated")

    def test_v1_bad_remove_qualifier(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1\tP2")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1\tP2\tQ3")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1\tP2\tQ3\tP4")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1\tP2\tQ3\tP4\tQ5\tP6")
            self.assertEqual(
                context.exception.message,
                "REMOVE_QUAL command must be Qid|Pid|value|Pid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_QUAL\tQ1\tP2\tQ3\tS4\tQ5")
            self.assertEqual(
                context.exception.message, "REMOVE_QUAL command must have 1 qualifier"
            )

    def test_v1_bad_remove_reference(self):
        parser = V1CommandParser()
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1\tP2")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1\tP2\tQ3")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1\tP2\tQ3\tS4")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1\tP2\tQ3\tS4\tQ5\tS6")
            self.assertEqual(
                context.exception.message,
                "REMOVE_REF command must be Qid|Pid|value|Sid|value",
            )
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("REMOVE_REF\tQ1\tP2\tQ3\tP4\tQ5")
            self.assertEqual(
                context.exception.message, "REMOVE_REF command must have 1 reference"
            )

    def test_v1_invalid_entries(self):
        parser = V1CommandParser()

        # Test invalid entity ID
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("INVALID_ENTITY\tP1\tQ1")
            self.assertEqual(context.exception.message, "Invalid entity INVALID_ENTITY")

        # Test invalid property ID
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tINVALID_PROPERTY\tQ1")
            self.assertEqual(context.exception.message, "Invalid property INVALID_PROPERTY")

        # Test invalid value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tP1\tINVALID_VALUE")
            self.assertEqual(context.exception.message, "Invalid value INVALID_VALUE")

        # Test invalid alias value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tApt\tINVALID_ALIAS")
            self.assertEqual(context.exception.message, "Invalid value INVALID_ALIAS")

        # Test invalid alias value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tApt\tQ1234")
            self.assertEqual(context.exception.message, "alias must be a string instance")

        # Test invalid description value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tDpt\tINVALID_DESCRIPTION")
            self.assertEqual(context.exception.message, "Invalid value INVALID_DESCRIPTION")

        # Test invalid description value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tDpt\tQ1234")
            self.assertEqual(context.exception.message, "description must be a string instance")

        # Test invalid label value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tLpt\tINVALID_LABEL")
            self.assertEqual(context.exception.message, "Invalid value INVALID_LABEL")

        # Test invalid label value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tLpt\tQ1234")
            self.assertEqual(context.exception.message, "label must be a string instance")

        # Test invalid sitelink value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tSwiki\tINVALID_SITELINK")
            self.assertEqual(context.exception.message, "Invalid value INVALID_SITELINK")

        # Test invalid sitelink value
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tSwiki\tQ1234")
            self.assertEqual(context.exception.message, "sitelink must be a string instance")

        # Test invalid qualifier property
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tP1\tQ1\tP_INVALID_QUALIFIER\tQ2")
            self.assertEqual(context.exception.message, "Invalid qualifier property P_INVALID_QUALIFIER")

        # Test invalid source property
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tP1\tQ1\tS_INVALID_SOURCE\tQ2")
            self.assertEqual(context.exception.message, "Invalid source S_INVALID_SOURCE")

        # Test invalid reference property
        with self.assertRaises(Exception) as context:
            _data = parser.parse_command("Q1234\tP1\tQ1\tS1\tINVALID_REFERENCE")
            self.assertEqual(context.exception.message, "Invalid value INVALID_REFERENCE")
