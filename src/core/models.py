import copy
import csv
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import jsonpatch
import requests
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache as django_cache
from django.db import models, transaction
from django.utils.timezone import now
from django.utils.translation import gettext as _
from requests.exceptions import HTTPError
from urllib3.util.retry import Retry

from .decorators import cache_with_first_arg
from .exceptions import (
    ApiException,
    EntityTypeNotImplemented,
    InvalidPropertyValueType,
    LastCouldNotBeEvaluated,
    NonexistantPropertyOrNoDataType,
    NoQualifiers,
    NoReferenceParts,
    NoStatementsForThatProperty,
    NoStatementsWithThatValue,
    NoValueTypeForThisDataType,
    ServerError,
    UnauthorizedToken,
    UserError,
)

logger = logging.getLogger("qsts3")

oauth = OAuth()
oauth.register(
    name="mediawiki",
    client_id=settings.OAUTH_CLIENT_ID,
    client_secret=settings.OAUTH_CLIENT_SECRET,
    access_token_url=settings.OAUTH_ACCESS_TOKEN_URL,
    authorize_url=settings.OAUTH_AUTHORIZATION_URL,
)


def get_default_wikibase():
    parsed_root_enpoint = urlparse(settings.DEFAULT_WIKIBASE_URL)
    default_wikibase_url = (
        f"{parsed_root_enpoint.scheme}://{parsed_root_enpoint.netloc}"
    )
    wikibase, _ = Wikibase.objects.get_or_create(url=default_wikibase_url)
    return wikibase


def unix_timestamp_to_datetime(expires_at_oauth: int):
    return datetime.fromtimestamp(expires_at_oauth, UTC)


class Client:
    def __init__(self, token: "Token", wikibase: "Wikibase"):
        retries = Retry(
            total=10,
            backoff_factor=1,
            status_forcelist=[429],
            allowed_methods=["GET", "POST", "PATCH", "DELETE"],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)

        self.token = token
        self.value_type_cache = {}
        self.labels_cache = {}
        self.wikibase = wikibase
        self.session = requests.Session()

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    @property
    def rest_endpoint_url(self):
        return self.wikibase.rest_endpoint_url

    @property
    def oauth_profile_endpoint(self):
        return settings.OAUTH_PROFILE_URL

    @property
    def wikibase_v1_endpoint(self):
        return self.wikibase.v1_endpoint

    @property
    def action_api_url(self):
        return self.wikibase.api_endpoint

    def __str__(self):
        return "API Client with token [redacted]"

    # ---
    # Utilities
    # ----

    def headers(self):
        return {
            "User-Agent": "QuickStatements 3.0",
            "Authorization": f"Bearer {self.token.value}",
            "Content-Type": "application/json",
        }

    def get(self, url):
        logger.debug(f"Sending GET request at {url}")
        self.token.refresh_if_needed()

        response = self.session.get(url, headers=self.headers())
        self.raise_for_status(response)
        return response

    def raise_for_status(self, response):
        status = response.status_code
        if status == 401:
            raise UnauthorizedToken()
        if 400 <= status <= 499:
            j = response.json()
            raise UserError(status, j.get("code"), j.get("message"), j)
        if 500 <= status:
            j = response.json()
            raise ServerError(j)

    # ---
    # Auth
    # ---
    def get_profile(self):
        if not hasattr(self, "_profile"):
            self._profile = self.get(self.oauth_profile_endpoint).json()
        return self._profile

    def get_username(self):
        try:
            profile = self.get_profile()
            return profile["username"]
        except KeyError:
            raise ServerError(profile)

    def get_user_groups(self):
        profile = self.get_profile()
        return profile.get("groups", [])

    def get_is_autoconfirmed(self):
        if "autoconfirmed" in self.get_user_groups():
            return True

        try:
            username = self.get_username()
            if username in settings.WHITELISTED_USERS:
                return True
        except ServerError:
            pass

        return False

    def get_is_blocked(self):
        profile = self.get_profile()
        return profile.get("blocked", False)

    # ---
    # Wikibase utilities
    # ---
    def wikibase_url(self, endpoint):
        return f"{self.wikibase_v1_endpoint}{endpoint}"

    def wikibase_entity_url(self, entity_id, entity_endpoint):
        endpoint = Client.wikibase_entity_endpoint(entity_id, entity_endpoint)
        return self.wikibase_url(endpoint)

    def wikibase_request_wrapper(self, method, endpoint, body):
        """
        Sends a request to the Wikibase REST API, using the provided
        endpoint, method and json body.
        """
        kwargs = {
            "json": body,
            "headers": self.headers(),
        }

        url = self.wikibase_url(endpoint)

        self.token.refresh_if_needed()

        logger.debug(f"{method} request at {url} | sending with body {body}")

        res = getattr(self.session, method.lower())(url, **kwargs)

        logger.debug(f"{method} request at {url} | response: {res.json()}")
        self.raise_for_status(res)
        return res.json()

    # ---
    # Wikibase GET/reading
    # ---

    @cache_with_first_arg("value_type_cache")
    def get_property_value_type(self, property_id):
        """
        Returns the expected value type of the property.

        Returns the value type as a string.

        Uses a dictionary attribute for caching.
        """
        endpoint = f"/entities/properties/{property_id}"
        url = self.wikibase_url(endpoint)

        try:
            res = self.session.get(url).json()
            data_type = res["data_type"]
        except (KeyError, UserError):
            raise NonexistantPropertyOrNoDataType(property_id)

        try:
            value_type = self.data_type_to_value_type(data_type)
        except KeyError:
            raise NoValueTypeForThisDataType(property_id, data_type)

        return value_type

    def data_type_to_value_type(self, data_type):
        """
        Gets the associated value type for a property's data type.

        # Raises

        - `KeyError` if there is no associated value type.
        """
        key = self.wikibase_url("/property-data-types")

        # We are caching this so that we don't need to hit it every time.
        # We are using the global cache (django cache), instead of
        # local dictionaries like the other caches, because this is
        # equal to every client and it is unlikely to change between batches.
        if django_cache.get(key) is not None:
            mapper = django_cache.get(key)
        else:
            mapper = self.get_property_data_types()
            django_cache.set(key, mapper)

        return mapper[data_type]

    def verify_value_type(self, property_id, value_type):
        """
        Verifies if the value type of the property with `property_id` matches `value_type`.

        If not, raises `InvalidPropertyValueType`.

        Value types "somevalue" and "novalue" are allowed for every property.
        """
        if value_type not in ["somevalue", "novalue"]:
            needed = self.get_property_value_type(property_id)
            if needed != value_type:
                raise InvalidPropertyValueType(property_id, value_type, needed)

    def get_property_data_types(self):
        """
        Returns a mapper of data types to value types
        from the Wikibase API.
        """
        url = self.wikibase_url("/property-data-types")
        return self.get(url).json()

    def get_entity(self, entity_id):
        """
        Returns the entire entity json document.
        """
        url = self.wikibase_entity_url(entity_id, "")
        return self.get(url).json()

    # ---
    # Action API GET/reading
    # ---

    def get_multiple_labels(self, entity_ids: List[str], language: str) -> dict:
        """
        Obtains multiple labels using the Action API.

        When the REST API allows this, we can swicth to it.

        Returns as an easy to use dictionary with the entity ids
        as keys and the labels as values, which can be empty strings.
        """
        action_api = self.action_api_url
        languages = f"{language}|en" if language != "en" else "en"
        ids = "|".join(entity_ids)
        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "labels",
            "languages": languages,
            "ids": ids,
            "languagefallback": "",
        }
        logger.debug(
            f"Sending GET request at {action_api}, languages={languages}, ids={ids}"
        )
        self.token.refresh_if_needed()
        res = requests.get(action_api, headers=self.headers(), params=params)
        self.raise_for_status(res)
        return res.json()

    @staticmethod
    def wikibase_entity_endpoint(entity_id, entity_endpoint=""):
        if entity_id.startswith("Q"):
            base = "/entities/items"
        elif entity_id.startswith("P"):
            base = "/entities/properties"
        else:
            raise EntityTypeNotImplemented(entity_id)

        return f"{base}/{entity_id}{entity_endpoint}"


