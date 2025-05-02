from django.contrib.auth.models import User
from django.test import TestCase


class ProfileTest(TestCase):
    def test_view_profile(self):
        user = User.objects.create_user(username="john")
        self.client.force_login(user)
        response = self.client.get("/statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("profile.html")
        self.assertEqual(response.context["batches_count"], 0)
        self.assertEqual(response.context["commands_count"], 0)
        self.assertEqual(response.context["average_commands_per_batch"], 0)
        self.assertEqual(response.context["items_created"], 0)
        self.assertEqual(response.context["editors"], 0)
        self.assertEqual(response.context["edits"], 0)
