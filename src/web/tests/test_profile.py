from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token


class ProfileTest(TestCase):

    def test_view_profile(self):
        c = Client()
        user = User.objects.create_user(username="john")
        c.force_login(user)

        self.assertFalse(Token.objects.exists())

        # Black box testing. We dont have any batch listed
        response = c.get("/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "en")
        self.assertIsNone(response.context["token"])

        self.assertFalse(Token.objects.exists())

        # Black box testing. We dont have any batch listed
        response = c.get("/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "en")
        self.assertIsNone(response.context["token"])

        self.assertFalse(Token.objects.exists())

    def test_change_profile_language(self):
        c = Client()
        user = User.objects.create_user(username="john")
        c.force_login(user)

        self.assertFalse(Token.objects.exists())

        # Black box testing. We dont have any batch listed
        response = c.get("/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "en")
        self.assertIsNone(response.context["token"])

        self.assertFalse(Token.objects.exists())

        data = urlencode({"action": "update_language", "language": "fr"})
        response = c.post(
            "/auth/profile/", data, content_type="application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "fr")
        self.assertIsNone(response.context["token"])

        self.assertFalse(Token.objects.exists())

    def test_change_profile_token(self):
        c = Client()
        user = User.objects.create_user(username="john")
        c.force_login(user)

        # Black box testing. We dont have any batch listed
        response = c.get("/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "en")
        self.assertIsNone(response.context["token"])
        self.assertFalse(Token.objects.exists())

        # generate the token on request
        data = urlencode({"action": "update_token"})
        response = c.post(
            "/auth/profile/", data, content_type="application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status_code, 200)
        prev_token = Token.objects.get(user=user)
        self.assertEqual(response.context["token"], prev_token.key)

        # viewing the profile keeps the token
        response = c.get("/auth/profile/")
        self.assertEqual(response.context["token"], prev_token.key)

        # update the token
        response = c.post(
            "/auth/profile/", data, content_type="application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")

        self.assertEqual(response.context["language"], "en")
        new_token = Token.objects.get(user=user)
        self.assertEqual(response.context["token"], new_token.key)
        self.assertNotEqual(response.context["token"], prev_token.key)
        self.assertNotEqual(prev_token, new_token)

        self.assertEqual(Token.objects.filter(user=user).count(), 1)
