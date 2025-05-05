import requests_mock
from django.test import TestCase

from core.factories import TokenFactory, BatchFactory
from core.models import BatchCommand, Client
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker


class TestBatchCommand(TestCase):
    def setUp(self):
        self.api_mocker = ApiMocker()
        self.token = TokenFactory(user__username="user")

    def parse(self, text):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(v1, "Test", "user", text)
        return batch

    def test_error_status(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(parser, "Batch", "wikiuser", "CREATE")
        command = batch.batchcommand_set.first()
        command.status = BatchCommand.STATUS_ERROR
        command.save()
        self.assertTrue(command.is_error_status())
        command.status = BatchCommand.STATUS_INITIAL
        command.save()
        self.assertFalse(command.is_error_status())
        command.status = BatchCommand.STATUS_RUNNING
        command.save()
        self.assertFalse(command.is_error_status())
        command.status = BatchCommand.STATUS_DONE
        command.save()
        self.assertFalse(command.is_error_status())

    def test_create_command(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(parser, "Batch", "wikiuser", "CREATE")
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "")
        self.assertEqual(command.action, BatchCommand.ACTION_CREATE)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, "")
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "")
        self.assertFalse(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_merge_command(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", "MERGE\tQ1\tQ2"
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "")
        self.assertEqual(command.action, BatchCommand.ACTION_MERGE)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, "")
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "")
        self.assertFalse(command.is_add_or_remove_command())
        self.assertTrue(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_remove_item(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", "-Q1234\tP2\tQ1"
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_REMOVE)
        self.assertEqual(command.prop, "P2")
        self.assertEqual(command.value, "Q1")
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "STATEMENT")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_remove_time(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", "-Q1234\tP1\t12"
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_REMOVE)
        self.assertEqual(command.prop, "P1")
        self.assertEqual(command.value, {"amount": "+12", "unit": "1"})
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "STATEMENT")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_add_item(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", "Q1234\tP2\tQ1"
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_ADD)
        self.assertEqual(command.prop, "P2")
        self.assertEqual(command.value, "Q1")
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "STATEMENT")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_add_alias(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", 'Q1234\tApt\t"Texto brasileiro"'
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_ADD)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, ["Texto brasileiro"])
        self.assertEqual(command.language, "pt")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "ALIAS")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertTrue(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_add_description(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", 'Q1234\tDen\t"Item description"'
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_ADD)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, "Item description")
        self.assertEqual(command.language, "en")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "DESCRIPTION")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertTrue(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_add_label(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", 'Q1234\tLfr\t"Note en français"'
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_ADD)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, "Note en français")
        self.assertEqual(command.language, "fr")
        self.assertEqual(command.sitelink, "")
        self.assertEqual(command.what, "LABEL")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertTrue(command.is_label_alias_description_command())
        self.assertFalse(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    def test_add_site(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", 'Q1234\tSmysite\t"Site mysite"'
        )
        command = batch.batchcommand_set.first()
        self.assertEqual(command.status_info, "INITIAL")
        self.assertEqual(command.entity_info, "[Q1234]")
        self.assertEqual(command.action, BatchCommand.ACTION_ADD)
        self.assertEqual(command.prop, "")
        self.assertEqual(command.value, "Site mysite")
        self.assertEqual(command.language, "")
        self.assertEqual(command.sitelink, "mysite")
        self.assertEqual(command.what, "SITELINK")
        self.assertTrue(command.is_add_or_remove_command())
        self.assertFalse(command.is_merge_command())
        self.assertFalse(command.is_label_alias_description_command())
        self.assertTrue(command.is_sitelink_command())
        self.assertFalse(command.is_error_status())

    @requests_mock.Mocker()
    def test_set_statement_api_payload(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q333")
        batch = self.parse(
            """Q1234|P1|Q2
        Q333|P3|12|P5|100"""
        )
        commands = batch.commands()
        client = Client(token=self.token, wikibase=self.api_mocker.wikibase)
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(
            commands[0].api_payload(client),
            {
                "patch": [
                    {
                        "op": "add",
                        "path": "/statements/P1",
                        "value": [
                            {
                                "property": {"id": "P1"},
                                "value": {"type": "value", "content": "Q2"},
                            }
                        ],
                    }
                ]
            },
        )
        self.assertEqual(
            commands[1].api_payload(client),
            {
                "patch": [
                    {
                        "op": "add",
                        "path": "/statements/P3",
                        "value": [
                            {
                                "property": {"id": "P3"},
                                "value": {
                                    "type": "value",
                                    "content": {"amount": "+12", "unit": "1"},
                                },
                                "qualifiers": [
                                    {
                                        "property": {"id": "P5"},
                                        "value": {
                                            "type": "value",
                                            "content": {"amount": "+100", "unit": "1"},
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        )
