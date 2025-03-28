from unittest import mock

import requests_mock
from django.contrib import auth
from django.contrib.auth.models import User
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from core.models import Client as ApiClient
from core.models import Token
from core.tests.test_api import ApiMocker

from ..utils import user_from_access_token, user_from_full_token


class TestCase(DjangoTestCase):
    """Custom TestCase class with useful methods"""

    URL_NAME = "/"

    def setUp(self):
        super().setUp()
        self.api_mocker = ApiMocker()

    # ----------------
    # Assertion methods
    # -----------------

    def assert200(self, response):
        """Asserts the response status code is 200"""
        self.assertStatus(response, 200)

    def assertStatus(self, response, status):
        """Asserts the response status code"""
        self.assertEqual(response.status_code, status)

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

    def assertUrlInRes(self, url_name, response):
        """Checks if the URL is contained in the response"""
        self.assertInRes(reverse(url_name), response)

    def assertInRes(self, substring, response):
        """Checks if a substring is contained in response content"""
        self.assertIn(substring.lower(), str(response.content).lower().strip())

    def assertNotInRes(self, substring, response):
        """Checks if a substring is not contained in response content"""
        self.assertNotIn(substring.lower(), str(response.content).lower().strip())

    def assertIsAuthenticated(self):
        self.assertTrue(self.get_user().is_authenticated)

    def assertIsNotAuthenticated(self):
        self.assertFalse(self.get_user().is_authenticated)

    # ---------------
    # Utility methods
    # ---------------

    def get(self):
        """Make a test GET request with the test client"""
        return self.client.get(reverse(self.URL_NAME))

    def post(self, data=None):
        """Make a test POST request with the test client"""
        return self.client.post(reverse(self.URL_NAME), data=data)

    def login_john(self):
        """Login with a user with 'john' username"""
        user = User.objects.create_user(username="john")
        client = self.client
        client.force_login(user)

    def get_user(self):
        return auth.get_user(self.client)

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


class Profile(TestCase):
    URL_NAME = "profile"

    def test_not_logged_in(self):
        res = self.get()
        self.assert200(res)
        self.assertInRes("not logged in", res)
        self.assertUrlInRes("login", res)

    def test_logged_in_when_username_in_session(self):
        self.login_john()
        res = self.get()
        self.assert200(res)
        self.assertInRes("John", res)
        self.assertUrlInRes("logout", res)

    @requests_mock.Mocker()
    def test_logout_and_token_expired(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        user, api_client = self.login_user_and_get_token("user")
        res = self.client.get("/auth/profile/")
        self.assertRedirect(res)
        self.assertRedirectToUrlName(res, "login")
        self.assertIsNotAuthenticated()
        self.assertTrue(self.client.session["token_expired"])


class Login(TestCase):
    URL_NAME = "login"

    def test_contains_dev_login_url(self):
        res = self.get()
        self.assert200(res)
        self.assertUrlInRes("login_dev", res)

    def test_redirects_to_profile_if_logged_in(self):
        self.login_john()
        res = self.get()
        self.assertRedirectToPath(res, "/")
        self.assertIsAuthenticated()

    @requests_mock.Mocker()
    def test_expired_notice_vanishes_after_login_and_logout(self, mocker):
        self.api_mocker.autoconfirmed_failed_unauthorized(mocker)
        user, api_client = self.login_user_and_get_token("user")
        self.assertIsAuthenticated()

        res = self.client.get("/auth/profile/")
        self.assertRedirectToUrlName(res, "login")
        self.assertIsNotAuthenticated()

        res = self.client.get(res.url)
        self.assertEqual(res.context["token_expired"], True)
        self.assertInRes("Your Wikimedia authentication has expired.", res)
        self.assertIsNotAuthenticated()

        self.client.force_login(user)
        self.client.logout()

        res = self.client.get("/auth/login/")
        self.assertEqual(res.context["token_expired"], False)
        self.assertNotInRes("Your Wikimedia authentication has expired.", res)
        self.assertIsNotAuthenticated()

    @requests_mock.Mocker()
    def test_user_from_full_token(self, mocker):
        self.api_mocker.login_success(mocker, "Maria")
        full_token = {
            "access_token": "access_token",
            "refresh_token": "refresh_token",
            "expires_at": 1729809078,
        }
        user = user_from_full_token(full_token, wikibase=self.api_mocker.wikibase)
        token = Token.objects.get(user=user)
        self.assertEqual(user.username, "Maria")
        self.assertEqual(token.value, "access_token")
        self.assertEqual(token.refresh_token, "refresh_token")
        self.assertEqual(token.expires_at.year, 2024)
        self.assertEqual(token.expires_at.hour, 22)


class LoginDev(TestCase):
    URL_NAME = "login_dev"

    def test_contains_form(self):
        res = self.get()
        self.assert200(res)
        self.assertInRes("form", res)

    @requests_mock.Mocker()
    def test_login_fail(self, mocker):
        self.api_mocker.login_fail(mocker)

        with mock.patch("web.views.auth.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            res = self.post(data={"access_token": "my_invalid_token"})
            self.assertStatus(res, 400)
            self.assertInRes("Your access token is not valid", res)

    @requests_mock.Mocker()
    def test_user_from_access_token(self, mocker):
        self.api_mocker.login_success(mocker, "Maria")
        user = user_from_access_token("valid_token", wikibase=self.api_mocker.wikibase)
        token = Token.objects.get(user=user)
        self.assertEqual(user.username, "Maria")
        self.assertEqual(token.value, "valid_token")

    @requests_mock.Mocker()
    def test_login_success(self, mocker):
        self.api_mocker.login_success(mocker, "Maria")

        with mock.patch("web.views.auth.get_default_wikibase") as patched_wikibase:
            patched_wikibase.return_value = self.api_mocker.wikibase
            res = self.post(data={"access_token": "valid_token"})
            self.assertRedirectToPath(res, "/")
            user = self.get_user()
            token = Token.objects.get(user=user)
            self.assertEqual(user.username, "Maria")
            self.assertEqual(token.value, "valid_token")


class Logout(TestCase):
    URL_NAME = "logout"

    def test_clear_tokens(self):
        self.login_john()
        user_id = self.get_user().id
        self.get()

        tokens = Token.objects.filter(user__id=user_id)
        self.assertFalse(tokens.exists())

    def test_redirects_to_root(self):
        res = self.get()
        self.assertRedirectToPath(res, "/")


class OAuthCallback(TestCase):
    URL_NAME = "oauth_callback"

    def test_mismatched_states(self):
        res = self.get()
        self.assertStatus(res, 401)
        self.assertInRes("The authentication server is being", res)
        self.assertInRes("not supposed to be here right now.", res)
