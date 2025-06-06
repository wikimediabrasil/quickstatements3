import copy
from django.test import TestCase

from core.factories import BatchFactory
from core.parsers.v1 import V1CommandParser
from core.exceptions import NoQualifiers
from core.exceptions import NoReferenceParts


class AddRemoveQualRefTests(TestCase):
    INITIAL: dict = {
        "type": "item",
        "id": "Q12345678",
        "labels": {},
        "descriptions": {},
        "aliases": {},
        "statements": {
            "P65": [
                {
                    "id": "Q12345678$FD9DA04C-1967-4949-92FF-BD8405BCE4D9",
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
                    "value": {
                        "type": "value",
                        "content": {"amount": "+42", "unit": "1"},
                    },
                }
            ],
            "P31": [
                {
                    "id": "Q238107$96026FB3-7D84-48E3-8C64-6D2E2D033B7E",
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
                        }
                    ],
                    "references": [
                        {
                            "hash": "95cc6e523b528da734a9cfdcb25c79f5a423cefe",
                            "parts": [
                                {
                                    "property": {
                                        "id": "P93",
                                        "data_type": "url"
                                    },
                                    "value": {
                                        "type": "value",
                                        "content": "https://kernel.org/",
                                    },
                                },
                                {
                                    "property": {
                                        "id": "P84267",
                                        "data_type": "quantity",
                                    },
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
                                    "property": {
                                        "id": "P93",
                                        "data_type": "url"
                                    },
                                    "value": {
                                        "type": "value",
                                        "content": "https://www.mediawiki.org/",
                                    },
                                },
                                {
                                    "property": {
                                        "id": "P74",
                                        "data_type": "time"
                                    },
                                    "value": {
                                        "type": "value",
                                        "content": {
                                            "time": "+1980-10-21T00:00:00Z",
                                            "precision": 11,
                                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                        },
                                    },
                                },
                                {
                                    "property": {
                                        "id": "P84267",
                                        "data_type": "quantity",
                                    },
                                    "value": {
                                        "type": "value",
                                        "content": {"amount": "+42", "unit": "1"},
                                    },
                                },
                            ],
                        },
                    ],
                    "property": {"id": "P31", "data_type": "url"},
                    "value": {"type": "somevalue"},
                }
            ],
        },
        "sitelinks": {},
    }

    def parse(self, text):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "Test", "user", text)
        return batch

    def assertStmtnCount(self, entity: dict, property_id: str, length: int):
        self.assertEqual(len(entity["statements"][property_id]), length)

    def assertQualCount(self, entity: dict, property_id: str, length: int, i: int = 0):
        quals = entity["statements"][property_id][i]["qualifiers"]
        self.assertEqual(len(quals), length)

    def assertRefCount(self, entity: dict, property_id: str, length: int, i: int = 0):
        refs = entity["statements"][property_id][i].get("references", [])
        self.assertEqual(len(refs), length)

    def assertRefPartsCount(
        self, entity: dict, pid: str, length: int, i: int = 0, ipart: int = 0
    ):
        parts = entity["statements"][pid][i]["references"][ipart]["parts"]
        self.assertEqual(len(parts), length)

    # -----
    # TESTS
    # -----

    def test_create_statement(self):
        text = """
        Q12345678|P65|42
        +Q12345678|P65|42|S12|"https://kernel.org"
        Q12345678|P65|-10
        """
        batch = self.parse(text)
        entity = copy.deepcopy(self.INITIAL)
        # -----
        create_statement = batch.commands()[0]
        self.assertStmtnCount(entity, "P65", 1)
        self.assertEqual(
            entity["statements"]["P65"][0]["value"]["content"]["amount"], "+42"
        )
        create_statement.update_entity_json(entity)
        self.assertEqual(entity, copy.deepcopy(self.INITIAL))
        # -----
        create_statement = batch.commands()[1]
        self.assertStmtnCount(entity, "P65", 1)
        self.assertEqual(
            entity["statements"]["P65"][0]["value"]["content"]["amount"], "+42"
        )
        create_statement.update_entity_json(entity)
        self.assertStmtnCount(entity, "P65", 2)
        self.assertEqual(
            entity["statements"]["P65"][0]["value"]["content"]["amount"], "+42"
        )
        self.assertRefCount(entity, "P65", 0, 0)
        self.assertEqual(
            entity["statements"]["P65"][1]["value"]["content"]["amount"], "+42"
        )
        self.assertRefCount(entity, "P65", 1, 1)
        # -----
        set_statement2 = batch.commands()[2]
        self.assertStmtnCount(entity, "P65", 2)
        set_statement2.update_entity_json(entity)
        self.assertStmtnCount(entity, "P65", 3)
        self.assertEqual(
            entity["statements"]["P65"][0]["value"]["content"]["amount"], "+42"
        )
        self.assertRefCount(entity, "P65", 0, 0)
        self.assertEqual(
            entity["statements"]["P65"][1]["value"]["content"]["amount"], "+42"
        )
        self.assertRefCount(entity, "P65", 1, 1)
        self.assertEqual(
            entity["statements"]["P65"][2]["value"]["content"]["amount"], "-10"
        )
        self.assertRefCount(entity, "P65", 0, 2)

    def test_remove_qualifier(self):
        text = """
        REMOVE_QUAL|Q12345678|P65|42|P84267|-5
        REMOVE_QUAL|Q12345678|P31|somevalue|P18|+2025-01-15T00:00:00Z/11
        REMOVE_QUAL|Q12345678|P65|42|P84267|999
        """
        batch = self.parse(text)
        entity = copy.deepcopy(self.INITIAL)
        # -----
        remove_p65_qual = batch.commands()[0]
        self.assertQualCount(entity, "P65", 2)
        remove_p65_qual.update_entity_json(entity)
        self.assertQualCount(entity, "P65", 1)
        self.assertEqual(
            entity["statements"]["P65"][0]["qualifiers"][0]["property"]["id"], "P65"
        )
        with self.assertRaises(NoQualifiers):
            # try to remove it again
            remove_p65_qual.update_entity_json(entity)
        # -----
        remove_p31_qual = batch.commands()[1]
        self.assertQualCount(entity, "P31", 1)
        remove_p31_qual.update_entity_json(entity)
        self.assertQualCount(entity, "P31", 0)
        with self.assertRaises(NoQualifiers):
            # try to remove it again
            remove_p31_qual.update_entity_json(entity)
        # -----
        remove_nothing = batch.commands()[2]
        self.assertQualCount(entity, "P65", 1)
        with self.assertRaises(NoQualifiers):
            remove_nothing.update_entity_json(entity)
        self.assertQualCount(entity, "P65", 1)

    def test_remove_reference(self):
        text = """
        REMOVE_REF|Q12345678|P65|42|S31|somevalue
        REMOVE_REF|Q12345678|P31|somevalue|S93|"https://www.mediawiki.org/"
        REMOVE_REF|Q12345678|P31|somevalue|S84267|42
        REMOVE_REF|Q12345678|P31|somevalue|S84267|42
        """
        batch = self.parse(text)
        entity = copy.deepcopy(self.INITIAL)
        # -----
        remove_nothing = batch.commands()[0]
        self.assertRefCount(entity, "P65", 0)
        with self.assertRaises(NoReferenceParts):
            remove_nothing.update_entity_json(entity)
        self.assertRefCount(entity, "P65", 0)
        # ---
        prop = entity["statements"]["P31"][0]["references"][0]["parts"][0]["property"]
        self.assertEqual(prop["id"], "P93")
        prop = entity["statements"]["P31"][0]["references"][1]["parts"][0]["property"]
        self.assertEqual(prop["id"], "P93")
        # -----
        remove_part_mediawiki = batch.commands()[1]
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        remove_part_mediawiki.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 2, ipart=1)
        with self.assertRaises(NoReferenceParts):
            # try to remove it again
            remove_part_mediawiki.update_entity_json(entity)
        # -----
        remove_42 = batch.commands()[2]
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 2, ipart=1)
        remove_42.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=0)
        self.assertRefPartsCount(entity, "P31", 2, ipart=1)
        # -----
        remove_42_again = batch.commands()[3]
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=0)
        self.assertRefPartsCount(entity, "P31", 2, ipart=1)
        remove_42_again.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=0)
        self.assertRefPartsCount(entity, "P31", 1, ipart=1)
        with self.assertRaises(NoReferenceParts):
            # try to remove it again
            remove_42_again.update_entity_json(entity)
        # ----
        prop = entity["statements"]["P31"][0]["references"][0]["parts"][0]["property"]
        self.assertEqual(prop["id"], "P93")
        prop = entity["statements"]["P31"][0]["references"][1]["parts"][0]["property"]
        self.assertEqual(prop["id"], "P74")

    def test_add_reference(self):
        text = """
        Q12345678|P31|somevalue|S93|"https://example.com/"
        Q12345678|P31|somevalue|S93|"https://kernel.org/"
        Q12345678|P31|somevalue|S93|"https://kernel.org/"
        Q12345678|P31|somevalue|S93|"https://kernel.org/"|S84267|42
        Q12345678|P31|somevalue|S93|"https://kernel.org/"|S84267|43
        """
        batch = self.parse(text)
        entity = copy.deepcopy(self.INITIAL)
        # -----
        add_new = batch.commands()[0]
        self.assertRefCount(entity, "P31", 2)
        add_new.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 3)
        # ---
        add_matching_part = batch.commands()[1]
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        self.assertRefPartsCount(entity, "P31", 1, ipart=2)
        add_matching_part.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 4)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        self.assertRefPartsCount(entity, "P31", 1, ipart=2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=3)
        # -----
        dont_add_duplicate = batch.commands()[2]
        dont_add_duplicate.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 4)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        self.assertRefPartsCount(entity, "P31", 1, ipart=2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=3)
        # -----
        dont_add_duplicate_existing = batch.commands()[3]
        dont_add_duplicate_existing.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 4)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        self.assertRefPartsCount(entity, "P31", 1, ipart=2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=3)
        # -----
        add_extended_matching_part = batch.commands()[4]
        add_extended_matching_part.update_entity_json(entity)
        self.assertRefCount(entity, "P31", 5)
        self.assertRefPartsCount(entity, "P31", 2, ipart=0)
        self.assertRefPartsCount(entity, "P31", 3, ipart=1)
        self.assertRefPartsCount(entity, "P31", 1, ipart=2)
        self.assertRefPartsCount(entity, "P31", 1, ipart=3)
        self.assertRefPartsCount(entity, "P31", 2, ipart=4)
        # ----
