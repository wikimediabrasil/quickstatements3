import requests_mock
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User

from core.tests.test_api import ApiMocker
from core.client import Client as ApiClient
from core.models import Batch
from core.models import BatchCommand
from core.parsers.v1 import V1CommandParser
from web.models import Token


class ProcessingTests(TestCase):
    def parse(self, text):
        user, _ = User.objects.get_or_create(username="user")
        Token.objects.get_or_create(user=user, value="tokenvalue")
        v1 = V1CommandParser()
        batch = v1.parse("Test", "user", text)
        batch.save_batch_and_preview_commands()
        return batch

    def parse_run(self, text):
        batch = self.parse(text)
        batch.run()
        return batch

    def parse_with_block_on_errors(self, text):
        batch = self.parse(text)
        batch.block_on_errors = True
        batch.save_batch_and_preview_commands()
        return batch

    @requests_mock.Mocker()
    def test_batch_success(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P65", "quantity")
        ApiMocker.property_data_type(mocker, "P12", "url")
        ApiMocker.item_empty(mocker, "Q1234")
        ApiMocker.add_statement_successful(mocker, "Q1234")

        batch = self.parse('Q1234|P65|32||Q1234|P12|"""https://myurl.com"""')
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)

        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_batch_is_blocked_when_value_type_verification_fails(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P65", "quantity")
        ApiMocker.add_statement_successful(mocker, "Q1234")

        batch = self.parse('Q1234|P65|32||Q1234|P65|"string"')
        batch.block_on_errors = True
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)

        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)

    @requests_mock.Mocker()
    def test_successful_value_type_verification_stays_on_initial(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P111", "quantity")
        ApiMocker.add_statement_successful(mocker, "Q1234")

        raw = """Q1234|P111|0
        Q1234|P111|1
        Q1234|P111|2
        Q1234|P111|3
        Q1234|P111|4
        Q1234|P111|5
        Q1234|P111|6
        Q1234|P111|"string"
        Q1234|P111|8"""
        batch = self.parse(raw)
        batch.block_on_errors = True
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)

        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[4].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[5].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[6].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[7].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[8].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(len(commands), 9)

    @requests_mock.Mocker()
    def test_all_data_types(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.create_item(mocker, "Q123")
        ApiMocker.item_empty(mocker, "Q123")
        ApiMocker.add_statement_successful(mocker, "Q123")
        ApiMocker.property_data_type(mocker, "P1", "commonsMedia")
        ApiMocker.property_data_type(mocker, "P2", "geo-shape")
        ApiMocker.property_data_type(mocker, "P3", "tabular-data")
        ApiMocker.property_data_type(mocker, "P4", "url")
        ApiMocker.property_data_type(mocker, "P5", "external-id")
        ApiMocker.property_data_type(mocker, "P6", "wikibase-item")
        ApiMocker.property_data_type(mocker, "P7", "wikibase-property")
        ApiMocker.property_data_type(mocker, "P8", "globe-coordinate")
        ApiMocker.property_data_type(mocker, "P9", "monolingualtext")
        ApiMocker.property_data_type(mocker, "P10", "quantity")
        ApiMocker.property_data_type(mocker, "P11", "string")
        ApiMocker.property_data_type(mocker, "P12", "time")
        ApiMocker.property_data_type(mocker, "P13", "musical-notation")
        ApiMocker.property_data_type(mocker, "P14", "math")
        ApiMocker.property_data_type(mocker, "P15", "wikibase-lexeme")
        ApiMocker.property_data_type(mocker, "P16", "wikibase-form")
        ApiMocker.property_data_type(mocker, "P17", "wikibase-sense")
        ApiMocker.property_data_type(mocker, "P18", "entity-schema")

        raw = """CREATE
        LAST|P1|"MyCommonsMedia.jpg"
        LAST|P2|"@43.26193/10.92708"
        LAST|P3|"my,tabular,data"
        LAST|P4|"https://www.myurl.com"
        LAST|P5|"123.456.789-00"
        LAST|P6|Q123
        LAST|P7|P123
        LAST|P8|@43.26193/10.92708
        LAST|P9|pt:"monolingualtext"
        LAST|P10|12345678
        LAST|P11|"string"
        LAST|P12|+1967-01-17T00:00:00Z/11
        LAST|P13|"my musical notation"
        LAST|P14|"my mathematical notation"
        LAST|P15|L123
        LAST|P16|L123-F123
        LAST|P17|L123-S123
        LAST|P18|Q123"""
        batch = self.parse(raw)
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)

        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.CREATE_ITEM)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[4].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[5].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[6].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[7].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[8].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[9].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[10].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[11].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[12].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[13].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[14].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[15].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[16].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[17].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[18].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_block_on_errors(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P5", "quantity")
        ApiMocker.item_empty(mocker, "Q1")
        ApiMocker.add_statement_successful(mocker, "Q1")
        raw = """Q1|P5|33||Q1|P5|"string"||Q1|P5|45"""

        batch = self.parse(raw)
        batch.block_on_errors = False
        batch.save_batch_and_preview_commands()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(len(commands), 3)

        ApiMocker.add_statement_failed_server(mocker, "Q2")
        v1 = V1CommandParser()
        batch = v1.parse(
            "Should block", "user", "Q1|P5|123||Q2|P5|123||Q1|P5|123||Q1|P5|123"
        )
        batch.block_on_errors = True
        batch.save_batch_and_preview_commands()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(len(commands), 4)

    @requests_mock.Mocker()
    def test_dont_block_on_errors_last_id(self, mocker):
        """
        Checks that when NOT blocking on errors, if a CREATE
        fails, all subsequent LAST commands also fail.
        """
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P1", "quantity")
        ApiMocker.item_empty(mocker, "Q1")
        ApiMocker.add_statement_successful(mocker, "Q1")
        ApiMocker.create_item_failed_server(mocker)
        batch = self.parse("CREATE||LAST|P1|1||LAST|P1|1||Q1|P1|1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.CREATE_ITEM)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertTrue(
            "The server failed to process the request" in commands[0].message
        )
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.LAST_NOT_EVALUATED)
        self.assertEqual(commands[1].message, "LAST could not be evaluated.")
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].error, BatchCommand.Error.LAST_NOT_EVALUATED)
        self.assertEqual(commands[2].message, "LAST could not be evaluated.")
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_block_on_errors_last_id(self, mocker):
        """
        Checks that when we DO block on errors, if a CREATE
        fails, all subsequent LAST commands stay in INITIAL.
        """
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.property_data_type(mocker, "P1", "quantity")
        ApiMocker.add_statement_successful(mocker, "Q1")
        ApiMocker.create_item_failed_server(mocker)
        batch = self.parse_with_block_on_errors("CREATE||LAST|P1|1||LAST|P1|1||Q1|P1|1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.CREATE_ITEM)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertTrue(
            "The server failed to process the request" in commands[0].message
        )
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_block_on_not_autoconfirmed(self, mocker):
        ApiMocker.is_not_autoconfirmed(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "The user is not an autoconfirmed user.")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_block_no_token_server_failed(self, mocker):
        ApiMocker.autoconfirmed_failed_server(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "We don't have a valid API token for the user")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_block_no_token_unauthorized(self, mocker):
        ApiMocker.autoconfirmed_failed_unauthorized(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "We don't have a valid API token for the user")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_remove_statement_by_id(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        batch = self.parse("-STATEMENT|Q1234$abcdefgh-uijkl")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(
            commands[0].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_ID
        )
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[0].response_json, "Statement deleted")

    @requests_mock.Mocker()
    def test_remove_statement_by_value_success(self, mocker):
        statements = {
            "P5": [
                {
                    "id": "Q1234$abcdefgh-uijkl",
                    "value": {
                        "type": "value",
                        "content": "Q12",
                    },
                }
            ],
        }
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.statements(mocker, "Q1234", statements)
        ApiMocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        batch = self.parse("-Q1234|P5|Q12")
        client = ApiClient.from_username(batch.user)
        res = batch.commands()[0].get_final_entity_json(client)
        self.assertEqual(len(res["statements"]["P5"]), 0)

    @requests_mock.Mocker()
    def test_remove_statement_by_value_success_will_pick_first(self, mocker):
        statements = {
            "P5": [
                {
                    "id": "Q1234$abcdefgh-uijkl",
                    "value": {
                        "type": "value",
                        "content": "Q12",
                    },
                },
                {
                    "id": "Q1234$defgh-xyzabc",
                    "value": {
                        "type": "value",
                        "content": "Q12",
                    },
                },
            ],
        }
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.statements(mocker, "Q1234", statements)
        ApiMocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        ApiMocker.delete_statement_fail(mocker, "Q1234$defgh-xyzabc")
        batch = self.parse("-Q1234|P5|Q12")
        client = ApiClient.from_username(batch.user)
        res = batch.commands()[0].get_final_entity_json(client)
        self.assertEqual(res["statements"]["P5"][0]["id"], "Q1234$defgh-xyzabc")

    @requests_mock.Mocker()
    def test_remove_statement_by_value_fail_no_statements_property(self, mocker):
        statements = {}
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.statements(mocker, "Q1234", statements)
        batch = self.parse("-Q1234|P5|Q12")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(
            commands[0].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.NO_STATEMENTS_PROPERTY)

    @requests_mock.Mocker()
    def test_remove_statement_by_value_fail_no_statements_value(self, mocker):
        statements = {
            "P5": [
                {
                    "id": "Q1234$abcdefgh-uijkl",
                    "value": {
                        "type": "value",
                        "content": "this is my string",
                    },
                }
            ],
        }
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.statements(mocker, "Q1234", statements)
        batch = self.parse("-Q1234|P5|Q12")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(
            commands[0].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.NO_STATEMENTS_VALUE)

    @requests_mock.Mocker()
    def test_set_sitelink_success(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.item_empty(mocker, "Q1234")
        ApiMocker.sitelink_success(mocker, "Q1234", "ptwiki", "Cool article")
        batch = self.parse("""Q1234|Sptwiki|"Cool article" """)
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_set_sitelink_invalid(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.item_empty(mocker, "Q1234")
        ApiMocker.sitelink_invalid(mocker, "Q1234", "ptwikix")
        batch = self.parse("""Q1234|Sptwikix|"Cool article" """)
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.SITELINK_INVALID)

    @requests_mock.Mocker()
    @override_settings(BASE_REST_URL="https://test.wikidata.org/w/rest.php")
    def test_remove_quantity_tolerance(self, mocker):
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.property_data_type(mocker, "P89982", "quantity")
        ApiMocker.statements(
            mocker,
            "Q1",
            {
                "P89982": [
                    {
                        "id": "Q208235$79D23941-64B1-4260-A962-8AB10E84B2C2",
                        "rank": "normal",
                        "qualifiers": [],
                        "references": [],
                        "property": {"id": "P89982", "data_type": "quantity"},
                        "value": {
                            "type": "value",
                            "content": {
                                "amount": "+30",
                                "unit": "http://test.wikidata.org/entity/Q208592",
                                "upperBound": "+40",
                                "lowerBound": "+10",
                            },
                        },
                    }
                ]
            },
        )
        ApiMocker.patch_item_successful(mocker, "Q1", {})
        batch = self.parse("-Q1|P89982|30[10,40]U208592")
        batch.run()
        client = ApiClient.from_username(batch.user)
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        command = batch.commands()[0]
        self.assertEqual(command.status, command.STATUS_DONE)
        entity = command.get_final_entity_json(client)
        self.assertEqual(len(entity["statements"]["P89982"]), 0)

    @requests_mock.Mocker()
    def test_all_errors(self, mocker):
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.item_empty(mocker, "Q1234")
        ApiMocker.item_empty(mocker, "Q5")
        ApiMocker.item_empty(mocker, "Q7")
        ApiMocker.property_data_type(mocker, "P5", "quantity")
        ApiMocker.sitelink_invalid(mocker, "Q1234", "ptwikix")
        ApiMocker.patch_item_fail(
            mocker, "Q5", 400, {"code": "code", "message": "message"}
        )
        ApiMocker.patch_item_fail(
            mocker, "Q7", 500, {"code": "code", "message": "message"}
        )
        ApiMocker.statements(mocker, "Q9", {})
        ApiMocker.statements(
            mocker,
            "Q11",
            {
                "P5": [
                    {
                        "id": "Q1234$abcdefgh-uijkl",
                        "value": {
                            "type": "value",
                            "content": {"amount": "+32", "unit": "1"},
                        },
                    }
                ],
            },
        )
        batch = self.parse(
            """
        CREATE_PROPERTY|url
        Q1234|P5|12
        Q1234|Sptwikix|"Cool article"
        Q5|P5|123
        Q7|P5|321
        -Q9|P5|123
        -Q11|P5|123
        """
        )
        batch.combine_commands = True
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.CREATE_PROPERTY)
        self.assertEqual(commands[0].error, BatchCommand.Error.OP_NOT_IMPLEMENTED)
        self.assertEqual(commands[1].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[1].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[2].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[2].error, BatchCommand.Error.SITELINK_INVALID)
        self.assertEqual(commands[3].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[3].error, BatchCommand.Error.API_USER_ERROR)
        self.assertEqual(commands[4].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[4].error, BatchCommand.Error.API_SERVER_ERROR)
        self.assertEqual(
            commands[5].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[5].error, BatchCommand.Error.NO_STATEMENTS_PROPERTY)
        self.assertEqual(
            commands[6].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[6].error, BatchCommand.Error.NO_STATEMENTS_VALUE)
        self.assertEqual(len(commands), 7)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_ERROR)

    @requests_mock.Mocker()
    def test_get_label(self, mocker):
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.create_item(mocker, "Q1")
        ApiMocker.item_empty(mocker, "Q1")
        ApiMocker.item_empty(mocker, "Q2")
        ApiMocker.property_data_type(mocker, "P1", "quantity")
        ApiMocker.patch_item_successful(mocker, "Q1", {})
        ApiMocker.patch_item_successful(mocker, "Q2", {})
        batch = self.parse(
            """
        CREATE
        LAST|P1|12
        Q2|P1|15
        """
        )
        batch.combine_commands = True
        commands = batch.commands()
        client = ApiClient.from_username(batch.user)
        labels = {
            "Q1": {"pt": "pt1", "en": "en1"},
            "Q2": {"pt": "pt2", "en": "en2"},
        }
        ApiMocker.labels(mocker, client, labels)
        BatchCommand.load_labels(client, commands, "pt")
        self.assertEqual(commands[0].display_label, None)
        self.assertEqual(commands[1].display_label, None)
        self.assertEqual(commands[2].display_label, "pt2")
        BatchCommand.load_labels(client, commands, "de")
        self.assertEqual(commands[0].display_label, None)
        self.assertEqual(commands[1].display_label, None)
        self.assertEqual(commands[2].display_label, "en2")
        BatchCommand.load_labels(client, commands, "en")
        self.assertEqual(commands[0].display_label, None)
        self.assertEqual(commands[1].display_label, None)
        self.assertEqual(commands[2].display_label, "en2")
        batch.run()  # -> load Q1 into commands[0] and commands[1]
        commands = batch.commands()
        BatchCommand.load_labels(client, commands, "pt")
        self.assertEqual(commands[0].display_label, "pt1")
        self.assertEqual(commands[1].display_label, "pt1")
        self.assertEqual(commands[2].display_label, "pt2")
        BatchCommand.load_labels(client, commands, "de")
        self.assertEqual(commands[0].display_label, "en1")
        self.assertEqual(commands[1].display_label, "en1")
        self.assertEqual(commands[2].display_label, "en2")
        BatchCommand.load_labels(client, commands, "en")
        self.assertEqual(commands[0].display_label, "en1")
        self.assertEqual(commands[1].display_label, "en1")
        self.assertEqual(commands[2].display_label, "en2")

    @requests_mock.Mocker()
    def test_remove_qual_or_ref_errors(self, mocker):
        ApiMocker.item(
            mocker,
            "Q1",
            {
                "statements": {
                    "P5": [
                        {
                            "id": "Q1234$abcdefgh-uijkl",
                            "value": {
                                "type": "value",
                                "content": "Q12",
                            },
                            "qualifiers": [
                                {
                                    "property": {"id": "P65", "data_type": "quantity"},
                                    "value": {
                                        "type": "value",
                                        "content": {"amount": "+84", "unit": "1"},
                                    },
                                },
                            ],
                            "references": [
                                {
                                    "hash": "i_am_ahash",
                                    "parts": [
                                        {
                                            "property": {
                                                "id": "P93",
                                                "data_type": "url",
                                            },
                                            "value": {
                                                "type": "value",
                                                "content": "https://kernel.org/",
                                            },
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            },
        )
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.property_data_type(mocker, "P5", "wikibase-item")
        ApiMocker.patch_item_successful(mocker, "Q1", {})
        batch = self.parse(
            """
        REMOVE_QUAL|Q1|P5|Q12|P123|123
        REMOVE_QUAL|Q1|P5|Q999|P65|84
        REMOVE_QUAL|Q1|P5|Q12|P65|84
        REMOVE_REF|Q1|P5|Q12|S93|"https://kernel.xyz"
        REMOVE_REF|Q1|P5|Q999|S93|"https://kernel.org/"
        REMOVE_REF|Q1|P5|Q12|S93|"https://kernel.org/"
        """
        )
        commands = batch.commands()
        batch.run()
        # qualifiers
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.NO_QUALIIFERS)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.NO_QUALIIFERS)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        # references
        self.assertEqual(commands[3].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[3].error, BatchCommand.Error.NO_REFERENCE_PARTS)
        self.assertEqual(commands[4].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[4].error, BatchCommand.Error.NO_REFERENCE_PARTS)
        self.assertEqual(commands[5].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_combine_with_create(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.create_item(mocker, "Q123")
        ApiMocker.item_empty(mocker, "Q123")
        ApiMocker.add_statement_successful(mocker, "Q123", {"id": "Q123$abcdef"})
        ApiMocker.property_data_type(mocker, "P11", "string")
        # ---
        # COMBINING COMMANDS
        # ---
        raw = """
        CREATE
        LAST|P11|"should combine"
        LAST|P11|"should combine"
        LAST|P11|"should send!"
        """
        batch = self.parse(raw)
        batch.combine_commands = True
        commands = batch.commands()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].response_json, {})  # no API connection
        self.assertEqual(commands[1].response_json, {})  # no API connection
        self.assertEqual(commands[2].response_json, {})  # no API connection
        self.assertEqual(
            commands[3].response_json, {"id": "Q123"}
        )  # created: API connection
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_DONE)
        # ---
        # WITHOUT COMBINING COMMANDS
        # ---
        v1 = V1CommandParser()
        batch = v1.parse("without", "user", raw)
        batch.save_batch_and_preview_commands()
        batch.combine_commands = False
        batch.run()
        commands = batch.commands()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(
            commands[0].response_json, {"id": "Q123"}
        )  # with API connection
        self.assertEqual(
            commands[1].response_json, {"id": "Q123$abcdef"}
        )  # with API connection
        self.assertEqual(
            commands[2].response_json, {"id": "Q123$abcdef"}
        )  # with API connection
        self.assertEqual(
            commands[3].response_json, {"id": "Q123$abcdef"}
        )  # with API connection
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_combine_failed_data_type_should_fail(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.item_empty(mocker, "Q1")
        ApiMocker.property_data_type(mocker, "P11", "string")
        ApiMocker.add_statement_successful(mocker, "Q1", {"id": "Q1$abcdef"})
        raw = """
        Q1|P11|"string"
        Q1|P11|"string"
        Q1|P11|123
        """
        batch = self.parse(raw)
        batch.combine_commands = True
        batch.run()
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[0].response_json, {})
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[1].response_json, {})
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].response_json, {})
        self.assertEqual(len(commands), 3)

    @requests_mock.Mocker()
    def test_create_and_last_should_combine(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.create_item(mocker, "Q123")
        ApiMocker.item_empty(mocker, "Q123")
        ApiMocker.property_data_type(mocker, "P11", "string")
        ApiMocker.add_statement_successful(mocker, "Q123", {"id": "Q123$abcdef"})
        # ---
        # COMBINING COMMANDS
        # ---
        raw = """
        LAST|P11|"string"
        CREATE
        CREATE
        LAST|P11|"string"
        CREATE
        LAST|P11|"string"
        LAST|P11|123
        """
        batch = self.parse(raw)
        batch.combine_commands = True
        commands = batch.commands()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.LAST_NOT_EVALUATED)
        self.assertEqual(commands[0].response_json, {})
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].response_json, {"id": "Q123"})
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[2].response_json, {})
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[3].response_json, {"id": "Q123"})
        self.assertEqual(commands[4].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[4].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[4].response_json, {})
        self.assertEqual(commands[5].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[5].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[5].response_json, {})
        self.assertEqual(commands[6].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[6].response_json, {})
        self.assertEqual(len(commands), 7)
        # ---
        # WITHOUT COMBINING COMMANDS
        # ---
        v1 = V1CommandParser()
        batch = v1.parse("without", "user", raw)
        batch.save_batch_and_preview_commands()
        batch.combine_commands = False
        batch.run()
        commands = batch.commands()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.LAST_NOT_EVALUATED)
        self.assertEqual(commands[0].response_json, {})
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].response_json, {"id": "Q123"})
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[2].response_json, {"id": "Q123"})
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[3].response_json, {"id": "Q123$abcdef"})
        self.assertEqual(commands[4].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[4].response_json, {"id": "Q123"})
        self.assertEqual(commands[5].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[5].response_json, {"id": "Q123$abcdef"})
        self.assertEqual(commands[6].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[6].response_json, {})
        self.assertEqual(len(commands), 7)

    @requests_mock.Mocker()
    def test_create_and_last_with_failure(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.property_data_type(mocker, "P11", "string")
        ApiMocker.create_item_failed_server(mocker)
        # ---
        # COMBINING COMMANDS
        # ---
        raw = """
        CREATE
        LAST|P11|"a"
        LAST|P11|"b"
        LAST|P11|"c"
        """
        batch = self.parse(raw)
        batch.combine_commands = True
        commands = batch.commands()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[0].response_json, {})
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[1].response_json, {})
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[2].response_json, {})
        self.assertEqual(commands[3].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[3].error, BatchCommand.Error.API_SERVER_ERROR)
        self.assertEqual(commands[3].response_json, {})
        self.assertEqual(len(commands), 4)

    @requests_mock.Mocker()
    def test_batch_wont_verify_commands_already_verified(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.item_empty(mocker, "Q1")
        ApiMocker.property_data_type(mocker, "P1", "string")
        ApiMocker.property_data_type(mocker, "P2", "quantity")
        ApiMocker.patch_item_successful(mocker, "Q1", {})
        raw = """
        Q1|P1|"string"
        Q1|P2|14
        Q1|P2|"won't error"
        Q1|P1|32
        """
        batch = self.parse(raw)
        batch.block_on_errors = True
        batch.combine_commands = True
        commands = batch.commands()
        command = commands[2]
        command.value_type_verified = True
        command.save()
        command = commands[3]
        command.value_type_verified = True
        command.save()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        v1 = V1CommandParser()
        batch = v1.parse("now it will", "user", raw)
        batch.save_batch_and_preview_commands()
        batch.block_on_errors = True
        batch.run()
        commands = batch.commands()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_batch_will_skip_done_commands(self, mocker):
        ApiMocker.is_autoconfirmed(mocker)
        ApiMocker.wikidata_property_data_types(mocker)
        ApiMocker.create_item(mocker, "Q3")
        raw = """
        CREATE
        LAST|Lpt|"label"
        """
        batch = self.parse(raw)
        batch.combine_commands = True
        commands = batch.commands()
        command = commands[1]
        command.status = BatchCommand.STATUS_DONE
        command.save()
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        # was not updated because we hacked the status:
        self.assertEqual(commands[1].entity_id(), "LAST")