@dataclass
class CombiningState:
    """
    Utility class to manage state between combining commands.

    Saves the current entity json document and the previous
    commands that have altered it.
    """

    commands: List["BatchCommand"]
    entity: Optional[dict]

    @classmethod
    def empty(cls):
        return cls(commands=[], entity=None)


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


class Wikibase(models.Model):
    url = models.URLField(primary_key=True)
    description = models.TextField()
    identifier = models.SlugField(default="wikidata", unique=True)

    @property
    def rest_endpoint_url(self):
        return f"{self.url}/w/rest.php"

    @property
    def api_endpoint(self):
        return f"{self.url}/w/api.php"

    @property
    def oauth_token_endpoint(self):
        return f"{self.rest_endpoint_url}/oauth2/access_token"

    @property
    def oauth_profile_endpoint(self):
        return f"{self.rest_endpoint_url}/oauth2/resource/profile"

    @property
    def oauth_authorization_endpoint(self):
        return f"{self.rest_endpoint_url}/oauth2/authorize"

    @property
    def v1_endpoint(self):
        return f"{self.rest_endpoint_url}/wikibase/v1"

    def __str__(self):
        return self.url


class Token(models.Model):
    """
    User OAuth tokens
    """

    user = models.ForeignKey(
        User,
        related_name="tokens",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )
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

    def refresh_if_needed(self):
        """
        The OAuth access token token can expire.

        This will check if it's near expiration and
        make a call for a new one with the refresh token
        if necessary.
        """
        if self.is_expired() and self.refresh_token:
            self.refresh()

    def refresh(self):
        """
        Refreshes the current `Token` using its refresh token.
        """
        logger.debug(f"[{self}] Refreshing OAuth token...")

        try:
            new_token = oauth.mediawiki.fetch_access_token(
                grant_type="refresh_token", refresh_token=self.refresh_token
            )
            self.value = new_token["access_token"]
            self.refresh_token = new_token["refresh_token"]
            unix_timestamp = new_token["expires_at"]
            self.expires_at = unix_timestamp_to_datetime(unix_timestamp)
            self.save()
        except HTTPError:
            raise UnauthorizedToken()


