"""Caching module for storing and retrieving ECB exchange rate data.

This module provides a simple disk-backed cache for ECB exchange rates and
contains deterministic seams to make caching behavior testable:

- Override the `clock_getter` callable to control the current time used for
  TTL calculations in tests.
- Override the `cache_factory` callable to provide a test-friendly Cache
  implementation (for example, an in-memory fake).

Public API (do not change):
- get_rates_from_cache() -> Optional[Dict[str, Any]]
- set_rates_to_cache(data: Dict[str, Any]) -> None
- clear_cache() -> None

Behavior:
- Cached data is stored under the key defined by CACHE_KEY using diskcache.
- TTL (expire) is computed to the next ECB update time: 16:00 CET on the next
  business day (skipping weekends and TARGET2 holidays approximated by DE
  holidays).
- On I/O or serialization errors the module logs a recoverable error and
  falls back to an in-memory no-op cache to preserve external behavior.
"""

import logging
import os
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, Optional

import holidays
from diskcache import Cache

logger = logging.getLogger(__name__)

CACHE_KEY = "ecb_rates"
ECB_UPDATE_TIME = time(16, 0)  # 16:00 CET

# Test seams: these can be overridden by tests to make behavior deterministic.
# Example: caching.clock_getter = lambda: datetime(2024, 1, 2, 12, 0)
clock_getter: Callable[[], datetime] = datetime.now
# Example: caching.cache_factory = lambda path: InMemoryCache()
cache_factory: Callable[[str], Cache] = Cache


