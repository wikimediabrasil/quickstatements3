from datetime import timedelta

import requests_mock
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache as django_cache
from django.test import TestCase, override_settings
from django.utils.timezone import now

from core.exceptions import (
    InvalidPropertyValueType,
    NonexistantPropertyOrNoDataType,
    NoValueTypeForThisDataType,
    ServerError,
    UnauthorizedToken,
)
from core.factories import TokenFactory, UserFactory, WikibaseFactory, BatchFactory
from core.models import BatchCommand, Client, Token, Label
from core.parsers.v1 import V1CommandParser


class ApiMocker:
    WIKIDATA_PROPERTY_DATA_TYPES = {
        "commonsMedia": "string",
        "geo-shape": "string",
        "tabular-data": "string",
        "url": "string",
        "external-id": "string",
        "wikibase-item": "wikibase-entityid",
        "wikibase-property": "wikibase-entityid",
        "globe-coordinate": "globecoordinate",
        "monolingualtext": "monolingualtext",
        "quantity": "quantity",
        "string": "string",
        "time": "time",
        "musical-notation": "string",
        "math": "string",
        "wikibase-lexeme": "wikibase-entityid",
        "wikibase-form": "wikibase-entityid",
        "wikibase-sense": "wikibase-entityid",
        "entity-schema": "wikibase-entityid",
    }

    def __init__(self):
        self.wikibase = WikibaseFactory()

    @property
    def oauth_profile_endpoint(self):
        return settings.OAUTH_PROFILE_URL

    @property
    def oauth_token_endpoint(self):
        return settings.OAUTH_ACCESS_TOKEN_URL

    def access_token(self, mocker, full_token):
        mocker.post(
            self.oauth_token_endpoint,
            json=full_token,
            status_code=200,
        )

    def access_token_fails(self, mocker):
        mocker.post(
            self.oauth_token_endpoint,
            json={"error": "error"},
            status_code=500,
        )

    def login_success(self, mocker, username):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"username": username},
            status_code=200,
        )

    def login_fail(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"error": "access denied"},
            status_code=401,
        )

    def login_failed_server(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"error": "server error"},
            status_code=500,
        )

    def is_autoconfirmed(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"groups": ["*", "autoconfirmed"]},
            status_code=200,
        )

    def is_blocked(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"groups": ["*", "autoconfirmed"], "blocked": True},
            status_code=200,
        )

    def is_not_autoconfirmed(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"groups": ["*"]},
            status_code=200,
        )

    def autoconfirmed_failed_unauthorized(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"error": "unauthorized"},
            status_code=401,
        )

    def autoconfirmed_failed_server(self, mocker):
        mocker.get(
            self.oauth_profile_endpoint,
            json={"error": "server error"},
            status_code=500,
        )

    def wikibase_url(self, endpoint):
        return f"{self.wikibase.v1_endpoint}{endpoint}"

    def property_data_type(self, mocker, property_id, data_type):
        mocker.get(
            self.wikibase_url(f"/entities/properties/{property_id}"),
            json={"data_type": data_type},
            status_code=200,
        )

    def item(self, mocker, item_id, item_json):
        mocker.get(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json=item_json,
            status_code=200,
        )

    def item_empty(self, mocker, item_id):
        EMPTY_ITEM = {
            "type": "item",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "statements": {},
            "sitelinks": {},
            "id": item_id,
        }
        mocker.get(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json=EMPTY_ITEM,
            status_code=200,
        )

    def property_data_type_not_found(self, mocker, property_id):
        mocker.get(
            self.wikibase_url(f"/entities/properties/{property_id}"),
            json={"code": "property-not-found"},
            status_code=404,
        )

    def create_item_failed_server(self, mocker):
        mocker.post(
            self.wikibase_url("/entities/items"),
            json={"error": "my-error-code"},
            status_code=500,
        )

    def patch_item_successful(self, mocker, item_id, json_result):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json=json_result,
            status_code=200,
        )

    def patch_item_fail(self, mocker, item_id, status_code, json_result):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json=json_result,
            status_code=status_code,
        )

    def add_statement_successful(self, mocker, item_id, response_json=None):
        response_json = (
            response_json if response_json else {"id": f"{item_id}$somestuff"}
        )
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json=response_json,
            status_code=200,
        )

    def add_statement_failed_server(self, mocker, item_id):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json={"error": "my-error-code"},
            status_code=500,
        )

    def delete_statement_sucessful(self, mocker, statement_id):
        mocker.delete(
            self.wikibase_url(f"/statements/{statement_id}"),
            json="Statement deleted",
            status_code=200,
        )

    def delete_statement_fail(self, mocker, statement_id):
        mocker.delete(
            self.wikibase_url(f"/statements/{statement_id}"),
            json="Unknown error",
            status_code=500,
        )

    def statements(self, mocker, item_id, statements):
        mocker.get(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json={"statements": statements},
            status_code=200,
        )

    def sitelink_success(self, mocker, item_id, sitelink, value):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json={
                "sitelinks": {
                    sitelink: {
                        "title": value,
                        "badges": [],
                        "url": "ignored",
                    }
                }
            },
            status_code=200,
        )

    def sitelink_invalid(self, mocker, item_id, sitelink):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json={
                "code": "invalid-path-parameter",
                "message": "Invalid path parameter: 'site_id'",
                "context": {"parameter": "site_id"},
            },
            status_code=400,
        )

    def sitelinks(self, mocker, item_id, sitelinks):
        mocker.get(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json={"sitelinks": sitelinks},
            status_code=200,
        )

    def remove_sitelink_success(self, mocker, item_id, sitelink):
        mocker.patch(
            self.wikibase_url(f"/entities/items/{item_id}"),
            json="Sitelink deleted",
            status_code=200,
        )

    def labels(self, mocker, client, labels: dict):
        res_json = {"entities": {}}
        for id, labels in labels.items():
            res_json["entities"].setdefault(id, {})
            res_json["entities"][id]["labels"] = {
                language: {"language": language, "value": value}
                for language, value in labels.items()
            }
        mocker.get(
            client.action_api_url,
            json=res_json,
            status_code=200,
        )

    def create_item(self, mocker, item_id):
        mocker.post(
            self.wikibase_url("/entities/items"),
            json={"id": item_id},
            status_code=200,
        )

    def property_data_types(self, mocker, mapper):
        mocker.get(
            self.wikibase_url("/property-data-types"),
            json=mapper,
            status_code=200,
        )

    def wikidata_property_data_types(self, mocker):
        self.property_data_types(
            mocker,
            self.WIKIDATA_PROPERTY_DATA_TYPES,
        )


