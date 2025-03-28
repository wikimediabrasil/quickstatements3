import factory
from django.contrib.auth.models import User

from .models import Token, Wikibase


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
