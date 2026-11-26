"""
Server lag monitoring, used to pause running batches while a Wikibase is lagged.

The Wikibase REST API has no `maxlag` parameter, so instead we periodically ask the
Action API for the current lag and pause batches while it is above
`settings.MAXLAG_THRESHOLD`.

See https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
"""

import logging
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("qsts3")

USER_AGENT = "QuickStatements 3.0"
TIMEOUT = (5, 10)  # connect, read

_MISSING = object()


def fetch_lag(api_url: str) -> Optional[float]:
    """
    Asks the Action API for the current lag, in seconds.

    Sending `maxlag=-1` makes the API always answer with a `maxlag` error carrying
    the current lag. On Wikidata this is the same value that `maxlag` is compared
    against, which includes the query service update lag, not only database
    replication lag.

    Returns None if the lag could not be determined.
    """
    params = {"action": "query", "titles": "MediaWiki", "format": "json", "maxlag": -1}
    try:
        response = requests.get(
            api_url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"Could not fetch the current lag from {api_url}: {e}")
        return None

    error = data.get("error") if isinstance(data, dict) else None
    if error and error.get("code") == "maxlag":
        try:
            return float(error["lag"])
        except (KeyError, TypeError, ValueError):
            pass

    # No lag error even with maxlag=-1: the wiki isn't reporting any lag.
    if error is None:
        return 0.0

    logger.warning(f"Unexpected response while fetching the current lag from {api_url}: {data}")
    return None


def get_lag(api_url: str) -> Optional[float]:
    """
    Returns the current lag of the wiki at `api_url`, in seconds,
    cached for `settings.MAXLAG_CHECK_INTERVAL` seconds.

    Returns None if the lag could not be determined.
    """
    key = f"maxlag:{api_url}"
    lag = cache.get(key, _MISSING)
    if lag is _MISSING:
        lag = fetch_lag(api_url)
        # Unknown lag (None) is cached too, so a failing API isn't queried on every command.
        cache.set(key, lag, settings.MAXLAG_CHECK_INTERVAL)
    return lag


def is_lagged(api_url: str) -> tuple[bool, Optional[float]]:
    """
    Returns whether batches editing the wiki at `api_url` should pause, and the lag.

    If the lag can't be determined, batches are not paused, so an Action API outage
    or a Wikibase without the Action API doesn't stop every batch.
    """
    if not settings.MAXLAG_PAUSE_ENABLED:
        return False, None
    lag = get_lag(api_url)
    return lag is not None and lag > settings.MAXLAG_THRESHOLD, lag
