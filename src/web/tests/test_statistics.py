import requests_mock
from django.contrib.auth.models import User
from django.test import TestCase
from django.core.cache import cache

from core.factories import TokenFactory, UserFactory
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker


class ProfileTest(TestCase):
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
        v1 = V1CommandParser()
        batch = v1.parse("Test", "wiki", "CREATE||LAST|P1|Q1||LAST|P1|Q2")
        batch.combine_commands = True
        batch.wikibase = api_mocker.wikibase
        batch.save_batch_and_preview_commands()
        batch.run()
        batch = v1.parse("Test", "wiki", "CREATE||LAST|P1|Q5")
        batch.combine_commands = True
        batch.wikibase = api_mocker.wikibase
        batch.save_batch_and_preview_commands()
        batch.run()
        batch = v1.parse("Test", "ikiw", "CREATE||LAST|P1|Q1||LAST|P1|Q2")
        batch.combine_commands = True
        batch.wikibase = api_mocker.wikibase
        batch.save_batch_and_preview_commands()
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
