from django.contrib.auth.models import User
from django.test import TestCase

import requests_mock
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from core.models import Batch
from core.tests.test_api import ApiMocker


class BatchListViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="myuser")
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def test_non_auth_request(self):
        response = self.client.get(reverse("batch-list"))
        self.assertEqual(response.status_code, 401)

    def test_bad_auth_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token fdsfsdfsfsdafsdfsdfsfsdfsad")
        response = self.client.get(reverse("batch-list"))
        self.assertEqual(response.status_code, 401)

    def test_empty_authenticated_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("batch-list"))
        self.assertEqual(response.status_code, 200)

    def test_single_batch_authenticated_request(self):
        original = Batch.objects.create(name="Batch 0", user="testuser")
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("batch-list"))
        data = response.data
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page_size"], 1)
        self.assertEqual(len(data["batches"]), 1)
        batch = data["batches"][0]
        self.assertEqual(batch["url"], f"http://testserver/api/v1/batches/{original.pk}/")
        self.assertEqual(batch["pk"], original.pk)
        self.assertEqual(batch["user"], "testuser")
        self.assertEqual(batch["name"], "Batch 0")
        self.assertEqual(batch["status"], {"code": 1, "display": "Initial"})
        self.assertEqual(batch["message"], None)
        self.assertTrue("created" in batch)
        self.assertTrue("modified" in batch)

    def test_single_running_batch_authenticated_request(self):
        original = Batch.objects.create(
            name="Batch 1",
            user="testuser",
            status=Batch.STATUS_RUNNING,
            message="My running message",
        )
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("batch-list"))
        data = response.data
        batch = data["batches"][0]
        self.assertEqual(batch["url"], f"http://testserver/api/v1/batches/{original.pk}/")
        self.assertEqual(batch["pk"], original.pk)
        self.assertEqual(batch["user"], "testuser")
        self.assertEqual(batch["name"], "Batch 1")
        self.assertEqual(batch["status"], {"code": 2, "display": "Running"})
        self.assertEqual(batch["message"], "My running message")
        self.assertTrue("created" in batch)
        self.assertTrue("modified" in batch)

    def test_single_done_batch_authenticated_request(self):
        original = Batch.objects.create(
            name="Batch 2",
            user="testuser",
            status=Batch.STATUS_DONE,
            message="My DONE message",
        )
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("batch-list"))
        data = response.data
        batch = data["batches"][0]
        self.assertEqual(batch["url"], f"http://testserver/api/v1/batches/{original.pk}/")
        self.assertEqual(batch["pk"], original.pk)
        self.assertEqual(batch["user"], "testuser")
        self.assertEqual(batch["name"], "Batch 2")
        self.assertEqual(batch["status"], {"code": 3, "display": "Done"})
        self.assertEqual(batch["message"], "My DONE message")
        self.assertTrue("created" in batch)
        self.assertTrue("modified" in batch)

    def test_single_blocked_batch_authenticated_request(self):
        original = Batch.objects.create(
            name="Batch 3",
            user="testuser",
            status=Batch.STATUS_BLOCKED,
            message="My BLOCKED message",
        )
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("batch-list"))
        data = response.data
        batch = data["batches"][0]
        self.assertEqual(batch["url"], f"http://testserver/api/v1/batches/{original.pk}/")
        self.assertEqual(batch["pk"], original.pk)
        self.assertEqual(batch["user"], "testuser")
        self.assertEqual(batch["name"], "Batch 3")
        self.assertEqual(batch["status"], {"code": -1, "display": "Blocked"})
        self.assertEqual(batch["message"], "My BLOCKED message")
        self.assertTrue("created" in batch)
        self.assertTrue("modified" in batch)

    def test_authenticated_request(self):
        for user in ["user1", "user2"]:
            for i in range(0, 35):
                Batch.objects.create(name=f"Batch {i} for {user}", user=user)

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        #####
        # Testing pagination
        #####
        response = self.client.get(reverse("batch-list"))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], "http://testserver/api/v1/batches/?page=2")
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 70)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(len(data["batches"]), 20)

        response = self.client.get("http://testserver/api/v1/batches/?page=2")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], "http://testserver/api/v1/batches/?page=3")
        self.assertEqual(data["links"]["previous"], "http://testserver/api/v1/batches/")
        self.assertEqual(data["total"], 70)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(len(data["batches"]), 20)

        response = self.client.get("http://testserver/api/v1/batches/?page=3")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], "http://testserver/api/v1/batches/?page=4")
        self.assertEqual(data["links"]["previous"], "http://testserver/api/v1/batches/?page=2")
        self.assertEqual(data["total"], 70)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(len(data["batches"]), 20)

        response = self.client.get("http://testserver/api/v1/batches/?page=4")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(data["links"]["previous"], "http://testserver/api/v1/batches/?page=3")
        self.assertEqual(data["total"], 70)
        self.assertEqual(data["page_size"], 10)
        self.assertEqual(len(data["batches"]), 10)

        #####
        # Testing filter by user1
        #####
        response = self.client.get("http://testserver/api/v1/batches/?username=user1")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(
            data["links"]["next"],
            "http://testserver/api/v1/batches/?page=2&username=user1",
        )
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 35)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(len(data["batches"]), 20)
        for b in data["batches"]:
            self.assertEqual(b["user"], "user1")

        response = self.client.get("http://testserver/api/v1/batches/?username=user1&page=2")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(
            data["links"]["previous"],
            "http://testserver/api/v1/batches/?username=user1",
        )
        self.assertEqual(data["total"], 35)
        self.assertEqual(data["page_size"], 15)
        self.assertEqual(len(data["batches"]), 15)
        for b in data["batches"]:
            self.assertEqual(b["user"], "user1")

        #####
        # Testing filter by user2
        #####
        response = self.client.get("http://testserver/api/v1/batches/?username=user2")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(
            data["links"]["next"],
            "http://testserver/api/v1/batches/?page=2&username=user2",
        )
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 35)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(len(data["batches"]), 20)
        for b in data["batches"]:
            self.assertEqual(b["user"], "user2")

        response = self.client.get("http://testserver/api/v1/batches/?username=user2&page=2")
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue("links" in data)
        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(
            data["links"]["previous"],
            "http://testserver/api/v1/batches/?username=user2",
        )
        self.assertEqual(data["total"], 35)
        self.assertEqual(data["page_size"], 15)
        self.assertEqual(len(data["batches"]), 15)
        for b in data["batches"]:
            self.assertEqual(b["user"], "user2")

    @requests_mock.Mocker()
    def test_create_batch_endpoint(self, mocker):
        api_mocker = ApiMocker()
        api_mocker.is_autoconfirmed(mocker)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        data = {"name": "Batch created via API", "v1": "CREATE||-Q1234|P1|12||Q222|P4|9~0.1"}

        response = self.client.post(reverse("batch-list"), data=data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Batch.objects.count(), 1)
        batch = Batch.objects.first()

        self.assertEqual(batch.user, "myuser")
        self.assertEqual(batch.status, Batch.STATUS_INITIAL)

    def test_non_allowed_methods_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        response = self.client.put(reverse("batch-list"))
        self.assertEqual(response.status_code, 405)

        response = self.client.delete(reverse("batch-list"))
        self.assertEqual(response.status_code, 405)
