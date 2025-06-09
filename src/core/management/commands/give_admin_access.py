from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Gives staff and superuser rights to an user"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)

    def handle(self, *args, **options):
        username = options["username"].lower()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist")
        user.is_staff = True
        user.is_superuser = True
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Turned '{username}' a QuickStatements 3.0 admin"))
