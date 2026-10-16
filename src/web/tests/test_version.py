from django.test import TestCase, override_settings


class VersionTest(TestCase):
    @override_settings(APP_VERSION="v1.2.3-4-gabcdef0")
    def test_version_in_footer(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "</a> · v1.2.3-4-gabcdef0")