class OAuthClientTests(TestCase):
    def setUp(self):
        self.api_mocker = ApiMocker()
        self.wikibase = self.api_mocker.wikibase

    @requests_mock.Mocker()
    def test_refresh_expired_token(self, mocker):
        # Replacing microseconds to zero for ease of use when comparing
        # because microseconds aren't saved in the database.
        old_expires = now().replace(microsecond=0)
        new_expires = (now() + timedelta(hours=1)).replace(microsecond=0)
        self.api_mocker.login_success(mocker, "WikiUser")
        self.api_mocker.access_token(
            mocker,
            {
                "refresh_token": "new_refresh",
                "access_token": "new_access",
                "expires_at": new_expires.timestamp(),
            },
        )
        old_token = {
            "access_token": "old_access",
            "refresh_token": "old_refresh",
            "expires_at": old_expires.timestamp(),
        }
        user = User.objects.create(username="u")
        t = Token.objects.create_from_full_token(user, old_token)
        client = Client(token=t, wikibase=self.wikibase)
        self.assertTrue(client.token.is_expired())
        self.assertEqual(client.token.user.id, user.id)
        self.assertEqual(client.token.value, "old_access")
        self.assertEqual(client.token.refresh_token, "old_refresh")
        self.assertEqual(client.token.expires_at, old_expires)
        username = client.get_username()
        self.assertEqual(username, "WikiUser")
        self.assertEqual(client.token, t)
        self.assertFalse(client.token.is_expired())
        self.assertEqual(client.token.user.id, user.id)
        self.assertEqual(client.token.value, "new_access")
        self.assertEqual(client.token.refresh_token, "new_refresh")
        self.assertEqual(client.token.expires_at, new_expires)
        username = client.get_username()
        self.assertEqual(username, "WikiUser")
        self.assertEqual(client.token, t)
        self.assertFalse(client.token.is_expired())
        self.assertEqual(client.token.user.id, user.id)
        self.assertEqual(client.token.value, "new_access")
        self.assertEqual(client.token.refresh_token, "new_refresh")
        self.assertEqual(client.token.expires_at, new_expires)

    @requests_mock.Mocker()
    def test_dont_refresh_token(self, mocker):
        expires = (now() + timedelta(hours=2)).replace(microsecond=0)
        self.api_mocker.login_success(mocker, "WikiUser")
        self.api_mocker.access_token_fails(mocker)
        token = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": expires.timestamp(),
        }
        user = User.objects.create(username="u")
        t = Token.objects.create_from_full_token(user, token)
        client = Client(token=t, wikibase=self.wikibase)
        self.assertFalse(client.token.is_expired())
        self.assertEqual(client.token.user.id, user.id)
        self.assertEqual(client.token.value, "access")
        self.assertEqual(client.token.refresh_token, "refresh")
        self.assertEqual(client.token.expires_at, expires)
        username = client.get_username()
        self.assertEqual(username, "WikiUser")
        self.assertFalse(client.token.is_expired())
        self.assertEqual(client.token.user.id, user.id)
        self.assertEqual(client.token.value, "access")
        self.assertEqual(client.token.refresh_token, "refresh")
        self.assertEqual(client.token.expires_at, expires)

    @requests_mock.Mocker()
    def test_failed_to_refresh_raises_unauthorized_token(self, mocker):
        expires = now().replace(microsecond=0)
        self.api_mocker.login_success(mocker, "WikiUser")
        self.api_mocker.access_token_fails(mocker)
        old_token = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": expires.timestamp(),
        }
        user = User.objects.create(username="u")
        t = Token.objects.create_from_full_token(user, old_token)
        client = Client(token=t, wikibase=self.wikibase)
        self.assertTrue(client.token.is_expired())
        with self.assertRaises(UnauthorizedToken):
            client.get_username()


