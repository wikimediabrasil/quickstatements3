import requests
import logging
from typing import List

from django.core.cache import cache as django_cache
from django.conf import settings
from django.contrib.auth.models import User
from requests.exceptions import HTTPError

from web.models import Token
from web.oauth import oauth

from .exceptions import EntityTypeNotImplemented
from .exceptions import NonexistantPropertyOrNoDataType
from .exceptions import UserError
from .exceptions import ServerError
from .exceptions import NoToken
from .exceptions import UnauthorizedToken
from .exceptions import InvalidPropertyValueType
from .exceptions import NoValueTypeForThisDataType

logger = logging.getLogger("qsts3")


def cache_with_first_arg(cache_name):
    """
    Returns a decorator that caches the value in a dictionary cache with `cache_name`,
    using as key the first argument of the method.

    If there is not first argument or first keyword argument, it uses a generic key.
    """

    def decorator(method):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, cache_name):
                setattr(self, cache_name, {})

            if len(args) >= 1:
                key = args[0]
            elif len(kwargs) >= 1:
                key = next(iter(kwargs.values()))
            else:
                key = "key"

            cache = getattr(self, cache_name)

            if cache.get(key) is not None:
                return cache.get(key)
            else:
                value = method(self, *args, **kwargs)
                cache[key] = value
                return value

        return wrapper

    return decorator


class Client:
    BASE_REST_URL = settings.BASE_REST_URL
    ENDPOINT_PROFILE = f"{BASE_REST_URL}/oauth2/resource/profile"
    WIKIBASE_URL = f"{BASE_REST_URL}/wikibase/v1"

    def __init__(self, token: Token):
        self.token = token
        self.value_type_cache = {}
        self.labels_cache = {}

    def __str__(self):
        return "API Client with token [redacted]"

    # ---
    # Constructors
    # ---

    @classmethod
    def from_token(cls, token: Token):
        return cls(token)

    @classmethod
    def from_user(cls, user: User):
        return cls.from_username(user.username)

    @classmethod
    def from_username(cls, username: str):
        try:
            token = Token.objects.get(user__username=username)
            return cls.from_token(token)
        except Token.DoesNotExist:
            raise NoToken(username)

    # ---
    # OAuth Token
    # ---
    def refresh_token_if_needed(self):
        """
        The OAuth access token token can expire.

        This will check if it's near expiration and
        make a call for a new one with the refresh token
        if necessary.
        """
        if self.token.is_expired() and self.token.refresh_token:
            self.refresh_token()

    def refresh_token(self):
        """
        Refreshes the current `Token` using its refresh token.
        """
        logger.debug(f"[{self.token}] Refreshing OAuth token...")

        try:
            new_token = oauth.mediawiki.fetch_access_token(
                grant_type="refresh_token",
                refresh_token=self.token.refresh_token,
            )
        except HTTPError:
            raise UnauthorizedToken()

        self.token.update_from_full_token(new_token)

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
        self.refresh_token_if_needed()
        response = requests.get(url, headers=self.headers())
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
            self._profile = self.get(self.ENDPOINT_PROFILE).json()
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
        return "autoconfirmed" in self.get_user_groups()

    def get_is_blocked(self):
        profile = self.get_profile()
        return profile.get("blocked", False)

    # ---
    # Wikibase utilities
    # ---
    def wikibase_url(self, endpoint):
        return f"{self.WIKIBASE_URL}{endpoint}"

    @staticmethod
    def wikibase_entity_endpoint(entity_id, entity_endpoint=""):
        if entity_id.startswith("Q"):
            base = "/entities/items"
        elif entity_id.startswith("P"):
            base = "/entities/properties"
        else:
            raise EntityTypeNotImplemented(entity_id)

        return f"{base}/{entity_id}{entity_endpoint}"

    def wikibase_entity_url(self, entity_id, entity_endpoint):
        endpoint = self.wikibase_entity_endpoint(entity_id, entity_endpoint)
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

        self.refresh_token_if_needed()

        logger.debug(f"{method} request at {url} | sending with body {body}")

        res = getattr(requests, method.lower())(url, **kwargs)

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
            res = self.get(url).json()
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
        key = f"{self.WIKIBASE_URL}/property-data-types"

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

    def action_api_url(self):
        return self.BASE_REST_URL.replace("/w/rest.php", "/w/api.php")

    def get_multiple_labels(self, entity_ids: List[str], language: str) -> dict:
        """
        Obtains multiple labels using the Action API.

        When the REST API allows this, we can swicth to it.

        Returns as an easy to use dictionary with the entity ids
        as keys and the labels as values, which can be empty strings.
        """
        action_api = self.action_api_url()
        languages = f"{language}|en" if language != "en" else "en"
        ids = "|".join(entity_ids)
        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "labels",
            "languages": languages,
            "ids": ids,
        }
        logger.debug(
            f"Sending GET request at {action_api}, languages={languages}, ids={ids}"
        )
        self.refresh_token_if_needed()
        res = requests.get(action_api, headers=self.headers(), params=params)
        self.raise_for_status(res)
        return res.json()
