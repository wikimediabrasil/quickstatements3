from django.test import TestCase
from django.test import override_settings
import unittest

from core.factories import BatchFactory
from core.models import Batch, BatchCommand
from core.parsers.v1 import V1CommandParser
from core.parsers.csv import CSVCommandParser


class TestBatch(TestCase):
    def test_batch_is_running(self):
        batch = Batch.objects.create(name="teste")
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertTrue(batch.is_running)

    def test_batch_is_stopped(self):
        batch = Batch.objects.create(name="teste")
        self.assertFalse(batch.is_running)
        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_stopped)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertTrue(batch.is_stopped)
        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertFalse(batch.is_stopped)
        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_stopped)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertFalse(batch.is_stopped)

    def test_batch_is_preview(self):
        batch = Batch.objects.create(name="teste")
        self.assertFalse(batch.is_preview)
        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_preview)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertFalse(batch.is_preview)
        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertTrue(batch.is_preview)
        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_preview)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertFalse(batch.is_preview)

    def test_batch_is_initial(self):
        batch = Batch.objects.create(name="teste")
        self.assertTrue(batch.is_initial)
        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertFalse(batch.is_stopped)

    def test_batch_is_initial_or_running(self):
        batch = Batch.objects.create(name="teste")
        self.assertTrue(batch.is_initial_or_running)

        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertTrue(batch.is_initial_or_running)

        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_initial_or_running)

        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertFalse(batch.is_initial_or_running)

        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertFalse(batch.is_initial_or_running)

        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_initial_or_running)

    def test_batch_is_preview_initial_or_running(self):
        batch = Batch.objects.create(name="teste")
        self.assertTrue(batch.is_preview_initial_or_running)

        batch.status = Batch.STATUS_RUNNING
        batch.save()
        self.assertTrue(batch.is_preview_initial_or_running)

        batch.status = Batch.STATUS_BLOCKED
        batch.save()
        self.assertFalse(batch.is_preview_initial_or_running)

        batch.status = Batch.STATUS_PREVIEW
        batch.save()
        self.assertTrue(batch.is_preview_initial_or_running)

        batch.status = Batch.STATUS_STOPPED
        batch.save()
        self.assertFalse(batch.is_preview_initial_or_running)

        batch.status = Batch.STATUS_DONE
        batch.save()
        self.assertFalse(batch.is_preview_initial_or_running)

    def test_batch_stop(self):
        batch = Batch.objects.create(name="teste")
        self.assertFalse(batch.is_stopped)
        batch.stop()
        self.assertTrue(batch.is_stopped)
        self.assertTrue(batch.message.startswith("Batch stopped processing at"))

    def test_batch_restart(self):
        batch = Batch.objects.create(name="teste", status=Batch.STATUS_BLOCKED)
        batch.restart()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        batch.restart()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_DONE
        batch.save()
        batch.restart()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        batch.restart()
        self.assertTrue(batch.is_initial)
        self.assertTrue(batch.message.startswith("Batch restarted at"))

    def test_batch_rerun(self):
        batch = Batch.objects.create(name="teste", status=Batch.STATUS_BLOCKED)
        batch.rerun()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_RUNNING
        batch.save()
        batch.rerun()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_STOPPED
        batch.save()
        batch.rerun()
        self.assertFalse(batch.is_initial)
        batch.status = Batch.STATUS_DONE
        batch.save()
        batch.rerun()
        self.assertFalse(batch.is_initial)
        BatchCommand.objects.create(
            batch=batch, index=0, json={}, raw="{}", status=BatchCommand.STATUS_DONE
        )
        batch.rerun()
        self.assertFalse(batch.is_initial)
        BatchCommand.objects.create(
            batch=batch, index=1, json={}, raw="{}", status=BatchCommand.STATUS_RUNNING
        )
        BatchCommand.objects.create(
            batch=batch, index=2, json={}, raw="{}", status=BatchCommand.STATUS_ERROR
        )
        batch.rerun()
        self.assertTrue(batch.is_initial)
        self.assertTrue(batch.message.startswith("Batch rerun at"))
        self.assertEqual(batch.commands()[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(batch.commands()[1].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(batch.commands()[2].status, BatchCommand.STATUS_INITIAL)


class TestV1Batch(TestCase):
    def test_v1_correct_create_command(self):
        v1 = V1CommandParser()
        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())
        batch = BatchFactory.load_from_parser(
            v1, "My batch", "myuser", "CREATE||-Q1234|P1|12||Q222|P4|9~0.1"
        )
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch")
        self.assertEqual(BatchCommand.objects.count(), 3)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 3)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(bc1.raw, "CREATE")
        self.assertEqual(bc1.operation, BatchCommand.Operation.CREATE_ITEM)
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(bc2.raw, "-Q1234\tP1\t12")
        bc3 = BatchCommand.objects.get(batch=batch, index=2)
        self.assertEqual(bc3.raw, "Q222\tP4\t9~0.1")

    def test_create_property(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", "CREATE_PROPERTY|wikibase-item||LAST|P1|Q2"
        )
        cmd = batch.commands()[0]
        self.assertEqual(cmd.raw, "CREATE_PROPERTY\twikibase-item")
        self.assertEqual(cmd.operation, BatchCommand.Operation.CREATE_PROPERTY)

    def test_remove_statemeny_by_id(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", "-STATEMENT|Q1234$abcdefgh-uijkl"
        )
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_ID)
        self.assertEqual(cmd.entity_id, "Q1234")

    def test_remove_statemeny_by_value(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "b", "u", "-Q1234|P5|Q31")
        cmd = batch.commands()[0]
        self.assertEqual(
            cmd.operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.prop, "P5")
        self.assertEqual(cmd.statement_api_value, {"type": "value", "content": "Q31"})

    def test_remove_statemeny_by_value_2(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", """-Q1234|P5|"my string" """
        )
        cmd = batch.commands()[0]
        self.assertEqual(
            cmd.operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.prop, "P5")
        self.assertEqual(
            cmd.statement_api_value, {"type": "value", "content": "my string"}
        )

    def test_user_summary(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "b", "u", "Q1|P1|Q2 /* my comment */")
        cmd = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(cmd.user_summary, "my comment")

    @override_settings(TOOLFORGE_TOOL_NAME="abcdef")
    def test_edit_summary_with_editgroups(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", "Q1|P1|Q2 /* my comment */||Q1|P1|Q3"
        )
        batch_id = batch.id
        cmd = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            cmd.edit_summary(),
            f"QuickStatements 3.0 [[:toollabs:abcdef/batch/{batch_id}|batch #{batch_id}]]: my comment",
        )
        cmd = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            cmd.edit_summary(),
            f"QuickStatements 3.0 [[:toollabs:abcdef/batch/{batch_id}|batch #{batch_id}]]",
        )

    def test_set_sitelink(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", """Q1234|Sptwiki|"Cool article" """
        )
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.sitelink, "ptwiki")
        self.assertEqual(cmd.value_value, "Cool article")

    def test_remove_sitelink(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "b", "u", """Q1234|Sptwiki|"" """)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_SITELINK)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.sitelink, "ptwiki")

    def test_set_label(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "b", "u", """Q1234|Lpt|"oi" """)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.SET_LABEL)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.language, "pt")
        self.assertEqual(cmd.value_value, "oi")

    def test_remove_label(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "b", "u", """Q1234|Lpt|"" """)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_LABEL)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(cmd.language, "pt")

    def test_remove_qualifier(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", """REMOVE_QUAL|Q1234|P1|Q2|P3|Q4"""
        )
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_QUALIFIER)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(len(cmd.references()), 0)
        self.assertEqual(
            cmd.qualifiers_for_api(),
            [{"property": {"id": "P3"}, "value": {"type": "value", "content": "Q4"}}],
        )

    def test_remove_reference(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", """REMOVE_REF|Q1234|P1|Q2|S3|Q4"""
        )
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_REFERENCE)
        self.assertEqual(cmd.entity_id, "Q1234")
        self.assertEqual(len(cmd.qualifiers()), 0)
        self.assertEqual(
            cmd.references_for_api(),
            [
                {
                    "parts": [
                        {
                            "property": {"id": "P3"},
                            "value": {"type": "value", "content": "Q4"},
                        }
                    ]
                }
            ],
        )

    def test_errors(self):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "b", "u", """CREATE||LAST|abc|123||xyz"""
        )
        cmd0 = batch.commands()[0]
        cmd1 = batch.commands()[1]
        cmd2 = batch.commands()[2]
        self.assertEqual(len(batch.commands()), 3)
        self.assertEqual(cmd0.status,BatchCommand.STATUS_INITIAL)
        self.assertEqual(cmd1.status,BatchCommand.STATUS_ERROR)
        self.assertEqual(cmd1.message, "Invalid property 'abc'")
        self.assertEqual(cmd2.status,BatchCommand.STATUS_ERROR)
        self.assertEqual(cmd2.message, "Statement must contain at least entity, property and value")


class TestCSVBatch(TestCase):
    def test_create_property(self):
        COMMAND = """qid,Len,Den,P31
,Regina Phalange,fictional character,Q95074"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(v1, "My batch CREATE", "myuser", COMMAND)
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch CREATE")
        self.assertEqual(BatchCommand.objects.count(), 4)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 4)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(bc1.json, {"action": "create", "type": "item"})
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "what": "label",
                "item": "LAST",
                "language": "en",
                "value": {"type": "string", "value": "Regina Phalange"},
            },
        )
        bc3 = BatchCommand.objects.get(batch=batch, index=2)
        self.assertEqual(
            bc3.json,
            {
                "action": "add",
                "what": "description",
                "item": "LAST",
                "language": "en",
                "value": {"type": "string", "value": "fictional character"},
            },
        )
        bc4 = BatchCommand.objects.get(batch=batch, index=3)
        self.assertEqual(
            bc4.json,
            {
                "action": "add",
                "what": "statement",
                "entity": {"type": "item", "id": "LAST"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q95074"},
            },
        )

    def test_add_and_remove_property(self):
        COMMAND = """qid,P31,-P31
Q4115189,Q5,Q5"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "My batch CREATE REMOVE", "myuser", COMMAND
        )
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch CREATE REMOVE")
        self.assertEqual(BatchCommand.objects.count(), 2)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 2)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "remove",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )

    def test_add_property(self):
        COMMAND = """qid,P369
Q4115189,Q5
Q4115189,somevalue
Q4115189,novalue
L123,Q5
L123-S1,Q5
L123-F1,Q5"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(v1, "My batch 1", "myuser", COMMAND)
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch 1")
        self.assertEqual(BatchCommand.objects.count(), 6)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 6)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P369",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P369",
                "value": {"type": "somevalue", "value": "somevalue"},
                "what": "statement",
            },
        )
        bc3 = BatchCommand.objects.get(batch=batch, index=2)
        self.assertEqual(
            bc3.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P369",
                "value": {"type": "novalue", "value": "novalue"},
                "what": "statement",
            },
        )
        bc4 = BatchCommand.objects.get(batch=batch, index=3)
        self.assertEqual(
            bc4.json,
            {
                "action": "add",
                "entity": {"id": "L123", "type": "lexeme"},
                "property": "P369",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )
        bc5 = BatchCommand.objects.get(batch=batch, index=4)
        self.assertEqual(
            bc5.json,
            {
                "action": "add",
                "entity": {"id": "L123-S1", "type": "sense"},
                "property": "P369",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )
        bc6 = BatchCommand.objects.get(batch=batch, index=5)
        self.assertEqual(
            bc6.json,
            {
                "action": "add",
                "entity": {"id": "L123-F1", "type": "form"},
                "property": "P369",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )

    def test_add_label(self):
        COMMAND = """qid,Len
Q4115189,Sandbox
Q4115189,"Patterns, Predictors, and Outcome"
"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(v1, "My batch LABEL", "myuser", COMMAND)
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch LABEL")
        self.assertEqual(BatchCommand.objects.count(), 2)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 2)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {"type": "string", "value": "Sandbox"},
                "what": "label",
                "language": "en",
            },
        )
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {
                    "type": "string",
                    "value": "Patterns, Predictors, and Outcome",
                },
                "what": "label",
                "language": "en",
            },
        )

    def test_add_alias(self):
        COMMAND = """qid,Apt
Q411518,Sandbox 3
Q411518,"Patterns, Predictors, and Outcome and Questions"
"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(v1, "My batch ALIAS", "myuser", COMMAND)
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch ALIAS")
        self.assertEqual(BatchCommand.objects.count(), 2)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 2)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "item": "Q411518",
                "value": {"type": "aliases", "value": ["Sandbox 3"]},
                "what": "alias",
                "language": "pt",
            },
        )
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "item": "Q411518",
                "value": {
                    "type": "aliases",
                    "value": ["Patterns, Predictors, and Outcome and Questions"],
                },
                "what": "alias",
                "language": "pt",
            },
        )

    def test_add_description(self):
        COMMAND = """qid,Dpt
Q411518,Sandbox Description
Q411518,"Patterns, Predictors, and Outcome and Descriptions"
"""

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "My batch DESCRIPTION", "myuser", COMMAND
        )
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch DESCRIPTION")
        self.assertEqual(BatchCommand.objects.count(), 2)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 2)
        bc1 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "item": "Q411518",
                "value": {"type": "string", "value": "Sandbox Description"},
                "what": "description",
                "language": "pt",
            },
        )
        bc2 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "item": "Q411518",
                "value": {
                    "type": "string",
                    "value": "Patterns, Predictors, and Outcome and Descriptions",
                },
                "what": "description",
                "language": "pt",
            },
        )

    def test_full_command(self):
        COMMAND = """qid,Len,Den,Aen,P31,-P31,P21,P735,qal1545,S248,s214,S143,Senwiki
Q4115189,Douglas Adams,author,Douglas Noël Adams,Q5,Q36180,Q6581097,Q463035,\"\"\"1\"\"\",Q54919,\"\"\"113230702\"\"\",Q328,Douglas Adams
"""
        self.maxDiff = None

        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())

        v1 = CSVCommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "My batch DESCRIPTION", "myuser", COMMAND
        )
        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.name, "My batch DESCRIPTION")
        self.assertEqual(BatchCommand.objects.count(), 8)
        self.assertEqual(BatchCommand.objects.filter(batch=batch).count(), 8)

        bc0 = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            bc0.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {"type": "string", "value": "Douglas Adams"},
                "what": "label",
                "language": "en",
            },
        )

        bc1 = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            bc1.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {"type": "string", "value": "author"},
                "what": "description",
                "language": "en",
            },
        )

        bc2 = BatchCommand.objects.get(batch=batch, index=2)
        self.assertEqual(
            bc2.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {"type": "aliases", "value": ["Douglas Noël Adams"]},
                "what": "alias",
                "language": "en",
            },
        )

        bc3 = BatchCommand.objects.get(batch=batch, index=3)
        self.assertEqual(
            bc3.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q5"},
                "what": "statement",
            },
        )

        bc4 = BatchCommand.objects.get(batch=batch, index=4)
        self.assertEqual(
            bc4.json,
            {
                "action": "remove",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P31",
                "value": {"type": "wikibase-entityid", "value": "Q36180"},
                "what": "statement",
            },
        )

        bc5 = BatchCommand.objects.get(batch=batch, index=5)
        self.assertEqual(
            bc5.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P21",
                "value": {"type": "wikibase-entityid", "value": "Q6581097"},
                "what": "statement",
            },
        )

        bc6 = BatchCommand.objects.get(batch=batch, index=6)
        self.assertEqual(
            bc6.json,
            {
                "action": "add",
                "entity": {"id": "Q4115189", "type": "item"},
                "property": "P735",
                "value": {"type": "wikibase-entityid", "value": "Q463035"},
                "what": "statement",
                "qualifiers": [
                    {"property": "P1545", "value": {"type": "string", "value": "1"}}
                ],
                "references": [
                    [
                        {
                            "property": "P248",
                            "value": {"type": "wikibase-entityid", "value": "Q54919"},
                        },
                        {
                            "property": "P214",
                            "value": {"type": "string", "value": "113230702"},
                        },
                    ],
                    [
                        {
                            "property": "P143",
                            "value": {"type": "wikibase-entityid", "value": "Q328"},
                        }
                    ],
                ],
            },
        )

        bc7 = BatchCommand.objects.get(batch=batch, index=7)
        self.assertEqual(
            bc7.json,
            {
                "action": "add",
                "item": "Q4115189",
                "value": {"type": "string", "value": "Douglas Adams"},
                "what": "sitelink",
                "site": "enwiki",
            },
        )

    def test_user_summary(self):
        COMMAND = """qid,P31,#
Q4115189,Q5,my comment"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(cmd.user_summary, "my comment")

    @override_settings(TOOLFORGE_TOOL_NAME="abcdef")
    def test_edit_summary_with_editgroups(self):
        COMMAND = """qid,P31,#
