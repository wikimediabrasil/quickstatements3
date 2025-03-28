from django.contrib.auth.models import User

from core.models import Client, Token


def user_from_full_token(full_token, wikibase):
    """
    Creates an user and a token given the full token from OAuth.
    """
    access_token = full_token["access_token"]
    client = Client(token=Token(value=access_token), wikibase=wikibase)
    wikimedia_username = client.get_username()
    user = create_user_and_clear_tokens(wikimedia_username)

    Token.objects.create_from_full_token(user=user, full_token=full_token)

    return user


def user_from_access_token(access_token, wikibase):
    client = Client(token=Token(value=access_token), wikibase=wikibase)
    wikimedia_username = client.get_username()
    user = create_user_and_clear_tokens(wikimedia_username)

    Token.objects.create(user=user, value=access_token)

    return user


def create_user_and_clear_tokens(wikimedia_username: str):
    user, was_created = User.objects.get_or_create(
        username=wikimedia_username,
    )

    if not was_created:
        Token.objects.filter(user__id=user.id).delete()

    return user


def clear_tokens(user):
    Token.objects.filter(user__id=user.id).delete()
