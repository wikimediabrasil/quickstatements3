import factory
from django.contrib.auth.models import User

from .models import Token, Wikibase, Batch


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Sequence(lambda n: f"test-user-{n:02d}")

    class Meta:
        model = User


class WikibaseFactory(factory.django.DjangoModelFactory):
    url = factory.Sequence(lambda n: f"https://wikibase-{n:02d}.example.com")
    identifier = factory.Sequence(lambda n: f"wikibase-{n:02d}")

    class Meta:
        model = Wikibase


class TokenFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    value = factory.Faker("pystr", max_chars=30)

    class Meta:
        model = Token


class BatchFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Test Batch #{n:03d}")
    user = "test_user"
    status = Batch.STATUS_INITIAL

    class Meta:
        model = Batch

    @classmethod
    def load_from_parser(cls, parser, name, user, data, **extra):
        batch = cls(name=name, user=user, **extra)
        for batch_command in parser.parse(data):
            batch_command.batch = batch
            batch_command.save()

        return batch