Q4115189,Q5,my comment
Q4115189,Q5,
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        batch_id = batch.id
        cmd = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(
            cmd.edit_summary(),
            f"QuickStatements 3.0 [[:toollabs:abcdef/batch/{batch_id}|batch #{batch_id}]]: my comment",
        )
        cmd = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(
            cmd.edit_summary(),
            f"QuickStatements 3.0 [[:toollabs:abcdef/batch/{batch_id}|batch #{batch_id}]]",
        )

    @override_settings(TOOLFORGE_TOOL_NAME=None)
    def test_edit_summary_without_editgroups(self):
        COMMAND = """qid,P31,#
Q4115189,Q5,my comment
Q4115189,Q5,
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = BatchCommand.objects.get(batch=batch, index=0)
        self.assertEqual(cmd.edit_summary(), "my comment")
        cmd = BatchCommand.objects.get(batch=batch, index=1)
        self.assertEqual(cmd.edit_summary(), "")

    def test_remove_statemeny_by_value(self):
        COMMAND = """qid,P31,-P31
Q4115189,Q5,Q6"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = batch.commands()[1]
        self.assertEqual(
            cmd.operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(cmd.entity_id, "Q4115189")
        self.assertEqual(cmd.prop, "P31")
        self.assertEqual(cmd.statement_api_value, {"type": "value", "content": "Q6"})

    def test_set_sitelink(self):
        COMMAND = """qid,Sptwiki
Q4115189,"Cool article"
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(cmd.entity_id, "Q4115189")
        self.assertEqual(cmd.sitelink, "ptwiki")
        self.assertEqual(cmd.value_value, "Cool article")

    def test_remove_sitelink_minus(self):
        COMMAND = """qid,-Sptwiki
Q4115189,"x"
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_SITELINK)
        self.assertEqual(cmd.entity_id, "Q4115189")
        self.assertEqual(cmd.sitelink, "ptwiki")

    def test_set_label(self):
        COMMAND = """qid,Lpt
Q4115189,"Cool label"
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.SET_LABEL)
        self.assertEqual(cmd.entity_id, "Q4115189")
        self.assertEqual(cmd.language, "pt")
        self.assertEqual(cmd.value_value, "Cool label")

    def test_remove_label_minus(self):
        COMMAND = """qid,-Lpt
Q4115189,"x"
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        cmd = batch.commands()[0]
        self.assertEqual(cmd.operation, BatchCommand.Operation.REMOVE_LABEL)
        self.assertEqual(cmd.entity_id, "Q4115189")
        self.assertEqual(cmd.language, "pt")

    @unittest.skip("Skipping as this is not implemented (issue #330)")
    def test_remove_sitelink_not_empty(self):
        COMMAND = """qid,Sptwiki
Q4115189,""
"""
        par = CSVCommandParser()
        batch = BatchFactory.load_from_parser(par, "b", "u", COMMAND)
        self.assertEqual(len(batch.commands()), 1)
