from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from core.models import Batch, BatchCommand
from core.parsers.v1 import V1CommandParser


class BatchCommandDetailViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="myuser")
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def test_non_auth_request(self):
        response = self.client.get(reverse("command-list", kwargs={"batchpk": 1}))
        self.assertEqual(response.status_code, 401)

    def test_bad_auth_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token fdsfsdfsfsdafsdfsdfsfsdfsad")
        response = self.client.get(reverse("command-list", kwargs={"batchpk": 1}))
        self.assertEqual(response.status_code, 401)

    def test_non_existing_authenticated_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("command-list", kwargs={"batchpk": 1}))
        self.assertEqual(response.status_code, 404)

    def test_batch_command_list_authenticated_request(self):
        v1 = V1CommandParser()
        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())
        batch = v1.parse("My batch", "myuser", "CREATE||-Q1234|P1|12||Q222|P4|9~0.1")
        batch.save_batch_and_preview_commands()
        commands = batch.commands()
        cmd1_pk = commands[0].pk
        cmd2_pk = commands[1].pk

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        response = self.client.get(
            reverse("command-list", kwargs={"batchpk": batch.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.data

        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["page_size"], 3)
        self.assertEqual(
            data["batch"],
            {"pk": batch.pk, "url": f"http://testserver/api/v1/batches/{batch.pk}/"},
        )

        c0 = data["commands"][0]
        self.assertEqual(c0["index"], 0)
        self.assertEqual(c0["url"], f"http://testserver/api/v1/commands/{cmd1_pk}")
        self.assertEqual(c0["action"], "CREATE")
        self.assertEqual(c0["json"], {"action": "create", "type": "item"})
        self.assertIsNone(c0["response_id"])
        self.assertEqual(c0["status"], 0)

        c1 = data["commands"][1]
        self.assertEqual(c1["index"], 1)
        self.assertEqual(c1["url"], f"http://testserver/api/v1/commands/{cmd2_pk}")
        self.assertEqual(c1["action"], "REMOVE")
        self.assertEqual(
            c1["json"],
            {
                "action": "remove",
                "what": "statement",
                "entity": {"type": "item", "id": "Q1234"},
                "property": "P1",
                "value": {"type": "quantity", "value": {"amount": "+12", "unit": "1"}},
            },
        )
        self.assertIsNone(c1["response_id"])
        self.assertEqual(c1["status"], 0)

    def test_batch_command_list_paginated_authenticated_request(self):
        batch = Batch.objects.create(name="Paginated batch", user="user")
        for i in range(0, 250):
            BatchCommand.objects.create(
                batch=batch, json={}, action=BatchCommand.ACTION_ADD, index=i
            )

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        response = self.client.get(
            f"http://testserver/api/v1/batches/{batch.pk}/commands/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(
            data["links"]["next"],
            f"http://testserver/api/v1/batches/{batch.pk}/commands/?page=2",
        )
        self.assertEqual(data["links"]["previous"], None)
        self.assertEqual(data["total"], 250)
        self.assertEqual(data["page_size"], 100)
        self.assertEqual(
            data["batch"],
            {"pk": batch.pk, "url": f"http://testserver/api/v1/batches/{batch.pk}/"},
        )

        response = self.client.get(
            f"http://testserver/api/v1/batches/{batch.pk}/commands/?page=2"
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(
            data["batch"],
            {"pk": batch.pk, "url": f"http://testserver/api/v1/batches/{batch.pk}/"},
        )
        self.assertEqual(
            data["links"]["next"],
            f"http://testserver/api/v1/batches/{batch.pk}/commands/?page=3",
        )
        self.assertEqual(
            data["links"]["previous"],
            f"http://testserver/api/v1/batches/{batch.pk}/commands/",
        )
        self.assertEqual(data["total"], 250)
        self.assertEqual(data["page_size"], 100)

        response = self.client.get(
            f"http://testserver/api/v1/batches/{batch.pk}/commands/?page=3"
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(
            data["batch"],
            {"pk": batch.pk, "url": f"http://testserver/api/v1/batches/{batch.pk}/"},
        )
        self.assertEqual(data["links"]["next"], None)
        self.assertEqual(
            data["links"]["previous"],
            f"http://testserver/api/v1/batches/{batch.pk}/commands/?page=2",
        )
        self.assertEqual(data["total"], 250)
        self.assertEqual(data["page_size"], 50)

    def test_non_allowed_methods_request(self):
        v1 = V1CommandParser()
        self.assertFalse(Batch.objects.count())
        self.assertFalse(BatchCommand.objects.count())
        batch = v1.parse("My batch", "myuser", "CREATE||-Q1234|P1|12||Q222|P4|9~0.1")
        batch.save_batch_and_preview_commands()

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        url = f"http://testserver/api/v1/batches/{batch.pk}/commands/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 405)
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)