class Batch(models.Model):
    """
    Represents a BATCH, containing multiple commands
    """

    STATUS_STOPPED = -2
    STATUS_BLOCKED = -1
    STATUS_PREVIEW = 0
    STATUS_INITIAL = 1
    STATUS_RUNNING = 2
    STATUS_DONE = 3

    STATUS_CHOICES = (
        (STATUS_STOPPED, _("Stopped")),
        (STATUS_BLOCKED, _("Blocked")),
        (STATUS_PREVIEW, _("Preview")),
        (STATUS_INITIAL, _("Initial")),
        (STATUS_RUNNING, _("Running")),
        (STATUS_DONE, _("Done")),
    )

    name = models.CharField(max_length=255, blank=False, null=False)
    user = models.CharField(max_length=128, blank=False, null=False, db_index=True)
    status = models.IntegerField(
        default=STATUS_INITIAL, choices=STATUS_CHOICES, null=False, db_index=True
    )
    message = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)
    block_on_errors = models.BooleanField(default=False)
    combine_commands = models.BooleanField(default=False)
    wikibase = models.ForeignKey(
        Wikibase, default=get_default_wikibase, on_delete=models.CASCADE
    )

    def __str__(self):
        return f"Batch #{self.pk}"

    class Meta:
        verbose_name = _("Batch")
        verbose_name_plural = _("Batches")

    def commands(self):
        return BatchCommand.objects.filter(batch=self).all().order_by("index")

    def run(self):
        """
        Sends all the batch commands to the Wikidata API. This method should not fail.
        Sets the batch status to BLOCKED when a command fails.
        """
        # Ignore when not INITIAL or RUNNING
        if not self.is_initial_or_running:
            return

        self.start()

        try:
            # FIXME: change Batch.user from username to real User objects
            token = Token.objects.get(user__username=self.user)
            client = Client(token=token, wikibase=self.wikibase)
            is_autoconfirmed = client.get_is_autoconfirmed()
        except (Token.DoesNotExist, UnauthorizedToken, ServerError):
            return self.block_no_token()
        if not is_autoconfirmed:
            return self.block_is_not_autoconfirmed()

        # TODO: if self.verify_value_types_before_running
        for command in self.commands().filter(value_type_verified=False).iterator():
            try:
                command.verify_value_types(client)
            except (InvalidPropertyValueType, NonexistantPropertyOrNoDataType):
                if self.block_on_errors:
                    return self.block_by(command)

        last_id = None
        state = CombiningState.empty()
        commands = self.commands().exclude(status=BatchCommand.STATUS_DONE)

        iterator = commands.iterator()

        try:
            current = next(iterator)
            while current is not None:
                self.refresh_from_db()
                if self.is_stopped:
                    # The status changed, so we have to stop
                    return
                try:
                    upcoming = next(iterator)
                except StopIteration:
                    upcoming = None

                current.check_combination(state, upcoming)
                current.update_last_id(last_id)
                current.run(client)

                if current.is_error_status() and self.block_on_errors:
                    return self.block_by(current)

                state = current.final_combining_state
                if current.action == BatchCommand.ACTION_CREATE:
                    last_id = current.response_id

                current = upcoming

        except StopIteration:
            pass

        if self.commands().filter(status=BatchCommand.STATUS_INITIAL).exists():
            logger.warning(
                f"[{self}] finished running but still has init commands, restarting..."
            )
            self.status = Batch.STATUS_INITIAL
            self.save()
            return
        self.finish()

    def start(self):
        logger.debug(f"[{self}] running...")
        self.message = f"Batch started processing at {datetime.now()}"
        self.status = self.STATUS_RUNNING
        self.save()

    def finish(self):
        logger.info(f"[{self}] finished")
        self.message = f"Batch finished processing at {datetime.now()}"
        self.status = self.STATUS_DONE
        self.save()

    def stop(self):
        if not self.is_done:
            logger.info(f"[{self}] stop...")
            self.message = f"Batch stopped processing at {datetime.now()}"
            self.status = self.STATUS_STOPPED
            self.save()
        else:
            logger.warning(f"[{self}] user tried to stop but batch is done.")

    def restart(self):
        if self.is_stopped:
            logger.info(f"[{self}] restarting...")
            self.message = f"Batch restarted at {datetime.now()}"
            self.status = self.STATUS_INITIAL
            self.save()

    def rerun(self):
        if self.is_done_and_has_pending:
            logger.info(f"[{self}] rerunning...")
            commands = []
            for command in self.commands().exclude(status=BatchCommand.STATUS_DONE):
                command.status = BatchCommand.STATUS_INITIAL
                commands.append(command)
            BatchCommand.objects.bulk_update(commands, ["status"])
            self.message = f"Batch rerun at {datetime.now()}"
            self.status = self.STATUS_INITIAL
            self.save()

    def block_is_not_autoconfirmed(self):
        logger.warning(f"[{self}] blocked, the user {self.user} is not autoconfirmed")
        message = "The user is not an autoconfirmed user."
        self.block_with_message(message)

    def block_no_token(self):
        logger.error(
            f"[{self}] blocked, we don't have a valid token for the user {self.user}"
        )
        message = "We don't have a valid API token for the user"
        self.block_with_message(message)

    def block_by(self, command):
        logger.warning(f"[{self}] blocked by {command}")
        message = f"blocked by command {command.index}"
        self.block_with_message(message)

    def block_with_message(self, message):
        self.message = message
        self.status = self.STATUS_BLOCKED
        self.save()

    @property
    def is_preview(self):
        return self.status == Batch.STATUS_PREVIEW

    @property
    def is_running(self):
        return self.status == Batch.STATUS_RUNNING

    @property
    def is_stopped(self):
        return self.status == Batch.STATUS_STOPPED

    @property
    def is_initial(self):
        return self.status == Batch.STATUS_INITIAL

    @property
    def is_initial_or_running(self):
        return self.is_initial or self.is_running

    @property
    def is_preview_initial_or_running(self):
        return self.is_preview or self.is_initial or self.is_running

    @property
    def is_done(self):
        return self.status == Batch.STATUS_DONE

    @property
    def has_pending_commands(self):
        return self.commands().exclude(status=BatchCommand.STATUS_DONE).exists()

    @property
    def is_done_and_has_pending(self):
        return self.is_done and self.has_pending_commands

    def add_preview_command(self, preview_command: "BatchCommand") -> bool:
        if not hasattr(self, "_preview_commands"):
            self._preview_commands = []
        if preview_command is not None and isinstance(preview_command, BatchCommand):
            self._preview_commands.append(preview_command)
            return True
        return False

    def get_preview_commands(self) -> list:
        if hasattr(self, "_preview_commands"):
            return self._preview_commands
        else:
            return []

    @transaction.atomic
    def save_batch_and_preview_commands(self):
        self.status = self.STATUS_INITIAL
        if not self.pk:
            super(Batch, self).save()
        if hasattr(self, "_preview_commands"):
            for batch_command in self._preview_commands:
                batch_command.batch = self
                batch_command.save()

    # ------
    # REPORT
    # ------

    def write_report(self, csvfile):
        """
        Uses `csvfile` as the csv writer's file to write the batch report.
        """
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "batch_id",
                "index",
                "operation",
                "status",
                "error",
                "message",
                "entity_id",
                "raw_input",
            ]
        )
        for cmd in self.commands():
            writer.writerow(
                [
                    self.pk,
                    cmd.index,
                    cmd.operation,
                    cmd.get_status_display(),
                    cmd.error,
                    cmd.message,
                    cmd.entity_id(),
                    cmd.raw.replace("\t", "|"),  # tabs are weird in csv
                ]
            )


