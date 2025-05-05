import os
from unittest import skipIf

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.factories import WikibaseFactory, BatchFactory
from core.models import Batch, Client, Token
from core.parsers.v1 import V1CommandParser

TOKEN = os.environ.get("INTEGRATION_TEST_AUTH_TOKEN")
SKIP_INTEGRATION = TOKEN is None


@skipIf(SKIP_INTEGRATION, "Integration")
@override_settings(TOOLFORGE_TOOL_NAME=None)
class IntegrationTests(TestCase):
    maxDiff = None

    def setUp(self):
        self.username = "integration_user"
        self.wikibase = WikibaseFactory(
            url="https://test.wikidata.org", identifier="test"
        )
        user = User.objects.create(username=self.username)
        token = Token.objects.create(user=user, value=TOKEN)
        self.client.force_login(user)
        self.api_client = Client(token=token, wikibase=self.wikibase)

    def parse_run(self, text):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "Integration", self.username, text, combine_commands=True
        )
        batch.run()
        return batch

    def test_Q238107(self):
        raw = """
        Q238107|Len|""
        Q238107|Den|""
        Q238107|Smetawiki|""
        Q238107|Len|"QuickStatements 3.0 test item"
        Q238107|Den|"A test item for the QuickStatements 3.0 project"
        Q238107|Aen|"A test item for QuickStatements"
        Q238107|Aen|"Removable alias"
        Q238107|Dpt|"Um item de teste do projeto QuickStatements 3.0"
        Q238107|Lpt|"Teste - rótulo a ser removido posteriormente"
        Q238107|Lpt|""
        -Q238107|Aen|"Removable alias"
        Q238107|Smetawiki|"QuickStatements 3.0"
        -Q238107|P65|42
        -Q238107|P372|1.5U71737
        -Q238107|P31|somevalue
        -Q238107|P18|+2001-01-15T00:00:00Z/11
        -Q238107|P196|novalue
        Q238107|P65|42|R+|P65|84|P84267|-5|P93|"https://toberemoved.org/"
        Q238107|P372|1.5U71737
        REMOVE_QUAL|Q238107|P65|42|P93|"https://toberemoved.org/"
        Q238107|P31|somevalue|P18|+2025-01-15T00:00:00Z/11|S93|"https://kernel.org/"|S84267|42|!S93|"https://www.mediawiki.org/"|S74|+1980-10-21T00:00:00Z/11
        Q238107|P18|+2001-01-15T00:00:00Z/11|R0|S65|999|!S74|+2012-12-21T00:00:00Z/11
        Q238107|P196|novalue|R-
        """
        batch = self.parse_run(raw)
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        doc = self.api_client.get_entity("Q238107")
        self.assertEqual(doc["type"], "item")
        self.assertEqual(doc["id"], "Q238107")
        self.assertEqual(doc["labels"], {"en": "QuickStatements 3.0 test item"})
        self.assertEqual(
            doc["descriptions"],
            {
                "en": "A test item for the QuickStatements 3.0 project",
                "pt": "Um item de teste do projeto QuickStatements 3.0",
            },
        )
        self.assertEqual(doc["aliases"], {"en": ["A test item for QuickStatements"]})
        self.assertEqual(
            doc["sitelinks"],
            {
                "metawiki": {
                    "title": "QuickStatements 3.0",
                    "badges": [],
                    "url": "https://meta.wikimedia.org/wiki/QuickStatements_3.0",
                }
            },
        )
        self.assertEqual(len(doc["statements"]["P65"]), 1)
        self.assertEqual(
            doc["statements"]["P65"][0],
            {
                "id": doc["statements"]["P65"][0]["id"],
                "rank": "preferred",
                "qualifiers": [
                    {
                        "property": {"id": "P65", "data_type": "quantity"},
                        "value": {
                            "type": "value",
                            "content": {"amount": "+84", "unit": "1"},
                        },
                    },
                    {
                        "property": {"id": "P84267", "data_type": "quantity"},
                        "value": {
                            "type": "value",
                            "content": {"amount": "-5", "unit": "1"},
                        },
                    },
                ],
                "references": [],
                "property": {"id": "P65", "data_type": "quantity"},
                "value": {"type": "value", "content": {"amount": "+42", "unit": "1"}},
            },
        )
        self.assertEqual(len(doc["statements"]["P31"]), 1)
        self.assertEqual(
            doc["statements"]["P31"][0],
            {
                "id": doc["statements"]["P31"][0]["id"],
                "rank": "normal",
                "qualifiers": [
                    {
                        "property": {"id": "P18", "data_type": "time"},
                        "value": {
                            "type": "value",
                            "content": {
                                "time": "+2025-01-15T00:00:00Z",
                                "precision": 11,
                                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                            },
                        },
                    },
                ],
                "references": [
                    {
                        "hash": "95cc6e523b528da734a9cfdcb25c79f5a423cefe",
                        "parts": [
                            {
                                "property": {"id": "P93", "data_type": "url"},
                                "value": {
                                    "type": "value",
                                    "content": "https://kernel.org/",
                                },
                            },
                            {
                                "property": {"id": "P84267", "data_type": "quantity"},
                                "value": {
                                    "type": "value",
                                    "content": {"amount": "+42", "unit": "1"},
                                },
                            },
                        ],
                    },
                    {
                        "hash": "71a764a610caa3ea6161dfee9115a682945223c7",
                        "parts": [
                            {
                                "property": {"id": "P93", "data_type": "url"},
                                "value": {
                                    "type": "value",
                                    "content": "https://www.mediawiki.org/",
                                },
                            },
                            {
                                "property": {"id": "P74", "data_type": "time"},
                                "value": {
                                    "type": "value",
                                    "content": {
                                        "time": "+1980-10-21T00:00:00Z",
                                        "precision": 11,
                                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                    },
                                },
                            },
                        ],
                    },
                ],
                "property": {"id": "P31", "data_type": "url"},
                "value": {"type": "somevalue"},
            },
        )
        self.assertEqual(len(doc["statements"]["P196"]), 1)
        self.assertEqual(
            doc["statements"]["P196"][0],
            {
                "id": doc["statements"]["P196"][0]["id"],
                "rank": "deprecated",
                "qualifiers": [],
                "references": [],
                "property": {"id": "P196", "data_type": "wikibase-item"},
                "value": {"type": "novalue"},
            },
        )
        self.assertEqual(len(doc["statements"]["P18"]), 1)
        self.assertEqual(
            doc["statements"]["P18"][0],
            {
                "id": doc["statements"]["P18"][0]["id"],
                "rank": "normal",
                "qualifiers": [],
                "references": [
                    {
                        "hash": "9bc946e5761bc2db49998dbe208f9390d88d0188",
                        "parts": [
                            {
                                "property": {"id": "P65", "data_type": "quantity"},
                                "value": {
                                    "type": "value",
                                    "content": {"amount": "+999", "unit": "1"},
                                },
                            }
                        ],
                    },
                    {
                        "hash": "6c3a2860c535c7a5b280fcfce413b39343aeda37",
                        "parts": [
                            {
                                "property": {"id": "P74", "data_type": "time"},
                                "value": {
                                    "type": "value",
                                    "content": {
                                        "time": "+2012-12-21T00:00:00Z",
                                        "precision": 11,
                                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                    },
                                },
                            }
                        ],
                    },
                ],
                "property": {"id": "P18", "data_type": "time"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2001-01-15T00:00:00Z",
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
        )
