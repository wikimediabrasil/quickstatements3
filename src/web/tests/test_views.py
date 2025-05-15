from unittest import mock

import requests_mock
from django.contrib.auth import get_user
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.factories import BatchFactory
from core.models import Batch, BatchCommand
from core.models import Client as ApiClient
from core.models import Token
from core.parsers.v1 import V1CommandParser
from core.tests.test_api import ApiMocker
from django.core.files.uploadedfile import SimpleUploadedFile


class ViewsTest(TestCase):
    URL_NAME = "profile"
    maxDiff = None

    def setUp(self):
        self.api_mocker = ApiMocker()

    def assertInRes(self, substring, response):
        """Checks if a substring is contained in response content"""
        self.assertIn(substring.lower(), str(response.content).lower().strip())

    def assertNotInRes(self, substring, response):
        """Checks if a substring is not contained in response content"""
        self.assertNotIn(substring.lower(), str(response.content).lower().strip())

    def assertRedirect(self, response):
        """Asserts the response is a redirect response"""
        self.assertEqual(response.status_code, 302)

    def assertRedirectToPath(self, response, path):
        """Asserts the response is a redirect to the specificed path"""
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], path)

    def assertRedirectToUrlName(self, response, url_name):
        """Asserts the response is a redirect to the specificed URL"""
        self.assertRedirectToPath(response, reverse(url_name))

    def get_user(self):
        return get_user(self.client)

    def assertIsAuthenticated(self):
        self.assertTrue(self.get_user().is_authenticated)

    def assertIsNotAuthenticated(self):
        self.assertFalse(self.get_user().is_authenticated)

    def login_user_and_get_token(self, username):
        """
        Creates an user and a test token.

        Returns a tuple with the user object and their API client.
        """
        user = User.objects.create_user(username=username)
        self.client.force_login(user)

        token = Token.objects.create(user=user, value="TEST_TOKEN")
        api_client = ApiClient(token=token, wikibase=self.api_mocker.wikibase)

        return (user, api_client)

    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("index.html")

    def test_batches(self):
        response = self.client.get("/batches")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["location"], "/batches/")

        response = self.client.get("/batches/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [])

    def test_batches_by_user(self):
        response = self.client.get("/batches/mgalves80")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["location"], "/batches/mgalves80/")

        response = self.client.get("/batches/mgalves80/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [])
        self.assertEqual(response.context["username"], "mgalves80")

    def test_non_existing_batch(self):
        response = self.client.get("/batch/123456789")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["location"], "/batch/123456789/")

        response = self.client.get("/batch/123456789/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed("batch_not_found.html")

    def test_existing_batch(self):
        batch = Batch.objects.create(
            name="My new batch", user="mgalves80", wikibase=self.api_mocker.wikibase
        )

        response = self.client.get(f"/batch/{batch.pk}")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["location"], f"/batch/{batch.pk}/")

        response = self.client.get(f"/batch/{batch.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertEqual(response.context["batch"], batch)

        response = self.client.get(f"/batch/{batch.pk}/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch_summary.html")
        self.assertEqual(response.context["pk"], batch.pk)
        self.assertEqual(response.context["status"], "Initial")
        self.assertEqual(response.context["error_count"], 0)
        self.assertEqual(response.context["initial_count"], 0)
        self.assertEqual(response.context["running_count"], 0)
        self.assertEqual(response.context["done_count"], 0)
        self.assertEqual(response.context["total_count"], 0)
        self.assertEqual(response.context["done_percentage"], 0)

        response = self.client.get(f"/batch/{batch.pk}/commands/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch_commands.html")
        self.assertEqual(response.context["batch_pk"], batch.pk)
        self.assertEqual(response.context["only_errors"], False)

    def test_batch_command_filters(self):
        batch = Batch.objects.create(
            name="My new batch", user="mgalves80", wikibase=self.api_mocker.wikibase
        )
        b1 = BatchCommand.objects.create(
            batch=batch,
            index=0,
            action=BatchCommand.ACTION_ADD,
            json={},
            raw="{}",
            status=BatchCommand.STATUS_INITIAL,
        )
        b2 = BatchCommand.objects.create(
            batch=batch,
            index=1,
            action=BatchCommand.ACTION_ADD,
            json={},
            raw="{}",
            status=BatchCommand.STATUS_ERROR,
        )
        b3 = BatchCommand.objects.create(
            batch=batch,
            index=2,
            action=BatchCommand.ACTION_ADD,
            json={},
            raw="{}",
            status=BatchCommand.STATUS_INITIAL,
        )
        b4 = BatchCommand.objects.create(
            batch=batch,
            index=4,
            action=BatchCommand.ACTION_ADD,
            json={},
            raw="{}",
            status=BatchCommand.STATUS_ERROR,
        )

        response = self.client.get(f"/batch/{batch.pk}/commands/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch_commands.html")
        self.assertEqual(response.context["batch_pk"], batch.pk)
        self.assertEqual(response.context["only_errors"], False)
        self.assertEqual(list(response.context["page"].object_list), [b1, b2, b3, b4])
        response = self.client.get(f"/batch/{batch.pk}/commands/?show_errors=1")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch_commands.html")
        self.assertEqual(response.context["batch_pk"], batch.pk)
        self.assertEqual(response.context["only_errors"], True)
        self.assertEqual(list(response.context["page"].object_list), [b2, b4])

    def test_existing_batches(self):
        b1 = Batch.objects.create(name="My new batch", user="mgalves80")
        b2 = Batch.objects.create(name="My new batch", user="mgalves80")
        b3 = Batch.objects.create(name="My new batch", user="wikilover")

        response = self.client.get("/batches/mgalves80/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [b2, b1])
        self.assertEqual(response.context["username"], "mgalves80")

        response = self.client.get("/batches/wikilover/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [b3])
        self.assertEqual(response.context["username"], "wikilover")

        response = self.client.get("/batches/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [b3, b2, b1])

    @requests_mock.Mocker()
    def test_create_v1_batch_logged_user(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")

        # Black box testing. We dont have any batch listed
        response = self.client.get("/batches/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batches.html")
        self.assertEqual(list(response.context["page"].object_list), [])

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            # Creating our new batch
            response = self.client.get("/batch/new/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("new_batch.html")

            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(response.status_code, 302)

            # Lets view the new batch
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)

            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertTemplateUsed("batch.html")
            batch = response.context["batch"]
            self.assertEqual(batch.name, "My v1 batch")
            self.assertTrue(batch.is_initial)
            self.assertEqual(batch.batchcommand_set.count(), 3)

            # Listing again. Now we have something
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [batch])
            self.assertTrue(batch.is_initial)

    @requests_mock.Mocker()
    def test_create_empty_name(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")
            response = self.client.post(
                "/batch/new/", data={"type": "v1", "commands": "CREATE"}
            )
            self.assertEqual(response.status_code, 302)
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)
            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)
            response = self.client.get(response.url)
            self.assertTemplateUsed("batch.html")

    @requests_mock.Mocker()
    def test_create_csv_batch_logged_user(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")

            # Black box testing. We dont have any batch listed
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [])

            # Creating our new batch
            response = self.client.get("/batch/new/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("new_batch.html")

            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My CSV batch",
                    "type": "csv",
                    "commands": "qid,P31,-P31",
                },
            )
            self.assertEqual(response.status_code, 302)

            # Lets view the new batch
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)

            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertTemplateUsed("batch.html")
            batch = response.context["batch"]
            self.assertEqual(batch.name, "My CSV batch")
            self.assertTrue(batch.is_initial)
            self.assertEqual(batch.batchcommand_set.count(), 0)

            # Listing again. Now we have something
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [batch])
            self.assertTrue(batch.is_initial)

    def test_create_batch_anonymous_user(self):
        response = self.client.get("/batch/new/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login/?next=/batch/new/")

        response = self.client.post(
            "/batch/new/",
            data={
                "name": "My v1 batch",
                "type": "v1",
                "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login/?next=/batch/new/")

    @requests_mock.Mocker()
    def test_create_csv_batch_with_file(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")

            # Black box testing. We don't have any batch listed
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [])

            # Creating our new batch
            response = self.client.get("/batch/new/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("new_batch.html")

            # Creating our new batch with a file upload
            mock_file = SimpleUploadedFile(
                "commands.csv", b"qid,P31,-P31", content_type="text/csv"
            )
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My CSV batch with file",
                    "type": "csv",
                    "file": mock_file,
                },
            )
            self.assertEqual(response.status_code, 302)

            # Let's view the new batch
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)

            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertTemplateUsed("batch.html")
            batch = response.context["batch"]
            self.assertEqual(batch.name, "My CSV batch with file")
            self.assertTrue(batch.is_initial)
            self.assertEqual(batch.batchcommand_set.count(), 0)

            # Listing again. Now we have something
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [batch])
            self.assertTrue(batch.is_initial)

    @requests_mock.Mocker()
    def test_create_v1_batch_with_file(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")

            # Black box testing. We don't have any batch listed
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [])

            # Creating our new batch with a file upload
            mock_file = SimpleUploadedFile(
                "commands.v1", b"CREATE||-Q1234|P1|12||Q222|P4|9~0.1", content_type="text/plain"
            )
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My V1 batch with file",
                    "type": "v1",
                    "file": mock_file,
                },
            )

            self.assertEqual(response.status_code, 302)

            # Let's view the new batch
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)

            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertTemplateUsed("batch.html")
            batch = response.context["batch"]
            self.assertEqual(batch.name, "My V1 batch with file")
            self.assertTrue(batch.is_initial)
            self.assertEqual(batch.batchcommand_set.count(), 3)

            # Listing again. Now we have something
            response = self.client.get("/batches/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batches.html")
            self.assertEqual(list(response.context["page"].object_list), [batch])
            self.assertTrue(batch.is_initial)

    def test_create_batch_anonymous_user_with_file(self):
        mock_file = SimpleUploadedFile(
            "commands.csv", b"qid,P31,-P31", content_type="text/csv"
        )
        response = self.client.post(
            "/batch/new/",
            data={
                "name": "Anonymous batch",
                "type": "csv",
                "file": mock_file,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/auth/login/?next=/batch/new/")

    @requests_mock.Mocker()
    def test_profile_is_autoconfirmed(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")
        with mock.patch("web.views.profile.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            res = self.client.get("/auth/profile/")
            self.assertEqual(res.status_code, 200)
            self.assertTemplateUsed("profile.html")
            self.assertEqual(res.context["is_autoconfirmed"], True)
            self.assertEqual(res.context["token_failed"], False)
            self.assertInRes(
                "We have successfully verified that you are an autoconfirmed user.", res
            )

    @requests_mock.Mocker()
    def test_profile_is_not_autoconfirmed(self, mocker):
        self.api_mocker.is_not_autoconfirmed(mocker)
        with mock.patch("web.views.profile.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")
            res = self.client.get("/auth/profile/")
            self.assertEqual(res.status_code, 200)
            self.assertTemplateUsed("profile.html")
            self.assertEqual(res.context["is_autoconfirmed"], False)
            self.assertEqual(res.context["token_failed"], False)
            self.assertInRes("You are not an autoconfirmed user.", res)

    @requests_mock.Mocker()
    def test_profile_autoconfirmed_failed(self, mocker):
        self.api_mocker.autoconfirmed_failed_server(mocker)
        with mock.patch("web.views.profile.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase

            user, api_client = self.login_user_and_get_token("user")
            res = self.client.get("/auth/profile/")
            self.assertEqual(res.status_code, 200)
            self.assertTemplateUsed("profile.html")
            self.assertEqual(res.context["is_autoconfirmed"], False)
            self.assertEqual(res.context["token_failed"], True)
            self.assertInRes("We could not verify you are an autoconfirmed user.", res)

    @requests_mock.Mocker()
    def test_new_batch_is_not_autoconfirmed(self, mocker):
        self.api_mocker.is_not_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")
            res = self.client.get("/batch/new/")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.context["is_autoconfirmed"], False)
            self.assertInRes("Preview", res)
            self.assertInRes("only autoconfirmed users can run batches", res)

    @requests_mock.Mocker()
    def test_new_batch_is_autoconfirmed(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")
        res = self.client.get("/batch/new/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["is_autoconfirmed"], True)
        self.assertInRes("Create", res)
        self.assertNotInRes("only autoconfirmed users can run batches", res)

    @requests_mock.Mocker()
    def test_new_batch_token_expired(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")
            res = self.client.get("/batch/new/")
            self.assertRedirectToUrlName(res, "login")
            self.assertIsNotAuthenticated()
            self.assertTrue(self.client.session["token_expired"])

    @requests_mock.Mocker()
    def test_allow_start_after_create(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/batch/new/preview/")

            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("preview_batch.html")

            response = self.client.get("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 405)
            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["batch"].is_preview)
            self.assertTrue(response.context["batch"].is_initial)

    @requests_mock.Mocker()
    def test_allow_start_after_create_is_not_autoconfirmed(self, mocker):
        self.api_mocker.is_not_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
            res = self.client.post(
                "/batch/new/",
                data={"name": "name", "type": "v1", "commands": "CREATE||LAST|P1|Q1"},
            )
            self.assertEqual(res.status_code, 302)
            res = self.client.get(res.url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.context["is_autoconfirmed"], False)
            self.assertInRes("only autoconfirmed users can run batches", res)
            self.assertInRes(
                """<input type="submit" value="Save and run batch" disabled>""", res
            )

    @requests_mock.Mocker()
    def test_allow_start_after_create_is_blocked(self, mocker):
        self.api_mocker.is_blocked(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase

            res = self.client.post(
                "/batch/new/",
                data={"name": "name", "type": "v1", "commands": "CREATE||LAST|P1|Q1"},
            )
            self.assertEqual(res.status_code, 302)
            res = self.client.get(res.url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.context["is_blocked"], True)
            self.assertInRes(
                "Your account is blocked and you will not be able to run any batches.",
                res,
            )
            self.assertInRes(
                """<input type="submit" value="Save and run batch" disabled>""", res
            )

    @requests_mock.Mocker()
    def test_allow_start_after_create_is_autoconfirmed(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
            res = self.client.post(
                "/batch/new/",
                data={"name": "name", "type": "v1", "commands": "CREATE||LAST|P1|Q1"},
            )
            self.assertEqual(res.status_code, 302)
            res = self.client.get(res.url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.context["is_autoconfirmed"], True)
            self.assertInRes(
                """<input type="submit" value="Save and run batch">""", res
            )
            self.assertNotInRes("only autoconfirmed users can run batches", res)
            self.assertNotInRes(
                """<input type="submit" value="Save and run batch" disabled>""", res
            )

    @requests_mock.Mocker()
    def test_allow_start_after_create_token_expired(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase

            res = self.client.post(
                "/batch/new/",
                data={"name": "name", "type": "v1", "commands": "CREATE||LAST|P1|Q1"},
            )
            self.assertEqual(res.status_code, 302)
            res = self.client.get(res.url)
            self.assertRedirectToUrlName(res, "login")
            self.assertIsNotAuthenticated()
            self.assertTrue(self.client.session["token_expired"])

    @requests_mock.Mocker()
    def test_batch_does_not_call_autoconfirmed_if_not_in_preview(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
            res = self.client.post(
                "/batch/new/",
                data={"name": "name", "type": "v1", "commands": "CREATE||LAST|P1|Q1"},
            )
            self.assertEqual(res.status_code, 302)
            url = res.url
            res = self.client.get(url)
            self.assertEqual(res.context["is_autoconfirmed"], True)
            response = self.client.post("/batch/new/preview/allow_start/")
            batch_url = response.url
            response = self.client.get(batch_url)
            batch = response.context["batch"]
            res = self.client.get(batch_url)
            self.assertEqual(res.context["is_autoconfirmed"], None)
            batch.stop()
            res = self.client.get(batch_url)
            self.assertEqual(res.context["is_autoconfirmed"], None)

    def test_create_block_on_errors(self):
        user = User.objects.create_user(username="john")
        self.client.force_login(user)

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "should NOT block",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            response = self.client.get(response.url)
            self.assertFalse(response.context["batch"].block_on_errors)
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "should block",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                    "block_on_errors": "block_on_errors",
                },
            )
            response = self.client.get(response.url)
            self.assertTrue(response.context["batch"].block_on_errors)

    def test_create_do_not_combine_commands(self):
        user = User.objects.create_user(username="john")
        self.client.force_login(user)

        with mock.patch("web.views.new_batch.get_default_wikibase") as mocked_wikibase:
            mocked_wikibase.return_value = self.api_mocker.wikibase
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "should combine",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            response = self.client.get(response.url)
            self.assertTrue(response.context["batch"].combine_commands)
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "should NOT combine",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                    "do_not_combine_commands": "do_not_combine_commands",
                },
            )
            response = self.client.get(response.url)
            self.assertFalse(response.context["batch"].combine_commands)

    @requests_mock.Mocker()
    def test_restart_after_stopped_buttons(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            user, api_client = self.login_user_and_get_token("user")
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertInRes("Save and run batch", response)

            response = self.client.post("/batch/new/preview/allow_start/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

            batch = response.context["batch"]
            pk = batch.pk

            response = self.client.post(f"/batch/{pk}/stop/")
            response = self.client.get(response.url)
            self.assertInRes("Restart", response)

            response = self.client.post(f"/batch/{pk}/restart/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

    @requests_mock.Mocker()
    def test_rerun_button(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P2", "wikibase-item")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q11")
        self.api_mocker.patch_item_fail(mocker, "Q1234", 418, {"id": "Q1234$stuff"})
        self.api_mocker.patch_item_fail(
            mocker, "Q11", 418, {"id": "Q11", "labels": {"en": "label"}}
        )
        user, api_client = self.login_user_and_get_token("wikiuser")
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser,
            "Batch",
            "wikiuser",
            """Q1234\tP2\tQ1||Q11|Len|"label" """,
            wikibase=self.api_mocker.wikibase,
        )
        pk = batch.pk

        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertNotInRes(
            f"""<form method="POST" action="/batch/{pk}/rerun/">""", response
        )
        self.assertNotInRes(
            """<input class="secondary" type="submit" value="Rerun">""", response
        )

        batch.run()

        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertInRes(
            f"""<form method="POST" action="/batch/{pk}/rerun/">""", response
        )
        self.assertInRes(
            """<input class="secondary" type="submit" value="Rerun">""", response
        )

        response = self.client.post(f"/batch/{pk}/rerun/")
        response = self.client.get(response.url)
        self.assertInRes("Stop execution", response)

    @requests_mock.Mocker()
    def test_batch_preview_commands(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        user, api_client = self.login_user_and_get_token("user")
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            labels = {
                "Q1234": {"en": "English label"},
                "Q222": {"en": "English label"},
            }
            self.api_mocker.labels(mocker, api_client, labels)
            self.api_mocker.labels(mocker, api_client, labels)
            res = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(res.status_code, 302)
            res = self.client.get(res.url)
            self.assertEqual(res.status_code, 200)
            self.assertInRes("Save and run batch", res)
            res = self.client.get("/batch/new/preview/commands/")
            self.assertEqual(res.status_code, 200)

    @requests_mock.Mocker()
    def test_batch_report(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P2", "wikibase-item")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q11")
        self.api_mocker.patch_item_successful(mocker, "Q1234", {"id": "Q1234$stuff"})
        self.api_mocker.patch_item_successful(
            mocker, "Q11", {"id": "Q11", "labels": {"en": "label"}}
        )
        user, api_client = self.login_user_and_get_token("wikiuser")
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", """Q1234\tP2\tQ1||Q11|Len|"label" """
        )
        batch.wikibase = self.api_mocker.wikibase
        pk = batch.pk

        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertNotInRes(
            f"""<form method="GET" action="/batch/{pk}/report/">""", response
        )
        self.assertNotInRes(
            """<input type="submit" value="Download report">""", response
        )

        batch.run()

        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertInRes(
            f"""<form method="GET" action="/batch/{pk}/report/">""", response
        )
        self.assertInRes("""<input type="submit" value="Download report">""", response)

        response = self.client.post(f"/batch/{pk}/report/")
        self.assertEqual(response.status_code, 405)

        response = self.client.get(f"/batch/{pk}/report/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Disposition"],
            f'attachment; filename="batch-{pk}-report.csv"',
        )
        result = (
            """b'batch_id,index,operation,status,error,message,entity_id,raw_input\\r\\n"""
            f"""{pk},0,set_statement,Done,,,Q1234,Q1234|P2|Q1\\r\\n"""
            f"""{pk},1,set_label,Done,,,Q11,"Q11|Len|""label""\"\\r\\n\'"""
        )
        self.assertEqual(result, str(response.content).strip())

    @requests_mock.Mocker()
    def test_batch_summary(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P2", "wikibase-item")
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.patch_item_successful(mocker, "Q1", {})

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            _user, api_client = self.login_user_and_get_token("wikiuser")
            response = self.client.post(
                "/batch/new/",
                data={
                    "type": "v1",
                    "commands": """
                Q1|P2|Q2
                Q1|P2|"string"
                Q1|P2|32
                Q1|P2|Q2
                Q1|P2|32
                """,
                },
            )
            response = self.client.get("/batch/new/preview/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("preview_batch.html")
            self.assertInRes("linear-gradient(to right, green 0%, #C52F21 0)", response)
            response = self.client.post("/batch/new/preview/allow_start/")
            self.assertEqual(response.status_code, 302)
            response = self.client.get(response.url)
            self.assertEqual(response.status_code, 200)
            batch = response.context["batch"]
            pk = batch.pk
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed("batch_summary.html")
            self.assertEqual(response.context["pk"], pk)
            self.assertEqual(response.context["status"], "Initial")
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 5)
            self.assertEqual(response.context["running_count"], 0)
            self.assertEqual(response.context["done_count"], 0)
            self.assertEqual(response.context["error_count"], 0)
            self.assertEqual(response.context["done_percentage"], 0)
            self.assertEqual(response.context["finish_percentage"], 0)
            self.assertEqual(response.context["done_to_finish_percentage"], 0)
            self.assertInRes("linear-gradient(to right, green 0%, #C52F21 0)", response)
            commands = batch.commands()
            commands[0].run(api_client)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 4)
            self.assertEqual(response.context["done_count"], 1)
            self.assertEqual(response.context["error_count"], 0)
            self.assertEqual(response.context["done_percentage"], 20)
            self.assertEqual(response.context["finish_percentage"], 20)
            self.assertEqual(response.context["done_to_finish_percentage"], 100)
            self.assertInRes(
                "linear-gradient(to right, green 100%, #C52F21 0)", response
            )
            commands[1].run(api_client)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 3)
            self.assertEqual(response.context["done_count"], 1)
            self.assertEqual(response.context["error_count"], 1)
            self.assertEqual(response.context["done_percentage"], 20)
            self.assertEqual(response.context["finish_percentage"], 40)
            self.assertEqual(response.context["done_to_finish_percentage"], 50)
            self.assertInRes(
                "linear-gradient(to right, green 50%, #C52F21 0)", response
            )
            commands[2].run(api_client)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 2)
            self.assertEqual(response.context["done_count"], 1)
            self.assertEqual(response.context["error_count"], 2)
            self.assertEqual(response.context["done_percentage"], 20)
            self.assertEqual(response.context["finish_percentage"], 60)
            self.assertEqual(response.context["done_to_finish_percentage"], 33)
            self.assertInRes(
                "linear-gradient(to right, green 33%, #C52F21 0)", response
            )
            commands[3].run(api_client)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 1)
            self.assertEqual(response.context["done_count"], 2)
            self.assertEqual(response.context["error_count"], 2)
            self.assertEqual(response.context["done_percentage"], 40)
            self.assertEqual(response.context["finish_percentage"], 80)
            self.assertEqual(response.context["done_to_finish_percentage"], 50)
            self.assertInRes(
                "linear-gradient(to right, green 50%, #C52F21 0)", response
            )
            commands[4].run(api_client)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 0)
            self.assertEqual(response.context["done_count"], 2)
            self.assertEqual(response.context["error_count"], 3)
            self.assertEqual(response.context["done_percentage"], 40)
            self.assertEqual(response.context["finish_percentage"], 100)
            self.assertEqual(response.context["done_to_finish_percentage"], 40)
            self.assertInRes(
                "linear-gradient(to right, green 40%, #C52F21 0)", response
            )
            batch.run()
            self.assertEqual(len(commands), 5)
            response = self.client.get(f"/batch/{pk}/summary/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["status"], "Done")
            self.assertEqual(response.context["total_count"], 5)
            self.assertEqual(response.context["initial_count"], 0)
            self.assertEqual(response.context["done_count"], 2)
            self.assertEqual(response.context["error_count"], 3)
            self.assertEqual(response.context["done_percentage"], 40)
            self.assertEqual(response.context["finish_percentage"], 100)
            self.assertEqual(response.context["done_to_finish_percentage"], 40)
            self.assertInRes(
                "linear-gradient(to right, green 40%, #C52F21 0)", response
            )

    @requests_mock.Mocker()
    def test_batch_heading_details(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.item_empty(mocker, "Q1")
        self.api_mocker.patch_item_successful(mocker, "Q1", {})
        user, api_client = self.login_user_and_get_token("wikiuser")
        parser = V1CommandParser()
        batch = BatchFactory.load_from_parser(
            parser, "Batch", "wikiuser", """Q11|Len|"label" """
        )
        pk = batch.pk
        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertInRes(
            """<a href="https://www.wikidata.org/wiki/User:wikiuser">wikiuser</a>""",
            response,
        )
        self.assertInRes("""[<a href="/batches/wikiuser/">""", response)
        self.assertInRes(
            f"""<a href="https://editgroups.toolforge.org/b/QSv3/{pk}">""", response
        )
        batch.run()
        response = self.client.get(f"/batch/{pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("batch.html")
        self.assertInRes(
            """<a href="https://www.wikidata.org/wiki/User:wikiuser">wikiuser</a>""",
            response,
        )
        self.assertInRes(
            f"""<a href="https://editgroups.toolforge.org/b/QSv3/{pk}">""", response
        )

    @requests_mock.Mocker()
    def test_batch_stop_permissions(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            admin = User.objects.create_superuser(username="admin")
            other_user, _ = self.login_user_and_get_token("other_user")
            creator, api_client = self.login_user_and_get_token("creator")

            # Creates the batch
            self.client.force_login(creator)
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertInRes("Save and run batch", response)

            response = self.client.post("/batch/new/preview/allow_start/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

            batch = response.context["batch"]
            pk = batch.pk

        def attempt_to_stop(user, authorized):
            batch.status = Batch.STATUS_INITIAL
            batch.save()

            if not user:
                self.client.logout()
            else:
                self.client.force_login(user)

            response = self.client.get(f"/batch/{pk}/")
            self.assertEqual(response.status_code, 200)

            # Checks if the user can access the batch stop option
            if authorized:
                self.assertInRes(
                    """<button class="secondary" onclick="showStopModal();">""",
                    response,
                )
            else:
                self.assertNotInRes(
                    """<button class="secondary" onclick="showStopModal();">""",
                    response,
                )

            return self.client.post(f"/batch/{pk}/stop/")

        # Test as batch creator
        response = attempt_to_stop(creator, authorized=True)
        self.assertEqual(response.status_code, 302)

        # Test as admin
        response = attempt_to_stop(admin, authorized=True)
        self.assertEqual(response.status_code, 302)

        # Test as other user
        response = attempt_to_stop(other_user, authorized=False)
        self.assertEqual(response.status_code, 403)

        # Test as not authenticated user
        response = attempt_to_stop(None, authorized=False)
        self.assertEqual(response.status_code, 403)

    @requests_mock.Mocker()
    def test_batch_restart_permissions(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase

            admin = User.objects.create_superuser(username="admin")
            other_user, _ = self.login_user_and_get_token("other_user")
            creator, api_client = self.login_user_and_get_token("creator")

            # Creates the batch
            self.client.force_login(creator)
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1",
                },
            )
            self.assertEqual(response.status_code, 302)

            response = self.client.get(response.url)
            self.assertInRes("Save and run batch", response)

            response = self.client.post("/batch/new/preview/allow_start/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

            batch = response.context["batch"]
            pk = batch.pk

            response = self.client.post(f"/batch/{pk}/stop/")
            response = self.client.get(response.url)

            def attempt_to_restart(user, authorized):
                batch.status = Batch.STATUS_STOPPED
                batch.save()

                if not user:
                    self.client.logout()
                else:
                    self.client.force_login(user)

                response = self.client.get(f"/batch/{pk}/")
                self.assertEqual(response.status_code, 200)

                # Checks if the user can access the batch stop option
                if authorized:
                    self.assertInRes("Restart", response)
                    self.assertInRes(
                        f"""<form method="POST" action="/batch/{pk}/restart/">""",
                        response,
                    )
                else:
                    self.assertNotInRes("Restart", response)
                    self.assertNotInRes(
                        f"""<form method="POST" action="/batch/{pk}/restart/">""",
                        response,
                    )

                return self.client.post(f"/batch/{pk}/restart/")

            # Test as batch creator
            response = attempt_to_restart(creator, authorized=True)
            self.assertEqual(response.status_code, 302)

            # Test as admin
            response = attempt_to_restart(admin, authorized=True)
            self.assertEqual(response.status_code, 302)

            # Test as other user
            response = attempt_to_restart(other_user, authorized=False)
            self.assertEqual(response.status_code, 403)

            # Test as not authenticated user
            response = attempt_to_restart(None, authorized=False)
            self.assertEqual(response.status_code, 403)

    @requests_mock.Mocker()
    def test_batch_rerun_permissions(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P2", "wikibase-item")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q11")
        self.api_mocker.patch_item_fail(mocker, "Q1234", 418, {"id": "Q1234$stuff"})
        self.api_mocker.patch_item_fail(
            mocker, "Q11", 418, {"id": "Q11", "labels": {"en": "label"}}
        )

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            admin = User.objects.create_superuser(username="admin")
            other_user, _ = self.login_user_and_get_token("other_user")
            creator, api_client = self.login_user_and_get_token("creator")

            self.client.force_login(creator)

            # Creates the batch and runs it
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": """Q1234\tP2\tQ1||Q11|Len|"label" """,
                },
            )
            self.assertEqual(response.status_code, 302)

            response = self.client.post("/batch/new/preview/allow_start/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

            batch = response.context["batch"]
            pk = batch.pk
            self.assertNotInRes(
                f"""<form method="POST" action="/batch/{pk}/rerun/">""", response
            )
            self.assertNotInRes(
                """<input class="secondary" type="submit" value="Rerun">""", response
            )
            batch.run()

            def attempt_to_rerun(user, authorized):
                batch.refresh_from_db()
                batch.run()
                if not user:
                    self.client.logout()
                else:
                    self.client.force_login(user)

                response = self.client.get(f"/batch/{pk}/")
                self.assertEqual(response.status_code, 200)

                # Checks if the user can access the batch rerun option
                if authorized:
                    self.assertInRes("rerun", response)
                    self.assertInRes(
                        f"""<form method="POST" action="/batch/{pk}/rerun/">""",
                        response,
                    )
                else:
                    self.assertNotInRes("rerun", response)
                    self.assertNotInRes(
                        f"""<form method="POST" action="/batch/{pk}/rerun/">""",
                        response,
                    )
                return self.client.post(f"/batch/{pk}/rerun/")

            # Test as batch creator
            response = attempt_to_rerun(creator, authorized=True)
            self.assertEqual(response.status_code, 302)

            # Test as admin
            response = attempt_to_rerun(admin, authorized=True)
            self.assertEqual(response.status_code, 302)

            # Test as other user
            response = attempt_to_rerun(other_user, authorized=False)
            self.assertEqual(response.status_code, 403)

            # Test as not authenticated user
            response = attempt_to_rerun(None, authorized=False)
            self.assertEqual(response.status_code, 403)

    @requests_mock.Mocker()
    def test_batch_report_permissions(self, mocker):
        self.api_mocker.is_autoconfirmed(mocker)
        self.api_mocker.wikidata_property_data_types(mocker)
        self.api_mocker.property_data_type(mocker, "P2", "wikibase-item")
        self.api_mocker.item_empty(mocker, "Q1234")
        self.api_mocker.item_empty(mocker, "Q11")
        self.api_mocker.patch_item_successful(mocker, "Q1234", {"id": "Q1234$stuff"})
        self.api_mocker.patch_item_successful(
            mocker, "Q11", {"id": "Q11", "labels": {"en": "label"}}
        )

        with mock.patch("web.views.new_batch.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            admin = User.objects.create_superuser(username="admin")
            other_user, _ = self.login_user_and_get_token("other_user")
            creator, api_client = self.login_user_and_get_token("creator")

            self.client.force_login(creator)

            # Creates the batch and runs it
            response = self.client.post(
                "/batch/new/",
                data={
                    "name": "My v1 batch",
                    "type": "v1",
                    "commands": """Q1234\tP2\tQ1||Q11|Len|"label" """,
                },
            )
            self.assertEqual(response.status_code, 302)

            response = self.client.post("/batch/new/preview/allow_start/")
            response = self.client.get(response.url)
            self.assertInRes("Stop execution", response)

            batch = response.context["batch"]
            pk = batch.pk
            self.assertNotInRes(
                f"""<form method="GET" action="/batch/{pk}/report/">""", response
            )
            self.assertNotInRes(
                """<input type="submit" value="Download report">""", response
            )
            batch.run()

        def checks_user_report_access(user, authorized):
            if not user:
                self.client.logout()
            else:
                self.client.force_login(user)

            response = self.client.get(f"/batch/{pk}/")
            self.assertEqual(response.status_code, 200)

            # Checks if the user can access the report download option
            if authorized:
                self.assertInRes(
                    f"""<form method="GET" action="/batch/{pk}/report/">""", response
                )
                self.assertInRes(
                    """<input type="submit" value="Download report">""", response
                )
            else:
                self.assertNotInRes(
                    f"""<form method="GET" action="/batch/{pk}/report/">""", response
                )
                self.assertNotInRes(
                    """<input type="submit" value="Download report">""", response
                )

            return self.client.get(f"/batch/{pk}/report/")

        # Test as batch creator
        response = checks_user_report_access(creator, authorized=True)
        self.assertEqual(response.status_code, 200)

        # Test as admin (regular user)
        response = checks_user_report_access(admin, authorized=True)
        self.assertEqual(response.status_code, 200)

        # Test as other user
        response = checks_user_report_access(other_user, authorized=False)
        self.assertEqual(response.status_code, 403)

        # Test as not authenticated user
        response = checks_user_report_access(None, authorized=False)
        self.assertEqual(response.status_code, 403)