class _FallbackCache:
    """A minimal in-memory fallback cache used when disk-backed cache is unavailable.

    This implements only the methods used by this module: get, set, delete.
    The expire argument is accepted and ignored.

    Complexity:
    - get: average O(1) time, O(n) worst-case depending on dict hash collisions.
    - set: average O(1) time, O(n) worst-case depending on rehashing.
    - delete: average O(1) time.
    Memory:
    - O(m) where m is the number of cached keys stored in the in-memory fallback.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


def _get_cache_directory() -> str:
    """Return the directory path used for the disk cache.

    The directory can be configured via the ECB_CACHE environment variable.

    Complexity: O(1)
    """
    return os.environ.get("ECB_CACHE", ".cache/ecbrates")


def _open_cache() -> Cache:
    """Open and return a Cache instance, falling back to an in-memory cache on error.

    Ensures the cache directory exists. Any I/O or serialization-related exceptions
    are caught and logged; callers receive a functional fallback that preserves
    external behavior.

    Complexity: O(1) for path resolution and object creation; filesystem operations
    may block and introduce I/O latency depending on environment.
    """
    cache_dir = _get_cache_directory()
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError as exc:
        logger.exception(
            "Failed to create cache directory '%s'. Falling back to in-memory cache.",
            cache_dir,
        )
        return _FallbackCache()

    try:
        return cache_factory(cache_dir)
    except Exception as exc:
        logger.exception(
            "Failed to open disk cache at '%s' using cache_factory. Falling back to in-memory cache.",
            cache_dir,
        )
        return _FallbackCache()


def _get_target_holiday_calendar() -> holidays.HolidayBase:
    """Return a holiday calendar approximating TARGET2 holidays.

    Currently uses German (DE) holidays as a reasonable proxy for TARGET2.

    Complexity: Construction is generally O(1) but underlying holiday generation
    may compute holidays lazily. Membership checks on the returned object may be
    linear depending on implementation; callers that perform repeated membership
    tests should materialize a set of dates for O(1) lookups.
    """
    try:
        return holidays.country_holidays("DE")
    except Exception:
        # In the unlikely event the holidays library fails, log and use an empty calendar.
        logger.exception("Failed to load TARGET2 holiday calendar; proceeding without holidays.")
        return holidays.HolidayBase()


def _get_next_update_ttl() -> int:
    """Calculate TTL in seconds until the next ECB update.

    The next update is at 16:00 CET on the next business day (skipping weekends
    and TARGET2 holidays as approximated by the DE holiday calendar).

    To avoid potentially repeated linear scans during holiday membership checks
    when advancing the date one day at a time, this function materializes the
    holiday calendar keys into a set once and uses O(1) membership checks
    thereafter.

    Returns:
        int: Number of seconds until the next update. If calculation fails,
             returns a conservative default of 60 seconds.

    Complexity:
    - Let k be the number of days advanced until the next business day.
      Building the holiday date set is O(h) where h is the number of holidays
      materialized (done once). Membership checks inside the loop are O(1),
      so overall time is O(h + k). In typical usage h and k are small.
    """
    try:
        now = clock_getter()
        holiday_calendar = _get_target_holiday_calendar()

        next_update = now.replace(
            hour=ECB_UPDATE_TIME.hour, minute=ECB_UPDATE_TIME.minute, second=0, microsecond=0
        )

        if now.time() >= ECB_UPDATE_TIME:
            next_update += timedelta(days=1)

        # Materialize holiday dates into a set once to ensure repeated membership
        # tests in the loop below are O(1) each instead of potentially linear.
        try:
            # holiday_calendar is mapping-like: keys() yields the holiday dates
            holiday_dates = set(holiday_calendar.keys())
        except Exception:
            # Fallback: attempt to iterate directly; if that fails, use empty set.
            try:
                holiday_dates = set(holiday_calendar)
            except Exception:
                holiday_dates = set()

        # Advance until next weekday that's not a TARGET2 holiday
        while next_update.weekday() >= 5 or next_update.date() in holiday_dates:
            next_update += timedelta(days=1)

        ttl_seconds = int((next_update - now).total_seconds())
        logger.debug("Calculated TTL: %d seconds until next ECB update at %s", ttl_seconds, next_update)
        return max(ttl_seconds, 0)
    except Exception:
        logger.exception("Error calculating TTL for next ECB update; defaulting to 60 seconds.")
        return 60


def get_rates_from_cache() -> Optional[Dict[str, Any]]:
    """Retrieve exchange rate data from the cache.

    Returns:
        Optional[Dict[str, Any]]: Cached exchange rate data if present and retrievable,
        otherwise None. Recoverable I/O/serialization errors are logged and result in
        returning None.

    Complexity: O(1) expected for cache lookup; underlying disk-backed cache may
    incur I/O latency.
    """
    cache = _open_cache()
    try:
        data = cache.get(CACHE_KEY, default=None)
    except Exception:
        logger.exception("Error reading ECB rates from cache; treating as cache miss.")
        return None

    if data is not None:
        logger.info("Cache hit for ECB rates.")
    else:
        logger.info("Cache miss for ECB rates.")
    return data


def set_rates_to_cache(data: Dict[str, Any]) -> None:
    """Store exchange rate data in the cache with a dynamically computed TTL.

    Args:
        data: Exchange rate data to cache. Errors during cache write are logged;
              the function returns without raising to preserve external behavior.

    Complexity: Computing TTL is O(h + k) where h is the cost to materialize holidays
    and k days advanced; the cache.set operation is expected O(1) amortized but may
    involve I/O for disk-backed caches.
    """
    cache = _open_cache()
    ttl = _get_next_update_ttl()
    try:
        # diskcache's Cache.set accepts an 'expire' argument in seconds.
        cache.set(CACHE_KEY, data, expire=ttl)
        logger.info("ECB rates cached with dynamic TTL of %d seconds.", ttl)
    except Exception:
        logger.exception("Error writing ECB rates to cache; write ignored.")


def clear_cache() -> None:
    """Clear the ECB rates cache.

    Errors during cache deletion are logged and swallowed to preserve external
    behavior.

    Complexity: O(1) expected for cache deletion; disk-backed caches may incur I/O.
    """
    cache = _open_cache()
    try:
        cache.delete(CACHE_KEY)
        logger.info("ECB rates cache cleared.")
    except Exception:
        logger.exception("Error clearing ECB rates cache; deletion ignored.")