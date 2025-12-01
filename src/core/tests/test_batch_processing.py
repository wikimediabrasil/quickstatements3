from unittest import mock

import requests_mock
from django.test import TestCase

from core.factories import TokenFactory, UserFactory, BatchFactory
from core.models import Batch, BatchCommand
from core.models import Client as ApiClient
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker


class ProcessingTests(TestCase):
    def setUp(self):
        self.api_mocker = ApiMocker()
        self.user = UserFactory(username="user")
        self.token = TokenFactory(user=self.user)
        self.api_client = ApiClient(token=self.token, wikibase=self.api_mocker.wikibase)

    def parse(self, text):
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1, "Test", "user", text, wikibase=self.api_mocker.wikibase
        )
        return batch

    def parse_run(self, text):
        batch = self.parse(text)
        batch.run()
        return batch

    def parse_with_block_on_errors(self, text):
        batch = self.parse(text)
        batch.block_on_errors = True
        batch.save()
        return batch

    @requests_mock.Mocker()
    def test_batch_success(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P65", "quantity")
        self.api_mocker.property_data_type(mocker, "P12", "url")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.add_statement_successful(mocker, "Q1234")

        batch = self.parse('Q1234|P65|32||Q1234|P12|"""https://myurl.com"""')
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)

        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_batch_is_blocked_when_value_type_verification_fails(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P65", "quantity")
        self.api_mocker.add_statement_successful(mocker, "Q1234")

        batch = self.parse('Q1234|P65|32||Q1234|P65|"string"')
        batch.block_on_errors = True
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)

        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)

    @requests_mock.Mocker()
    def test_successful_value_type_verification_stays_on_initial(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P111", "quantity")
        self.api_mocker.add_statement_successful(mocker, "Q1234")

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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.create_item(mocker, "Q123")
        self.api_mocker.item_empty(mocker, "Q123")
        self.api_mocker.add_statement_successful(mocker, "Q123")
        self.api_mocker.property_data_type(mocker, "P1", "commonsMedia")
        self.api_mocker.property_data_type(mocker, "P2", "geo-shape")
        self.api_mocker.property_data_type(mocker, "P3", "tabular-data")
        self.api_mocker.property_data_type(mocker, "P4", "url")
        self.api_mocker.property_data_type(mocker, "P5", "external-id")
        self.api_mocker.property_data_type(mocker, "P6", "wikibase-item")
        self.api_mocker.property_data_type(mocker, "P7", "wikibase-property")
        self.api_mocker.property_data_type(mocker, "P8", "globe-coordinate")
        self.api_mocker.property_data_type(mocker, "P9", "monolingualtext")
        self.api_mocker.property_data_type(mocker, "P10", "quantity")
        self.api_mocker.property_data_type(mocker, "P11", "string")
        self.api_mocker.property_data_type(mocker, "P12", "time")
        self.api_mocker.property_data_type(mocker, "P13", "musical-notation")
        self.api_mocker.property_data_type(mocker, "P14", "math")
        self.api_mocker.property_data_type(mocker, "P15", "wikibase-lexeme")
        self.api_mocker.property_data_type(mocker, "P16", "wikibase-form")
        self.api_mocker.property_data_type(mocker, "P17", "wikibase-sense")
        self.api_mocker.property_data_type(mocker, "P18", "entity-schema")

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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P5", "quantity")
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.add_statement_successful(mocker, "Q1")
        raw = """Q1|P5|33||Q1|P5|"string"||Q1|P5|45"""

        batch = self.parse(raw)
        batch.block_on_errors = False
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(len(commands), 3)

        self.api_mocker.add_statement_failed_server(mocker, "Q2")

        # FIXME: two different ways to instantiate the batch
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1,
            "Should block",
            "user",
            "Q1|P5|123||Q2|P5|123||Q1|P5|123||Q1|P5|123",
            wikibase=self.api_mocker.wikibase,
            block_on_errors=True,
        )
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P1", "quantity")
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.add_statement_successful(mocker, "Q1")
        self.api_mocker.create_item_failed_server(mocker)
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P1", "quantity")
        self.api_mocker.add_statement_successful(mocker, "Q1")
        self.api_mocker.create_item_failed_server(mocker)
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
        self.api_mocker.is_not_autoconfirmed(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "The user is not an autoconfirmed user.")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_block_no_token_server_failed(self, mocker):
        self.api_mocker.autoconfirmed_failed_server(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "We don't have a valid API token for the user")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_block_no_token_unauthorized(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        batch = self.parse("CREATE||LAST|P1|Q1")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_BLOCKED)
        self.assertEqual(batch.message, "We don't have a valid API token for the user")
        commands = batch.commands()
        self.assertEqual(commands[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_INITIAL)

    @requests_mock.Mocker()
    def test_remove_statement_by_id(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        batch = self.parse("-STATEMENT|Q1234$abcdefgh-uijkl")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(
            commands[0].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_ID
        )
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)

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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.statements(mocker, "Q1234", statements)
        self.api_mocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        batch = self.parse("-Q1234|P5|Q12")
        res = batch.commands()[0].get_final_entity_json(self.api_client)
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.statements(mocker, "Q1234", statements)
        self.api_mocker.delete_statement_sucessful(mocker, "Q1234$abcdefgh-uijkl")
        self.api_mocker.delete_statement_fail(mocker, "Q1234$defgh-xyzabc")
        batch = self.parse("-Q1234|P5|Q12")
        res = batch.commands()[0].get_final_entity_json(self.api_client)
        self.assertEqual(res["statements"]["P5"][0]["id"], "Q1234$defgh-xyzabc")

    @requests_mock.Mocker()
    def test_remove_statement_by_value_fail_no_statements_property(self, mocker):
        statements = {}
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.statements(mocker, "Q1234", statements)
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.statements(mocker, "Q1234", statements)
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.sitelink_success(mocker, "Q1234", "ptwiki", "Cool article")
        batch = self.parse("""Q1234|Sptwiki|"Cool article" """)
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_set_sitelink_invalid(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.sitelink_invalid(mocker, "Q1234", "ptwikix")
        batch = self.parse("""Q1234|Sptwikix|"Cool article" """)
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        commands = batch.commands()
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.SITELINK_INVALID)

    @requests_mock.Mocker()
    def test_remove_quantity_tolerance(self, mocker):
        unit_url = f"{self.api_mocker.wikibase.url}/entity/Q208592".replace(
            "https://", "http://"
        )
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.property_data_type(mocker, "P89982", "quantity")
        self.api_mocker.statements(
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
                                "unit": unit_url,
                                "upperBound": "+40",
                                "lowerBound": "+10",
                            },
                        },
                    }
                ]
            },
        )
        self.api_mocker.patch_item_successful(mocker, "Q1", {})
        batch = self.parse("-Q1|P89982|30[10,40]U208592")
        batch.run()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        command = batch.commands()[0]
        self.assertEqual(command.status, command.STATUS_DONE)
        entity = command.get_final_entity_json(self.api_client)
        self.assertEqual(len(entity["statements"]["P89982"]), 0)

    @requests_mock.Mocker()
    def test_all_errors(self, mocker):
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q5")
        self.api_mocker.item_empty(mocker, "Q7")
        self.api_mocker.property_data_type(mocker, "P5", "quantity")
        self.api_mocker.sitelink_invalid(mocker, "Q1234", "ptwikix")
        self.api_mocker.patch_item_fail(
            mocker, "Q5", 400, {"code": "code", "message": "message"}
        )
        self.api_mocker.patch_item_fail(
            mocker, "Q7", 500, {"code": "code", "message": "message"}
        )
        self.api_mocker.statements(mocker, "Q9", {})
        self.api_mocker.statements(
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
        self.assertEqual(commands[0].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[0].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertEqual(commands[1].operation, BatchCommand.Operation.SET_SITELINK)
        self.assertEqual(commands[1].error, BatchCommand.Error.SITELINK_INVALID)
        self.assertEqual(commands[2].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[2].error, BatchCommand.Error.API_USER_ERROR)
        self.assertEqual(commands[3].operation, BatchCommand.Operation.SET_STATEMENT)
        self.assertEqual(commands[3].error, BatchCommand.Error.API_SERVER_ERROR)
        self.assertEqual(
            commands[4].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[4].error, BatchCommand.Error.NO_STATEMENTS_PROPERTY)
        self.assertEqual(
            commands[5].operation, BatchCommand.Operation.REMOVE_STATEMENT_BY_VALUE
        )
        self.assertEqual(commands[5].error, BatchCommand.Error.NO_STATEMENTS_VALUE)
        self.assertEqual(len(commands), 6)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_ERROR)

    @requests_mock.Mocker()
    def test_remove_qual_or_ref_errors(self, mocker):
        self.api_mocker.item(
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
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.property_data_type(mocker, "P5", "wikibase-item")
        self.api_mocker.patch_item_successful(mocker, "Q1", {})
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
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.create_item(mocker, "Q123")
        self.api_mocker.item_empty(mocker, "Q123")
        self.api_mocker.add_statement_successful(mocker, "Q123", {"id": "Q123$abcdef"})
        self.api_mocker.property_data_type(mocker, "P11", "string")
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
        self.assertIsNone(commands[0].response_id)  # no API connection
        self.assertIsNone(commands[1].response_id)  # no API connection
        self.assertIsNone(commands[2].response_id)  # no API connection
        self.assertEqual(commands[3].response_id, "Q123")  # created: API connection
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_DONE)
        # ---
        # WITHOUT COMBINING COMMANDS
        # ---
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1,
            "without",
            "user",
            raw,
            wikibase=self.api_mocker.wikibase,
            combine_commands=False,
        )
        batch.run()
        commands = batch.commands()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].response_id, "Q123")  # with API connection
        self.assertEqual(commands[1].response_id, "Q123$abcdef")  # with API connection
        self.assertEqual(commands[2].response_id, "Q123$abcdef")  # with API connection
        self.assertEqual(commands[3].response_id, "Q123$abcdef")  # with API connection
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command.status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_combine_failed_data_type_should_fail(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.property_data_type(mocker, "P11", "string")
        self.api_mocker.add_statement_successful(mocker, "Q1", {"id": "Q1$abcdef"})
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
        self.assertIsNone(commands[0].response_id)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertIsNone(commands[1].response_id)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertIsNone(commands[2].response_id)
        self.assertEqual(len(commands), 3)

    @requests_mock.Mocker()
    def test_create_and_last_should_combine(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.create_item(mocker, "Q123")
        self.api_mocker.item_empty(mocker, "Q123")
        self.api_mocker.property_data_type(mocker, "P11", "string")
        self.api_mocker.add_statement_successful(mocker, "Q123", {"id": "Q123$abcdef"})
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
        self.assertIsNone(commands[0].response_id)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].response_id, "Q123")
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertIsNone(commands[2].response_id)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[3].response_id, "Q123")
        self.assertEqual(commands[4].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[4].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertIsNone(commands[4].response_id)
        self.assertEqual(commands[5].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[5].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertIsNone(commands[5].response_id)
        self.assertEqual(commands[6].status, BatchCommand.STATUS_ERROR)
        self.assertIsNone(commands[6].response_id)
        self.assertEqual(len(commands), 7)
        # ---
        # WITHOUT COMBINING COMMANDS
        # ---
        v1 = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            v1,
            "without",
            "user",
            raw,
            wikibase=self.api_mocker.wikibase,
            combine_commands=False,
        )
        batch.run()
        commands = batch.commands()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(commands[0].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[0].error, BatchCommand.Error.LAST_NOT_EVALUATED)
        self.assertIsNone(commands[0].response_id)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[1].response_id, "Q123")
        self.assertEqual(commands[2].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[2].response_id, "Q123")
        self.assertEqual(commands[3].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[3].response_id, "Q123$abcdef")
        self.assertEqual(commands[4].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[4].response_id, "Q123")
        self.assertEqual(commands[5].status, BatchCommand.STATUS_DONE)
        self.assertEqual(commands[5].response_id, "Q123$abcdef")
        self.assertEqual(commands[6].status, BatchCommand.STATUS_ERROR)
        self.assertIsNone(commands[6].response_id)
        self.assertEqual(len(commands), 7)

    @requests_mock.Mocker()
    def test_create_and_last_with_failure(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P11", "string")
        self.api_mocker.create_item_failed_server(mocker)
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
        self.assertIsNone(commands[0].response_id)
        self.assertEqual(commands[1].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[1].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertIsNone(commands[1].response_id)
        self.assertEqual(commands[2].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[2].error, BatchCommand.Error.COMBINING_COMMAND_FAILED)
        self.assertIsNone(commands[2].response_id)
        self.assertEqual(commands[3].status, BatchCommand.STATUS_ERROR)
        self.assertEqual(commands[3].error, BatchCommand.Error.API_SERVER_ERROR)
        self.assertIsNone(commands[3].response_id)
        self.assertEqual(len(commands), 4)

    @requests_mock.Mocker()
    def test_batch_wont_verify_commands_already_verified(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.property_data_type(mocker, "P1", "string")
        self.api_mocker.property_data_type(mocker, "P2", "quantity")
        self.api_mocker.patch_item_successful(mocker, "Q1", {})

        with mock.patch("core.models.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
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
            batch = BatchFactory.load_from_parser(v1, "now it will", "user", raw)
            batch.block_on_errors = True
            batch.wikibase = self.api_mocker.wikibase
            batch.run()
            commands = batch.commands()
            self.assertEqual(batch.status, Batch.STATUS_BLOCKED)

            expected = {
                0: BatchCommand.STATUS_INITIAL,
                1: BatchCommand.STATUS_INITIAL,
                2: BatchCommand.STATUS_ERROR,
                3: BatchCommand.STATUS_INITIAL,
            }

            for idx, status in expected.items():
                command = commands[idx]
                self.assertEqual(
                    command.status, status, f"command is {command.get_status_display()}"
                )

    @requests_mock.Mocker()
    def test_batch_will_skip_done_commands(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.create_item(mocker, "Q3")
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
        self.assertEqual(commands[1].entity_id, "LAST")

    @requests_mock.Mocker()
    def test_batch_estimated_runtime(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.create_item(mocker, "Q3")
        v1 = V1CommandParser()
        raw1 = "||".join(["CREATE" for _ in range (90)])
        BatchFactory.load_from_parser(
            v1,
            "without",
            "user",
            raw1,
            wikibase=self.api_mocker.wikibase,
        )
        raw2 = "||".join(["CREATE" for _ in range (180)])
        BatchFactory.load_from_parser(
            v1,
            "without",
            "user",
            raw2,
            wikibase=self.api_mocker.wikibase,
        )
        batches = Batch.objects.for_send_batches()
        batch1, batch2 = batches
        self.assertEqual(batch1.estimated_runtime, 60)
        self.assertEqual(batch2.estimated_runtime, 120)
        self.assertEqual(batch1.estimated_runtime_total, 60)
        self.assertEqual(batch2.estimated_runtime_total, 180)
        self.assertEqual(len(batch1.previous_batches_to_run()), 0)
        self.assertEqual(len(batch2.previous_batches_to_run()), 1)
        self.assertEqual(batch2.previous_batches_to_run()[0].id, batch1.id)
        batch1.block_is_not_autoconfirmed()
        self.assertIsNone(batch1.estimated_runtime)
        self.assertEqual(batch2.estimated_runtime, 120)
        self.assertIsNone(batch1.estimated_runtime_total)
        self.assertEqual(batch2.estimated_runtime_total, 120)
