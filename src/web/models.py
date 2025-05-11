from datetime import timedelta
from datetime import datetime
from datetime import UTC

from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.utils.translation import pgettext_lazy

from .languages import LANGUAGE_CHOICES


def unix_timestamp_to_datetime(expires_at_oauth: int):
    return datetime.fromtimestamp(expires_at_oauth, UTC)


class TokenManager(models.Manager):
    def create_from_full_token(self, user, full_token):
        access_token = full_token["access_token"]
        refresh_token = full_token["refresh_token"]
        unix_timestamp = full_token["expires_at"]
        expires_at = unix_timestamp_to_datetime(unix_timestamp)

        return self.create(
            user=user,
            value=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )


class Token(models.Model):
    """
    User OAuth tokens
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=False, null=False)
    # TODO: store this encrypted?
    value = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    objects = TokenManager()

    def __str__(self):
        if hasattr(self, "user"):
            return f"Token for {self.user}: [redacted]"
        else:
            return "Anonymous token: [redacted]"

    class Meta:
        verbose_name = pgettext_lazy("web-models-token", "Token")
        verbose_name_plural = pgettext_lazy("web-models-tokens", "Tokens")

    def is_expired(self, buffer_minutes=5):
        """
        Checks if the access token is expired or
        will expire soon, using by default
        a 5 minute time buffer.

        If there is no `self.expires_at`, returns False,
        assuming the access token will never expire.
        """
        if not self.expires_at:
            return False
        soon = now() + timedelta(minutes=buffer_minutes)
        return self.expires_at <= soon

    def update_from_full_token(self, full_token):
        self.value = full_token["access_token"]
        self.refresh_token = full_token["refresh_token"]
        unix_timestamp = full_token["expires_at"]
        self.expires_at = unix_timestamp_to_datetime(unix_timestamp)
        self.save()


class PreferencesManager(models.Manager):
    def get_language(self, user, default):
        if user is None or not user.is_authenticated:
            return default
        try:
            prefs = self.get_queryset().only('language').get(user=user)
            return prefs.language or default
        except self.model.DoesNotExist:
            return default


class Preferences(models.Model):
    """
    User preferences
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=False, null=False)
    language = models.CharField(
        max_length=32, choices=LANGUAGE_CHOICES, blank=True, null=False
    )

    objects = PreferencesManager()

    def __str__(self):
        return f"Preferences for {self.user}"

    class Meta:
        verbose_name = pgettext_lazy("web-models-preferences", "Preferences")
        verbose_name_plural = pgettext_lazy("web-models-preferences", "Preferences")