class BatchCommand(models.Model):
    """
    Individual command from a batch
    """

    STATUS_ERROR = -1
    STATUS_INITIAL = 0
    STATUS_RUNNING = 1
    STATUS_DONE = 2

    STATUS_CHOICES = (
        (STATUS_ERROR, _("Error")),
        (STATUS_INITIAL, _("Initial")),
        (STATUS_RUNNING, _("Running")),
        (STATUS_DONE, _("Done")),
    )

    ACTION_CREATE = 0
    ACTION_ADD = 1
    ACTION_REMOVE = 2
    ACTION_MERGE = 3

    ACTION_CHOICES = (
        (ACTION_CREATE, "CREATE"),
        (ACTION_ADD, "ADD"),
        (ACTION_REMOVE, "REMOVE"),
        (ACTION_MERGE, "MERGE"),
    )

    # -------
    # Identifier fields
    # -------
    batch = models.ForeignKey(Batch, null=False, on_delete=models.CASCADE)
    index = models.IntegerField()

    # -------
    # Datetime
    # -------
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    # -------
    # Parser fields
    # -------
    raw = models.TextField()
    json = models.JSONField()

    # -------
    # Operation/action fields
    # -------
    action = models.IntegerField(
        default=ACTION_CREATE, choices=ACTION_CHOICES, null=False, blank=False
    )
    user_summary = models.TextField(blank=True, null=True)

    class Operation(models.TextChoices):
        CREATE_ITEM = "create_item", _("Create item")
        CREATE_PROPERTY = "create_property", _("Create property")
        #
        SET_STATEMENT = "set_statement", _("Set statement")
        CREATE_STATEMENT = "create_statement", _("Create statement")
        #
        REMOVE_STATEMENT_BY_ID = "remove_statement_by_id", _("Remove statement by id")
        REMOVE_STATEMENT_BY_VALUE = "remove_statement_by_value", _(
            "Remove statement by value"
        )
        #
        REMOVE_QUALIFIER = "remove_qualifier", _("Remove qualifier")
        REMOVE_REFERENCE = "remove_reference", _("Remove reference")
        #
        SET_SITELINK = "set_sitelink", _("Set sitelink")
        SET_LABEL = "set_label", _("Set label")
        SET_DESCRIPTION = "set_description", _("Set description")
        #
        REMOVE_SITELINK = "remove_sitelink", _("Remove sitelink")
        REMOVE_LABEL = "remove_label", _("Remove label")
        REMOVE_DESCRIPTION = "remove_description", _("Remove description")
        #
        ADD_ALIAS = "add_alias", _("Add alias")
        REMOVE_ALIAS = "remove_alias", _("Remove alias")

    operation = models.TextField(
        null=True,
        blank=True,
        choices=Operation,
    )

    # -------
    # Running fields
    # -------
    status = models.IntegerField(
        default=STATUS_INITIAL, choices=STATUS_CHOICES, null=False, db_index=True
    )
    value_type_verified = models.BooleanField(default=False)

    # -------
    # Post-running fields
    # -------
    message = models.TextField(blank=True, null=True)
    response_id = models.CharField(max_length=48, null=True, blank=True)

    class Error(models.TextChoices):
        OP_NOT_IMPLEMENTED = "op_not_implemented", _("Operation not implemented")
        NO_STATEMENTS_PROPERTY = "no_statements_property", _(
            "No statements for given property"
        )
        NO_STATEMENTS_VALUE = "no_statements_value", _("No statements with given value")
        NO_QUALIIFERS = "no_qualifiers", _("No qualifiers with given value")
        NO_REFERENCE_PARTS = "no_reference_parts", _(
            "No reference parts with given value"
        )
        SITELINK_INVALID = "sitelink_invalid", _("The sitelink id is invalid")
        COMBINING_COMMAND_FAILED = "combining_failed", _("The next command failed")
        API_USER_ERROR = "api_user_error", _("API returned a User error")
        API_SERVER_ERROR = "api_server_error", _("API returned a server error")
        LAST_NOT_EVALUATED = "last_not_evaluated", _("LAST could not be evaluated.")

    error = models.TextField(
        null=True,
        blank=True,
        choices=Error,
    )

    def __str__(self):
        return f"Batch #{self.batch.pk} Command #{self.pk} ##{self.index}"

    # -----------------
    # Status-changing methods
    # -----------------

    def start(self):
        logger.debug(f"[{self}] running...")
        self.status = BatchCommand.STATUS_RUNNING
        self.save()

    def finish(self):
        logger.info(f"[{self}] finished")
        self.status = BatchCommand.STATUS_DONE
        if self.is_id_last_or_create_item():
            self.set_entity_id(self.response_id)
        self.save()
        self.propagate_to_previous_commands()

    def error_with_value(self, value: Error, message: str = None):
        self.error = value
        if message is not None:
            self.error_with_message(message)
        else:
            self.error_with_message(value.label)

    def error_with_exception(self, exception: Exception):
        message = getattr(exception, "message", str(exception))
        self.error_with_message(message)

    def error_with_message(self, message):
        logger.error(f"[{self}] error: {message}")
        self.message = message
        self.status = BatchCommand.STATUS_ERROR
        self.save()
        self.propagate_to_previous_commands()

    def propagate_to_previous_commands(self):
        for cmd in getattr(self, "previous_commands", []):
            logger.debug(f"[{self}] propagating to [{cmd}]")
            cmd.status = self.status
            if self.is_error_status():
                cmd.error = self.Error.COMBINING_COMMAND_FAILED
                cmd.message = cmd.error.label
            elif cmd.is_id_last_or_create_item():
                cmd.set_entity_id(self.entity_id())
            cmd.save()

    # -----------------
    # Entity id methods
    # -----------------

    @property
    def entity_info(self):
        entity_id = self.entity_id()
        return f"[{entity_id}]" if entity_id else ""

    def entity_id(self):
        item = self.json.get("item", None)
        if item:
            return item
        return self.json.get("entity", {}).get("id", None)

    def set_entity_id(self, value):
        if "item" in self.json:
            self.json["item"] = value
        else:
            self.json.setdefault("entity", {})
            self.json["entity"]["id"] = value

    def entity_url(self):
        entity_id = self.entity_id()
        base = self.batch.wikibase.url
        if entity_id and entity_id != "LAST":
            return f"{base}/entity/{entity_id}"
        else:
            return ""

    # -----------------
    # Property methods
    # -----------------

    @property
    def status_info(self):
        return self.get_status_display().upper()

    @property
    def language(self):
        return self.json.get("language", "")

    @property
    def sitelink(self):
        return self.json.get("site", "")

    @property
    def what(self):
        return self.json.get("what", "").upper()

    @property
    def what_plural_lowercase(self):
        what = self.json.get("what")
        if what == "alias":
            return "aliases"
        elif what:
            return f"{what}s"

    @property
    def language_or_sitelink(self):
        return self.language if self.language else self.sitelink

    @property
    def prop(self):
        return self.json.get("property", "")

    @property
    def type(self):
        return self.json.get("type", "").upper()

    @property
    def value_dict(self):
        if not hasattr(self, "_value_dict"):
            self._value_dict = self.json.get("value") or {}
        return self._value_dict

    @property
    def value(self):
        return self.value_dict.get("value", "")

    @property
    def value_type(self):
        return self.value_dict.get("type", "")

    @property
    def value_value(self):
        return self.value_dict.get("value", "")

    def parser_value_to_api_value(self, parser_value):
        if parser_value["type"] in ["novalue", "somevalue"]:
            return {
                "type": parser_value["type"],
            }
        else:
            return {
                "type": "value",
                "content": parser_value["value"],
            }

    @property
    def statement_api_value(self):
        self.update_quantity_units_if_needed()
        return self.parser_value_to_api_value(self.json["value"])

    def update_quantity_units_if_needed(self):
        # TODO: maybe we can add this elsewhere,
        # because `statement_api_value` above is called a lot
        value = self.json["value"]
        base = self.batch.wikibase.url.replace("https://", "http://")
        if (
            value["type"] == "quantity"
            and value["value"]["unit"] != "1"
            and base not in value["value"]["unit"]
        ):
            unit_id = value["value"]["unit"]
            full_unit = f"{base}/entity/Q{unit_id}"
            value["value"]["unit"] = full_unit

    def update_statement(self, st):
        st.setdefault("property", {"id": self.prop})
        st.setdefault("value", self.statement_api_value)
        quals, refs, rank = (
            self.qualifiers_for_api(),
            self.references_for_api(),
            self.statement_rank(),
        )
        if quals:
            st.setdefault("qualifiers", [])
            st["qualifiers"].extend(quals)
        if refs:
            st.setdefault("references", [])
            st["references"].extend(refs)
        if rank:
            st["rank"] = rank

    def qualifiers_for_api(self):
        return [
            {
                "property": {"id": q["property"]},
                "value": self.parser_value_to_api_value(q["value"]),
            }
            for q in self.qualifiers()
        ]

    def references_for_api(self):
        all_refs = []
        for ref in self.references():
            fixed_parts = []
            for part in ref:
                fixed_parts.append(
                    {
                        "property": {"id": part["property"]},
                        "value": self.parser_value_to_api_value(part["value"]),
                    }
                )
            all_refs.append({"parts": fixed_parts})
        return all_refs

    def qualifiers(self):
        return self.json.get("qualifiers", [])

    def references(self):
        return self.json.get("references", [])

    def reference_parts(self):
        parts = []
        for ref in self.references():
            parts.extend(ref)
        return parts

    def statement_rank(self):
        return self.json.get("rank")

    def is_in_qualifiers(self, qualifier: dict):
        """
        Checks if a qualifier is contained within the command's qualifiers.
        """
        property_id = qualifier["property"]["id"]
        api_value = qualifier["value"]
        for q in self.qualifiers_for_api():
            if q["property"]["id"] == property_id and q["value"] == api_value:
                return True
        return False

    def is_part_in_references(self, reference_part: dict):
        """
        Checks if a reference part is contained within the command's references.
        """
        property_id = reference_part["property"]["id"]
        api_value = reference_part["value"]
        for r in self.references_for_api():
            for part in r.get("parts", []):
                if part["property"]["id"] == property_id and part["value"] == api_value:
                    return True
        return False

    # -----------------
    # verification methods
    # -----------------

    def is_add(self):
        return self.action == BatchCommand.ACTION_ADD

    def is_add_statement(self):
        return self.is_add() and self.what == "STATEMENT"

    def is_add_label_description_alias(self):
        return self.is_add() and self.what in ["DESCRIPTION", "LABEL", "ALIAS"]

    def is_remove(self):
        return self.action == BatchCommand.ACTION_REMOVE

    def is_add_or_remove_command(self):
        return self.action in [BatchCommand.ACTION_ADD, BatchCommand.ACTION_REMOVE]

    def is_merge_command(self):
        return self.action == BatchCommand.ACTION_MERGE

    def is_label_alias_description_command(self):
        return self.what in ["DESCRIPTION", "LABEL", "ALIAS"]

    def is_sitelink_command(self):
        return self.what == "SITELINK"

    def is_error_status(self):
        return self.status == BatchCommand.STATUS_ERROR

    def is_not_create_item(self):
        return self.operation != self.Operation.CREATE_ITEM

    def is_id_last_or_create_item(self):
        return (
            self.entity_id() == "LAST" or self.operation == self.Operation.CREATE_ITEM
        )

    # # -----------------
    # # LAST related methods
    # # -----------------

    def update_last_id(self, last_id=None):
        """
        Updates this command's entity id, if it's LAST, to the argument.
        """
        if self.entity_id() == "LAST" and last_id is not None:
            self.set_entity_id(last_id)
            self.save()

    # -----------------
    # Wikibase API basic methods
    # -----------------

    def run(self, client: Client):
        """
        Sends the command to the Wikibase API. This method should not raise exceptions.
        """
        # If we alredy have an error, just propagate backwards

        if self.status == BatchCommand.STATUS_ERROR:
            return self.propagate_to_previous_commands()

        # Ignore when not INITIAL
        if self.status != BatchCommand.STATUS_INITIAL:
            return

        self.start()

        try:
            self.verify_value_types(client)
            if self.can_combine_with_next:
                self.update_combining_state(client)
            else:
                response_json = self.send_to_api(client)
                try:
                    self.response_id = response_json.get("id")
                except AttributeError:
                    pass
                self.finish()
        except NotImplementedError:
            self.error_with_value(self.Error.OP_NOT_IMPLEMENTED)
        except NoStatementsForThatProperty:
            self.error_with_value(self.Error.NO_STATEMENTS_PROPERTY)
        except NoStatementsWithThatValue:
            self.error_with_value(self.Error.NO_STATEMENTS_VALUE)
        except NoQualifiers:
            self.error_with_value(self.Error.NO_QUALIIFERS)
        except NoReferenceParts:
            self.error_with_value(self.Error.NO_REFERENCE_PARTS)
        except LastCouldNotBeEvaluated:
            self.error_with_value(self.Error.LAST_NOT_EVALUATED)
        except UserError as e:
            if e.response_message == "Invalid path parameter: 'site_id'":
                self.error_with_value(self.Error.SITELINK_INVALID)
            else:
                self.error_with_value(self.Error.API_USER_ERROR, e.message)
        except ServerError as e:
            self.error_with_value(self.Error.API_SERVER_ERROR, e.message)
        except (ApiException, Exception) as e:
            self.error_with_exception(e)

    def edit_summary(self):
        """
        Returns the final edit summary.

        It joins the user supplied summary with
        the identification necessary for EditGroups.

        Also joins the summary from the previous combined commands.
        """
        summaries = [self.user_summary]
        summaries.extend(
            [c.user_summary for c in getattr(self, "previous_commands", [])]
        )
        combined = " | ".join([s for s in summaries[::-1] if bool(s)])
        editgroups = self.editgroups_summary()
        if editgroups:
            return f"{editgroups}: {combined}" if combined else editgroups
        else:
            return combined

    def editgroups_summary(self):
        """
        Returns the EditGroups notice to put into the summary.
        """
        # Our regex for EditGroups:
        # ".*\[\[:toollabs:TOOLFORGE_TOOL_NAME/batch/(\d+)\|.*"
        tool = settings.TOOLFORGE_TOOL_NAME
        if tool is not None:
            batch_id = self.batch.id
            return f"[[:toollabs:{tool}/batch/{batch_id}|batch #{batch_id}]]"
        else:
            return ""

    def operation_is_combinable(self):
        """
        Returns True for commands that work by modifying the entity's json,
        thus being combinable with future commands.
        """
        return self.operation in (
            self.Operation.CREATE_ITEM,
            self.Operation.SET_STATEMENT,
            self.Operation.CREATE_STATEMENT,
            self.Operation.REMOVE_STATEMENT_BY_VALUE,
            self.Operation.REMOVE_QUALIFIER,
            self.Operation.REMOVE_REFERENCE,
            self.Operation.ADD_ALIAS,
            self.Operation.SET_LABEL,
            self.Operation.SET_DESCRIPTION,
            self.Operation.SET_SITELINK,
            self.Operation.REMOVE_ALIAS,
            self.Operation.REMOVE_LABEL,
            self.Operation.REMOVE_DESCRIPTION,
            self.Operation.REMOVE_SITELINK,
        )

    @property
    def can_combine_with_next(self):
        """
        Defines if the command should just return the
        modified entity json, because connecting to the API
        will be done by the next command.
        """
        return getattr(self, "_can_combine_with_next", False)

    def check_combination(self, state: CombiningState, next: Optional["BatchCommand"]):
        """
        Caches the previous_entity_json as given, even if None.

        Checks combination with next command if available.
        """
        self._can_combine_with_next = (
            self.batch.combine_commands
            and self.operation_is_combinable()
            and next is not None
            and next.operation_is_combinable()
            and next.is_not_create_item()
            and self.has_combinable_id_with(next)
        )
        self.previous_entity_json = state.entity
        self.previous_commands = state.commands

    def has_combinable_id_with(self, next: "BatchCommand"):
        """
        Returns True if `self` is CREATE_ITEM and `next`
        has LAST as entity id, or if both have the same entity id.
        """
        return (
            self.operation == self.Operation.CREATE_ITEM and next.entity_id() == "LAST"
        ) or (self.entity_id() == next.entity_id())

    def update_combining_state(self, client: Client):
        """
        Updates the combining state, appending itself
        as a command and updating the current entity json
        with the command's modifications.
        """
        commands = [self, *getattr(self, "previous_commands", [])]
        entity = self.get_final_entity_json(client)
        self._final_combining_state = CombiningState(
            commands=commands,
            entity=entity,
        )
        logger.debug(f"[{self}] combined with next")

    @property
    def final_combining_state(self):
        return getattr(self, "_final_combining_state", CombiningState.empty())

    def get_original_entity_json(self, client: Client):
        """
        Returns the original entity json.

        Used for calculating the final patch send to the API.

        If the command has no previous_entity_json, will use this
        to save a copy into it, so that the get_previous_entity_json
        method does not have to call the API agian.
        """
        entity = client.get_entity(self.entity_id())
        if getattr(self, "previous_entity_json", None) is None:
            self.previous_entity_json = copy.deepcopy(entity)
        return entity

    def get_entity_or_empty_item(self, client: Client):
        """
        Calls the API to get the entity json or returns
        an empty item if this command is a CREATE_ITEM.
        """
        if self.operation == self.Operation.CREATE_ITEM:
            return {
                "type": "item",
                "labels": {},
                "descriptions": {},
                "aliases": {},
                "statements": {},
                "sitelinks": {},
                "id": None,
            }
        else:
            if self.entity_id() == "LAST":
                raise LastCouldNotBeEvaluated()
            return client.get_entity(self.entity_id())

    def get_previous_entity_json(self, client: Client):
        """
        Returns the previous entity json. Has cache.

        Used for calculating the final entity json to pass along
        to the next command.
        """
        cached = getattr(self, "previous_entity_json", None)
        entity = cached if cached else self.get_entity_or_empty_item(client)
        return entity

    def get_final_entity_json(self, client: Client) -> dict:
        """
        Returns the final entity json, applying the operations.
        """
        entity = self.get_previous_entity_json(client)
        self.update_entity_json(entity)
        return entity

    def update_entity_json(self, entity: dict):
        """
        Modifies the entity json in-place.
        """
        if self.operation in (
            self.Operation.SET_STATEMENT,
            self.Operation.CREATE_STATEMENT,
        ):
            self._update_entity_statements(entity)
        elif self.operation == self.Operation.REMOVE_STATEMENT_BY_VALUE:
            self._remove_entity_statement(entity)
        elif self.operation in (self.Operation.ADD_ALIAS, self.Operation.REMOVE_ALIAS):
            self._update_entity_aliases(entity)
        elif self.operation in (
            self.Operation.REMOVE_QUALIFIER,
            self.Operation.REMOVE_REFERENCE,
        ):
            self._remove_qualifier_or_reference(entity)
        elif self.operation == self.Operation.SET_SITELINK:
            entity["sitelinks"][self.sitelink] = {"title": self.value_value}
        elif self.operation in (
            self.Operation.SET_LABEL,
            self.Operation.SET_DESCRIPTION,
        ):
            entity[self.what_plural_lowercase][self.language] = self.value_value
        elif self.operation in (
            self.Operation.REMOVE_LABEL,
            self.Operation.REMOVE_DESCRIPTION,
            self.Operation.REMOVE_SITELINK,
        ):
            # the "" is there to make the `pop` safe
            entity[self.what_plural_lowercase].pop(self.language_or_sitelink, "")

    def _get_statement(self, entity: dict) -> Optional[dict]:
        """
        Returns the statement that matches the command's value.

        Returns `None` if there is no matching statement.
        """
        statements = entity["statements"].setdefault(self.prop, [])
        for i, statement in enumerate(statements):
            if statement["value"] == self.statement_api_value:
                return statement
        return None

    def _update_entity_statements(self, entity: dict):
        """
        Modifies the entity json statements in-place.

        If it's SET_STATEMENT, tries to get the current statement to edit it,
        creating if there is none.

        If it's CREATE_STATEMENT, always creates the statement
        """
        if self.operation == self.Operation.SET_STATEMENT:
            statement = self._get_statement(entity)
        if self.operation == self.Operation.CREATE_STATEMENT or statement is None:
            entity["statements"].setdefault(self.prop, [])
            entity["statements"][self.prop].append(dict())
            statement = entity["statements"][self.prop][-1]
        self.update_statement(statement)

    def _remove_qualifier_or_reference(self, entity: dict):
        """
        Removes a qualifier or a reference from the entity.
        """
        statement = self._get_statement(entity)
        statement = statement if statement else {}
        found_qualifier = False
        found_ref_part = False
        for i, qual in enumerate(statement.get("qualifiers", [])):
            if self.is_in_qualifiers(qual):
                statement["qualifiers"].pop(i)
                found_qualifier = True
                break
        for i, ref in enumerate(statement.get("references", [])):
            for j, part in enumerate(ref["parts"]):
                if self.is_part_in_references(part):
                    statement["references"][i]["parts"].pop(j)
                    found_ref_part = True
                    break
            if found_ref_part:
                break
        if not found_qualifier and len(self.qualifiers_for_api()) > 0:
            raise NoQualifiers()
        if not found_ref_part and len(self.references_for_api()) > 0:
            raise NoReferenceParts()

    def _remove_entity_statement(self, entity: dict):
        """
        Removes an entity statement with the command's value, in-place.
        """
        statements = entity["statements"].get(self.prop, [])
        if len(statements) == 0:
            raise NoStatementsForThatProperty(self.entity_id(), self.prop)

        for i, statement in enumerate(statements):
            if statement["value"] == self.statement_api_value:
                return entity["statements"][self.prop].pop(i)
        raise NoStatementsWithThatValue(
            self.entity_id(), self.prop, self.statement_api_value
        )

    def _update_entity_aliases(self, entity: dict):
        """
        Update the entity's aliases, adding or removing.
        """
        entity["aliases"].setdefault(self.language, [])
        aliases = entity["aliases"][self.language]
        if self.operation == self.Operation.ADD_ALIAS:
            for alias in self.value_value:
                if alias not in aliases:
                    aliases.append(alias)
        elif self.operation == self.Operation.REMOVE_ALIAS:
            new = [a for a in aliases if a not in self.value_value]
            if len(new) > 0:
                entity["aliases"][self.language] = new
            else:
                # It is not possible to leave a language with 0 aliases
                entity["aliases"].pop(self.language)

    def entity_patch(self, client: Client):
        """
        Calculates the entity json patch to send to the API.

        The cached entity json will be the baseline to work with,
        but the patch needs to be calculated using the original
        entity json, since that's what exists in the wikibase server.

        The json patch is a series of operations that tell the API
        how to modify the entity's json.
        """
        original = self.get_original_entity_json(client)
        entity = self.get_previous_entity_json(client)
        self.update_entity_json(entity)
        return jsonpatch.JsonPatch.from_diff(original, entity).patch

    # ----------------
    # REST API methods
    # ----------------

    def api_payload(self, client: Client):
        """
        Returns the data that is sent to the Wikibase API through the body.
        """
        if self.operation == self.Operation.CREATE_ITEM:
            return {"item": {}}
        if self.operation_is_combinable():
            if self.is_id_last_or_create_item():
                return {"item": self.get_final_entity_json(client)}
            else:
                return {"patch": self.entity_patch(client)}
        return {}

    def api_body(self, client: Client):
        """
        Returns the final Wikibase API body.

        Joins the api payload with bot marking = False and the edit summary.
        """
        body = self.api_payload(client)
        body["bot"] = False
        body["comment"] = self.edit_summary()
        return body

    def send_to_api(self, client: Client) -> dict:
        """
        Sends the operation to the Wikibase REST API.

        # Raises

        - `NotImplementedError` if the operation
        is not implemented.
        """
        if self.operation == self.Operation.CREATE_PROPERTY:
            raise NotImplementedError()
        method, endpoint = self.operation_method_and_endpoint(client)
        body = self.api_body(client)
        return client.wikibase_request_wrapper(method, endpoint, body)

    # -----------------
    # Auxiliary methods for Wikibase API interaction
    # -----------------

    def operation_method_and_endpoint(self, client: Client):
        """
        Returns a tuple of HTTP method and the endpoint
        necessary for the operation.
        """
        if self.operation_is_combinable():
            if self.is_id_last_or_create_item():
                return ("POST", "/entities/items")
            else:
                return ("PATCH", Client.wikibase_entity_endpoint(self.entity_id()))
        match self.operation:
            case self.Operation.REMOVE_STATEMENT_BY_ID:
                statement_id = self.json["id"]
                return ("DELETE", f"/statements/{statement_id}")

    # -----------------
    # Visualization/label methods
    # -----------------

    @classmethod
    def load_labels(cls, client: Client, commands: List["BatchCommand"], language="en"):
        """
        This commands loads labels in the command entity ids
        in the `display_label` attribute.

        If there is no label returned from the API, it
        sets `display_label` as None.

        It loops twice through the commands list.
        """
        ids = set()
        entities = dict()

        for command in commands:
            id = command.entity_id()
            if id is not None and id != "LAST":
                ids.add(command.entity_id())
        ids = list(ids)

        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            api_json = client.get_multiple_labels(batch_ids, language)
            entities.update(api_json.get("entities", {}))

        for command in commands:
            id = command.entity_id()
            response_labels = entities.get(id, {}).get("labels", {})
            label = response_labels.get(language, {}).get("value", None)
            if not label:
                label = response_labels.get("en", {}).get("value", None)
            command.display_label = label

    # -----------------
    # Value type verification
    # -----------------

    def verify_value_types(self, client: Client):
        """
        Checks if the supplied value type is allowed by the property's required value type.

        Makes that check for the statement and for qualifiers and references.

        It sets the status to ERROR if the value type is invalid, updates the message,
        and raises InvalidPropertyValueType.

        Only makes sense in commands that require value type verification
        (see self._should_verify_value_types)

        # Raises

        - InvalidPropertyValueType: when the value type is not valid.
        """
        if self.should_verify_value_types():
            try:
                client.verify_value_type(self.prop, self.value_type)
                for q in self.qualifiers():
                    client.verify_value_type(q["property"], q["value"]["type"])
                for p in self.reference_parts():
                    client.verify_value_type(p["property"], p["value"]["type"])
            except InvalidPropertyValueType as e:
                self.error_with_message(e.message)
                raise e

        self.value_type_verified = True
        self.save()

    def should_verify_value_types(self):
        """
        Checks if this command needs value type verification.

        1) It needs to be not verified yet, of course.

        2) It needs if it is of the following types/actions:

        - Statement addition
        """
        is_not_verified_yet = not self.value_type_verified
        is_needed_actions = self.is_add_statement()
        return is_not_verified_yet and is_needed_actions

    # -----------------
    # Meta
    # -----------------

    class Meta:
        verbose_name = _("Batch Command")
        verbose_name_plural = _("Batch Commands")
        index_together = ("batch", "index")
