from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from core.models import Batch, BatchCommand


class BatchCommandDetailViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username="myuser")
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def test_non_auth_request(self):
        response = self.client.get(reverse("command-detail", kwargs={"pk": 1}))
        self.assertEqual(response.status_code, 401)

    def test_bad_auth_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token fdsfsdfsfsdafsdfsdfsfsdfsad")
        response = self.client.get(reverse("command-detail", kwargs={"pk": 1}))
        self.assertEqual(response.status_code, 401)

    def test_non_existing_authenticated_request(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.get(reverse("command-detail", kwargs={"pk": 1}))
        self.assertEqual(response.status_code, 404)

    def test_batch_command_authenticated_request(self):
        batch = Batch.objects.create(
            name="Batch 1", user="testuser", status=Batch.STATUS_RUNNING
        )
        command = BatchCommand.objects.create(
            batch=batch,
            index=1,
            action=BatchCommand.ACTION_ADD,
            json={},
            status=BatchCommand.STATUS_INITIAL,
        )

        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

        response = self.client.get(reverse("command-detail", kwargs={"pk": command.pk}))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["pk"], command.pk)
        self.assertEqual(data["batch"]["pk"], batch.pk)
        self.assertEqual(data["batch"]["user"], "testuser")
        self.assertEqual(data["batch"]["name"], "Batch 1")
        self.assertEqual(
            data["batch"]["url"], f"http://testserver/api/v1/batches/{batch.pk}/"
        )
        self.assertEqual(data["batch"]["status"], {"code": 2, "display": "Running"})
        self.assertEqual(data["index"], 1)
        self.assertEqual(data["action"], "ADD")
        self.assertEqual(data["raw"], "")
        self.assertEqual(data["json"], {})
        self.assertIsNone(data["response_id"])
        self.assertEqual(data["status"], {"code": 0, "display": "Initial"})

        command.status = BatchCommand.STATUS_RUNNING
        command.raw = "CREATE"
        command.json = {"action": "create", "type": "item"}
        command.save()

        response = self.client.get(reverse("command-detail", kwargs={"pk": command.pk}))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["pk"], command.pk)
        self.assertEqual(data["batch"]["pk"], batch.pk)
        self.assertEqual(data["batch"]["user"], "testuser")
        self.assertEqual(data["batch"]["name"], "Batch 1")
        self.assertEqual(
            data["batch"]["url"], f"http://testserver/api/v1/batches/{batch.pk}/"
        )
        self.assertEqual(data["batch"]["status"], {"code": 2, "display": "Running"})
        self.assertEqual(data["index"], 1)
        self.assertEqual(data["action"], "ADD")
        self.assertEqual(data["raw"], "CREATE")
        self.assertEqual(data["json"], {"action": "create", "type": "item"})
        self.assertIsNone(data["response_id"])
        self.assertEqual(data["status"], {"code": 1, "display": "Running"})

        command.status = BatchCommand.STATUS_DONE
        command.action = BatchCommand.ACTION_CREATE
        command.save()

        response = self.client.get(reverse("command-detail", kwargs={"pk": command.pk}))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["pk"], command.pk)
        self.assertEqual(data["batch"]["pk"], batch.pk)
        self.assertEqual(data["batch"]["user"], "testuser")
        self.assertEqual(data["batch"]["name"], "Batch 1")
        self.assertEqual(
            data["batch"]["url"], f"http://testserver/api/v1/batches/{batch.pk}/"
        )
        self.assertEqual(data["batch"]["status"], {"code": 2, "display": "Running"})
        self.assertEqual(data["index"], 1)
        self.assertEqual(data["action"], "CREATE")
        self.assertEqual(data["raw"], "CREATE")
        self.assertEqual(data["json"], {"action": "create", "type": "item"})
        self.assertIsNone(data["response_id"])
        self.assertEqual(data["status"], {"code": 2, "display": "Done"})

        command.status = BatchCommand.STATUS_ERROR
        command.save()

        response = self.client.get(reverse("command-detail", kwargs={"pk": command.pk}))
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["pk"], command.pk)
        self.assertEqual(data["batch"]["pk"], batch.pk)
        self.assertEqual(data["batch"]["user"], "testuser")
        self.assertEqual(data["batch"]["name"], "Batch 1")
        self.assertEqual(
            data["batch"]["url"], f"http://testserver/api/v1/batches/{batch.pk}/"
        )
        self.assertEqual(data["batch"]["status"], {"code": 2, "display": "Running"})
        self.assertEqual(data["index"], 1)
        self.assertEqual(data["action"], "CREATE")
        self.assertEqual(data["raw"], "CREATE")
        self.assertEqual(data["json"], {"action": "create", "type": "item"})
        self.assertIsNone(data["response_id"])
        self.assertEqual(data["status"], {"code": -1, "display": "Error"})

    def test_non_allowed_methods_request(self):
        original = Batch.objects.create(
            name="Batch 1", user="testuser", status=Batch.STATUS_RUNNING
        )
        command = BatchCommand.objects.create(
            batch=original,
            index=1,
            action=BatchCommand.ACTION_ADD,
            json={},
            status=BatchCommand.STATUS_INITIAL,
        )
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        response = self.client.post(
            reverse("command-detail", kwargs={"pk": command.pk})
        )
        self.assertEqual(response.status_code, 405)
        response = self.client.put(reverse("command-detail", kwargs={"pk": command.pk}))
        self.assertEqual(response.status_code, 405)
        response = self.client.delete(
            reverse("command-detail", kwargs={"pk": command.pk})
        )
        self.assertEqual(response.status_code, 405)
