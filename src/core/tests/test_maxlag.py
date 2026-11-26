from unittest import mock

import requests_mock
from django.core.cache import cache
from django.test import TestCase, override_settings

from core import maxlag
from core.factories import TokenFactory, UserFactory, BatchFactory
from core.models import Batch, BatchCommand
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker


def lag_response(lag):
    return {
        "error": {
            "code": "maxlag",
            "info": f"Waiting for all: {lag} seconds lagged.",
            "host": "all",
            "lag": lag,
            "type": "wikibase-queryservice",
        }
    }


@override_settings(MAXLAG_PAUSE_ENABLED=True, MAXLAG_THRESHOLD=5, MAXLAG_CHECK_INTERVAL=15)
class MaxlagTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api_mocker = ApiMocker()
        self.api_url = self.api_mocker.wikibase.api_endpoint

    def tearDown(self):
        cache.clear()

    @requests_mock.Mocker()
    def test_fetch_lag_from_maxlag_error(self, mocker):
        mocker.get(self.api_url, json=lag_response(7.5))
        self.assertEqual(maxlag.fetch_lag(self.api_url), 7.5)
        query = mocker.last_request.qs
        self.assertEqual(query["maxlag"], ["-1"])
        self.assertEqual(query["action"], ["query"])

    @requests_mock.Mocker()
    def test_fetch_lag_without_error_is_zero(self, mocker):
        mocker.get(self.api_url, json={"batchcomplete": "", "query": {}})
        self.assertEqual(maxlag.fetch_lag(self.api_url), 0.0)

    @requests_mock.Mocker()
    def test_fetch_lag_unknown_on_failure(self, mocker):
        mocker.get(self.api_url, text="<html>not json</html>", status_code=503)
        self.assertIsNone(maxlag.fetch_lag(self.api_url))

    @requests_mock.Mocker()
    def test_fetch_lag_unknown_on_other_error(self, mocker):
        mocker.get(self.api_url, json={"error": {"code": "internal_api_error"}})
        self.assertIsNone(maxlag.fetch_lag(self.api_url))

    @requests_mock.Mocker()
    def test_get_lag_is_cached(self, mocker):
        mocker.get(self.api_url, json=lag_response(1))
        self.assertEqual(maxlag.get_lag(self.api_url), 1.0)
        self.assertEqual(maxlag.get_lag(self.api_url), 1.0)
        self.assertEqual(mocker.call_count, 1)

        cache.clear()  # as if the check interval had passed
        mocker.get(self.api_url, json=lag_response(2))
        self.assertEqual(maxlag.get_lag(self.api_url), 2.0)
        self.assertEqual(mocker.call_count, 2)

    @requests_mock.Mocker()
    def test_is_lagged(self, mocker):
        mocker.get(self.api_url, json=lag_response(5))
        self.assertEqual(maxlag.is_lagged(self.api_url), (False, 5.0))
        cache.clear()
        mocker.get(self.api_url, json=lag_response(5.1))
        self.assertEqual(maxlag.is_lagged(self.api_url), (True, 5.1))

    @requests_mock.Mocker()
    def test_is_not_lagged_when_lag_unknown(self, mocker):
        mocker.get(self.api_url, status_code=500, text="error")
        self.assertEqual(maxlag.is_lagged(self.api_url), (False, None))

    @override_settings(MAXLAG_PAUSE_ENABLED=False)
    @requests_mock.Mocker()
    def test_disabled_does_not_query(self, mocker):
        self.assertEqual(maxlag.is_lagged(self.api_url), (False, None))
        self.assertEqual(mocker.call_count, 0)


@override_settings(MAXLAG_PAUSE_ENABLED=True, MAXLAG_THRESHOLD=5, MAXLAG_CHECK_INTERVAL=15)
class BatchMaxlagTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api_mocker = ApiMocker()
        self.api_url = self.api_mocker.wikibase.api_endpoint
        self.user = UserFactory(username="user")
        self.token = TokenFactory(user=self.user)

    def tearDown(self):
        cache.clear()

    def parse(self, text):
        return BatchFactory.load_from_parser(
            V1CommandParser(), "Test", "user", text, wikibase=self.api_mocker.wikibase
        )

    def mock_batch_apis(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P65", "quantity")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.add_statement_successful(mocker, "Q1234")

    def edits(self, mocker):
        return [r for r in mocker.request_history if r.method != "GET"]

    @requests_mock.Mocker()
    def test_runs_normally_when_not_lagged(self, mocker):
        self.mock_batch_apis(mocker)
        mocker.get(self.api_url, json=lag_response(0.5))

        batch = self.parse("Q1234|P65|32")
        with mock.patch("core.models.time.sleep") as sleep:
            batch.run()

        sleep.assert_not_called()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(batch.commands()[0].status, BatchCommand.STATUS_DONE)

    @requests_mock.Mocker()
    def test_pauses_until_lag_drops(self, mocker):
        self.mock_batch_apis(mocker)
        mocker.get(
            self.api_url,
            [{"json": lag_response(12)}, {"json": lag_response(8)}, {"json": lag_response(1)}],
        )

        batch = self.parse("Q1234|P65|32")
        messages = []

        def fake_sleep(seconds):
            # No edit is sent while paused
            self.assertEqual(self.edits(mocker), [])
            batch.refresh_from_db()
            messages.append(batch.message)
            self.assertEqual(batch.status, Batch.STATUS_RUNNING)
            # Expire the cache so the next check fetches a new value
            cache.clear()

        with mock.patch("core.models.time.sleep", side_effect=fake_sleep) as sleep:
            batch.run()

        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(15)
        self.assertIn("12.0s", messages[0])
        self.assertIn("8.0s", messages[1])
        self.assertEqual(batch.status, Batch.STATUS_DONE)
        self.assertEqual(batch.commands()[0].status, BatchCommand.STATUS_DONE)
        self.assertEqual(len(self.edits(mocker)), 1)

    @requests_mock.Mocker()
    def test_stop_while_paused(self, mocker):
        self.mock_batch_apis(mocker)
        mocker.get(self.api_url, json=lag_response(30))

        batch = self.parse("Q1234|P65|32")

        def stop_during_sleep(seconds):
            Batch.objects.filter(pk=batch.pk).update(status=Batch.STATUS_STOPPED)

        with mock.patch("core.models.time.sleep", side_effect=stop_during_sleep):
            batch.run()

        batch.refresh_from_db()
        self.assertEqual(batch.status, Batch.STATUS_STOPPED)
        self.assertEqual(batch.commands()[0].status, BatchCommand.STATUS_INITIAL)
        self.assertEqual(self.edits(mocker), [])

    @requests_mock.Mocker()
    def test_runs_when_lag_unknown(self, mocker):
        self.mock_batch_apis(mocker)
        mocker.get(self.api_url, status_code=500, text="error")

        batch = self.parse("Q1234|P65|32")
        with mock.patch("core.models.time.sleep") as sleep:
            batch.run()

        sleep.assert_not_called()
        self.assertEqual(batch.status, Batch.STATUS_DONE)