class ClientTests(TestCase):
    def setUp(self):
        self.api_mocker = ApiMocker()

    def tearDown(self):
        # this is needed for the property-data-types to work correctly,
        # since it uses the cache
        django_cache.clear()

    def api_client(self):
        user, _ = User.objects.get_or_create(username="test_token_user")
        token, _ = Token.objects.get_or_create(user=user, value="TEST_TOKEN")
        return Client(token=token, wikibase=self.api_mocker.wikibase)

    def wikibase_url(self, endpoint):
        return f"{self.wikibase.v1_endpoint}{endpoint}"

    def test_wikibase_entity_endpoint(self):
        client = self.api_client()
        self.assertEqual(
            client.wikibase_entity_endpoint("Q123", "/labels"),
            "/entities/items/Q123/labels",
        )
        self.assertEqual(
            client.wikibase_entity_endpoint("P444", "/statements"),
            "/entities/properties/P444/statements",
        )

    def test_wikibase_entity_url(self):
        client = self.api_client()
        self.assertEqual(
            client.wikibase_entity_url("P987", "/statements"),
            f"{client.wikibase_v1_endpoint}/entities/properties/P987/statements",
        )

    @requests_mock.Mocker()
    def test_get_property_value_type(self, mocker):
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P1104", "quantity")
        value_type = self.api_client().get_property_value_type("P1104")
        self.assertEqual(value_type, "quantity")

    @requests_mock.Mocker()
    def test_get_property_value_type_error(self, mocker):
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type_not_found(mocker, "P321341234")
        with self.assertRaises(NonexistantPropertyOrNoDataType):
            self.api_client().get_property_value_type("P321341234")

    @requests_mock.Mocker()
    def test_no_value_type_for_a_data_type(self, mocker):
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P1", "idonotexist")
        with self.assertRaises(KeyError):
            self.api_client().data_type_to_value_type("idonotexist")
        with self.assertRaises(NoValueTypeForThisDataType):
            self.api_client().get_property_value_type("P1")

    @requests_mock.Mocker()
    def test_verify_value_type(self, mocker):
        self.api_mocker.wikidata_property_data_types(mocker)
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

        client = self.api_client()

        all_value_types = (
            "globecoordinate",
            "monolingualtext",
            "quantity",
            "string",
            "time",
            "wikibase-entityid",
        )

        correct_value_types = {
            "P1": "string",
            "P2": "string",
            "P3": "string",
            "P4": "string",
            "P5": "string",
            "P6": "wikibase-entityid",
            "P7": "wikibase-entityid",
            "P8": "globecoordinate",
            "P9": "monolingualtext",
            "P10": "quantity",
            "P11": "string",
            "P12": "time",
            "P13": "string",
            "P14": "string",
            "P15": "wikibase-entityid",
            "P16": "wikibase-entityid",
            "P17": "wikibase-entityid",
            "P18": "wikibase-entityid",
        }

        for i in range(18):
            property_id = f"P{i + 1}"
            client.verify_value_type(property_id, correct_value_types[property_id])

        for i in range(18):
            property_id = f"P{i + 1}"
            for v in all_value_types:
                if v != correct_value_types[property_id]:
                    with self.assertRaises(InvalidPropertyValueType):
                        client.verify_value_type(property_id, v)

    @requests_mock.Mocker()
    def test_is_autoconfirmed(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        client = self.api_client()
        self.assertTrue(client.get_is_autoconfirmed())

    @requests_mock.Mocker()
    def test_is_not_autoconfirmed(self, mocker):
        self.api_mocker.is_not_autoconfirmed(mocker)
        client = self.api_client()
        self.assertFalse(client.get_is_autoconfirmed())

    @requests_mock.Mocker()
    def test_autoconfirmed_failed(self, mocker):
        self.api_mocker.autoconfirmed_failed_server(mocker)
        client = self.api_client()
        with self.assertRaises(ServerError):
            client.get_is_autoconfirmed()

    @requests_mock.Mocker()
    def test_autoconfirmed_unauthorized(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        client = self.api_client()
        with self.assertRaises(UnauthorizedToken):
            client.get_is_autoconfirmed()

    @requests_mock.Mocker()
    def test_login(self, mocker):
        self.api_mocker.login_success(mocker, "username")
        client = self.api_client()
        self.assertEqual(client.get_username(), "username")

    @requests_mock.Mocker()
    def test_login_unauthorized(self, mocker):
        self.api_mocker.login_fail(mocker)
        client = self.api_client()
        with self.assertRaises(UnauthorizedToken):
            client.get_profile()
        with self.assertRaises(UnauthorizedToken):
            client.get_username()
        with self.assertRaises(UnauthorizedToken):
            client.get_user_groups()
        with self.assertRaises(UnauthorizedToken):
            client.get_is_autoconfirmed()

    @requests_mock.Mocker()
    def test_login_failed_server(self, mocker):
        self.api_mocker.login_failed_server(mocker)
        client = self.api_client()
        with self.assertRaises(ServerError):
            client.get_profile()
        with self.assertRaises(ServerError):
            client.get_username()
        with self.assertRaises(ServerError):
            client.get_user_groups()
        with self.assertRaises(ServerError):
            client.get_is_autoconfirmed()

    @requests_mock.Mocker()
    def test_arbitrary_property_data_types(self, mocker):
        mapper = {"data1": "value1", "data2": "value2"}
        self.api_mocker.property_data_types(mocker, mapper)

        client = self.api_client()
        self.assertEqual(client.get_property_data_types(), mapper)

        # ---

        self.api_mocker.property_data_type(mocker, "P1", "data1")
        self.api_mocker.property_data_type(mocker, "P2", "data2")

        client.verify_value_type("P1", "value1")
        client.verify_value_type("P2", "value2")

        # ---

        with self.assertRaises(InvalidPropertyValueType):
            client.verify_value_type("P1", "value2")

        with self.assertRaises(InvalidPropertyValueType):
            client.verify_value_type("P2", "value1")

        with self.assertRaises(InvalidPropertyValueType):
            client.verify_value_type("P2", "abcdef")

        # ---

        # not present in mapper:
        self.api_mocker.property_data_type(mocker, "P3", "data3")

        with self.assertRaises(NoValueTypeForThisDataType):
            client.verify_value_type("P3", "value3")

    @requests_mock.Mocker()
    def test_headers(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        client = self.api_client()
        headers = {
            "User-Agent": "QuickStatements 3.0",
            "Authorization": "Bearer TEST_TOKEN",
            "Content-Type": "application/json",
        }
        self.assertEqual(client.headers(), headers)


class TestBatchCommand(TestCase):
    def setUp(self):
        self.api_mocker = ApiMocker()
        self.wikibase = self.api_mocker.wikibase
        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.client.force_login(self.user)
        self.api_client = Client(token=self.token, wikibase=self.wikibase)

    def test_api_payload(self):
        payload = BatchCommand().api_payload(self.api_client)
        self.assertEqual(payload, {})
        payload = BatchCommand(
            operation=BatchCommand.Operation.CREATE_ITEM
        ).api_payload(self.api_client)
        self.assertEqual(payload, {"item": {}})

    @override_settings(TOOLFORGE_TOOL_NAME="qs-dev")
    def test_api_body(self):
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(parser, "b", "u", "CREATE /* hello */")
        batch_id = batch.id
        cmd = batch.commands()[0]
        comment = f"QuickStatements 3.0 [[:toollabs:qs-dev/batch/{batch_id}|batch #{batch_id}]]: hello"
        self.assertEqual(
            cmd.api_body(self.api_client),
            {
                "item": {},
                "bot": False,
                "comment": comment,
            },
        )

    @requests_mock.Mocker()
    def test_send_create_item(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.create_item(mocker, "Q5")
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(parser, "b", "u", "CREATE||LAST|P1|Q1")
        cmd: BatchCommand = batch.commands()[0]
        cmd.run(self.api_client)
        self.assertEqual(cmd.operation, BatchCommand.Operation.CREATE_ITEM)
        self.assertEqual(cmd.status, BatchCommand.STATUS_DONE)
        self.assertEqual(cmd.response_id, "Q5")

    @requests_mock.Mocker()
    def test_send_create_property(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "b", "u", "CREATE_PROPERTY|wikibase-item||LAST|P1|Q1"
        )
        cmd: BatchCommand = batch.commands()[0]
        cmd.run(self.api_client)
        self.assertEqual(cmd.operation, BatchCommand.Operation.CREATE_PROPERTY)
        self.assertEqual(cmd.status, BatchCommand.STATUS_ERROR)
        self.assertEqual(cmd.error, BatchCommand.Error.OP_NOT_IMPLEMENTED)
        self.assertIsNone(cmd.response_id)
        with self.assertRaises(NotImplementedError):
            cmd.send_to_api(self.api_client)
