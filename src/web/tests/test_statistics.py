from datetime import timedelta

import requests_mock
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.core.cache import cache
from django.utils.timezone import now

from core.factories import TokenFactory, UserFactory, BatchFactory
from core.models import Batch
from core.models import BatchCommand
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker


class ProfileTest(TransactionTestCase):
    def assertInRes(self, substring, response):
        """Checks if a substring is contained in response content"""
        self.assertIn(substring.lower(), str(response.content).lower().strip())

    def test_empty(self):
        user = User.objects.create_user(username="john")
        self.client.force_login(user)
        response = self.client.get("/statistics/counters/")
        self.assertTemplateUsed(response, "statistics_all_time_counters.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["batches_count"], 0)
        self.assertEqual(response.context["commands_count"], 0)
        self.assertEqual(response.context["average_commands_per_batch"], 0)
        self.assertEqual(response.context["items_created"], 0)
        self.assertEqual(response.context["editors"], 0)
        self.assertEqual(response.context["edits"], 0)
        response = self.client.get("/statistics/counters/john/")
        self.assertTemplateUsed(response, "statistics_all_time_counters.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["batches_count"], 0)
        self.assertEqual(response.context["commands_count"], 0)
        self.assertEqual(response.context["average_commands_per_batch"], 0)
        self.assertEqual(response.context["items_created"], 0)
        self.assertEqual(response.context["editors"], 0)
        self.assertEqual(response.context["edits"], 0)
        response = self.client.get("/statistics/")
        self.assertTemplateUsed(response, "statistics.html")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/statistics/john/")
        self.assertTemplateUsed(response, "statistics.html")
        self.assertEqual(response.status_code, 200)
        cache.clear()

    @requests_mock.Mocker()
    def test_basic(self, mocker):
        api_mocker = ApiMocker()
        api_mocker.is_autoconfirmed(mocker)
        api_mocker.wikidata_property_data_types(mocker)
        api_mocker.property_data_type(mocker, "P1", "wikibase-item")
        api_mocker.create_item(mocker, "Q123")
        user = UserFactory(username="wiki")
        user2 = UserFactory(username="ikiw")
        TokenFactory(user=user)
        TokenFactory(user=user2)
        parser = V1CommandParser()
        _ignored_batch = BatchFactory.load_from_parser(
            parser,
            "Test",
            "wiki",
            "CREATE||LAST|P1|Q1||LAST|P1|Q2",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
            status=Batch.STATUS_PREVIEW,
        )
        batch = BatchFactory.load_from_parser(
            parser,
            "Test",
            "wiki",
            "CREATE||LAST|P1|Q1||LAST|P1|Q2",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
        )
        batch.run()
        batch = BatchFactory.load_from_parser(
            parser,
            "Test",
            "wiki",
            "CREATE||LAST|P1|Q5",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
        )
        batch.run()
        batch = BatchFactory.load_from_parser(
            parser,
            "Test",
            "ikiw",
            "CREATE||LAST|P1|Q1||LAST|P1|Q2",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
        )
        batch.run()
        self.client.force_login(user)
        response = self.client.get("/statistics/counters/")
        self.assertTemplateUsed(response, "statistics_all_time_counters.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["batches_count"], 3)
        self.assertEqual(response.context["commands_count"], 8)
        self.assertEqual(response.context["average_commands_per_batch"], 3)
        self.assertEqual(response.context["items_created"], 3)
        self.assertEqual(response.context["editors"], 2)
        self.assertEqual(response.context["edits"], 3)
        response = self.client.get("/statistics/counters/wiki/")
        self.assertTemplateUsed(response, "statistics_all_time_counters.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["batches_count"], 2)
        self.assertEqual(response.context["commands_count"], 5)
        self.assertEqual(response.context["average_commands_per_batch"], 2)
        self.assertEqual(response.context["items_created"], 2)
        self.assertEqual(response.context["editors"], 1)
        self.assertEqual(response.context["edits"], 2)
        response = self.client.get("/statistics/counters/ikiw/")
        self.assertTemplateUsed(response, "statistics_all_time_counters.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["batches_count"], 1)
        self.assertEqual(response.context["commands_count"], 3)
        self.assertEqual(response.context["average_commands_per_batch"], 3)
        self.assertEqual(response.context["items_created"], 1)
        self.assertEqual(response.context["editors"], 1)
        self.assertEqual(response.context["edits"], 1)
        response = self.client.get("/statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "statistics.html")
        response = self.client.get("/statistics/wiki/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "statistics.html")
        response = self.client.get("/statistics/ikiw/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "statistics.html")
        cache.clear()

    @requests_mock.Mocker()
    def test_old_commands_are_cached(self, mocker):
        api_mocker = ApiMocker()
        api_mocker.is_autoconfirmed(mocker)
        api_mocker.wikidata_property_data_types(mocker)
        api_mocker.property_data_type(mocker, "P1", "wikibase-item")
        api_mocker.create_item(mocker, "Q123")
        user = UserFactory(username="wiki")
        TokenFactory(user=user)
        parser = V1CommandParser()
        old_batch = BatchFactory.load_from_parser(
            parser,
            "Old",
            "wiki",
            "CREATE||LAST|P1|Q1",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
        )
        old_batch.run()
        old_created = now() - timedelta(days=30)
        Batch.objects.filter(pk=old_batch.pk).update(created=old_created)
        BatchCommand.objects.filter(batch=old_batch).update(created=old_created)
        recent_batch = BatchFactory.load_from_parser(
            parser,
            "Recent",
            "wiki",
            "CREATE||LAST|P1|Q5",
            combine_commands=True,
            wikibase=api_mocker.wikibase,
        )
        recent_batch.run()
        self.client.force_login(user)
        response = self.client.get("/statistics/counters/wiki/")
        self.assertEqual(response.context["commands_count"], 4)
        self.assertEqual(response.context["items_created"], 2)
        self.assertEqual(response.context["edits"], 2)
        response = self.client.get("/statistics/plots/wiki/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["editors_and_edits_per_day"]["edits"][-1], 2)
        self.assertEqual(sum(response.context["commands_per_day"]["done"]), 4)
        # old counts are cached, so deleting old commands is not reflected yet
        BatchCommand.objects.filter(batch=old_batch).delete()
        response = self.client.get("/statistics/counters/wiki/?nocache=1")
        self.assertEqual(response.context["commands_count"], 4)
        cache.clear()
        response = self.client.get("/statistics/counters/wiki/?nocache=2")
        self.assertEqual(response.context["commands_count"], 2)
        cache.clear()
