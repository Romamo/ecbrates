"""Core module containing the CurrencyRates class for exchange rate operations.

This module exposes CurrencyRates which retrieves and caches exchange rates
published by the European Central Bank (ECB). The class supports dependency
injection for external interactions (network fetcher, parser, and cache
functions) to improve testability and flexibility while preserving default
behaviour.

Public API:
- CurrencyRates: class to obtain exchange rates and refresh the cache.
"""

import datetime
import logging
from typing import Any, Callable, Dict, Optional

from .cache import clear_cache, get_rates_from_cache, set_rates_to_cache
from .datasource import _fetch_data, _parse_data
from .exceptions import RateNotFound

logger: logging.Logger = logging.getLogger(__name__)


class CurrencyRates:
    """Main class for retrieving exchange rates from the European Central Bank.

    The class lazily loads rates, caches them, and provides exchange rate lookups.

    Parameters:
        fetch_data: Callable that returns raw data (defaults to module _fetch_data).
        parse_data: Callable that parses raw data into the rates dict (defaults to _parse_data).
        cache_get: Callable that returns cached rates or None (defaults to get_rates_from_cache).
        cache_set: Callable that stores rates into cache (defaults to set_rates_to_cache).
        cache_clear: Callable that clears the cache (defaults to clear_cache).
        logger_: Logger instance to use for logging (defaults to module logger).

    The rates data structure expected from parse_data:
        Dict[str, Dict[str, float]]
        Mapping of "YYYY-MM-DD" -> { "CUR": rate, ... }
    """

    def __init__(
        self,
        fetch_data: Callable[[], Any] = _fetch_data,
        parse_data: Callable[[Any], Dict[str, Dict[str, float]]] = _parse_data,
        cache_get: Callable[[], Optional[Dict[str, Dict[str, float]]]] = get_rates_from_cache,
        cache_set: Callable[[Dict[str, Dict[str, float]]], None] = set_rates_to_cache,
        cache_clear: Callable[[], None] = clear_cache,
        logger_: logging.Logger = logger,
    ) -> None:
        """Initialize a CurrencyRates instance with optional dependency injection."""
        self._rates: Optional[Dict[str, Dict[str, float]]] = None
        self._fetch_data = fetch_data
        self._parse_data = parse_data
        self._cache_get = cache_get
        self._cache_set = cache_set
        self._cache_clear = cache_clear
        self._logger = logger_

    def _ensure_rates(self) -> None:
        """Ensure that self._rates is populated, using cache or fetching/parsing as needed.

        This method will attempt to read from the configured cache first. If the cache
        is empty or encounters an error, it will fetch and parse fresh data and populate
        the cache. Exceptions from fetch/parse are logged and re-raised.
        """
        if self._rates is not None:
            return

        try:
            cached = self._cache_get()
        except Exception as err:
            self._logger.exception("Error while reading rates from cache: %s", err)
            cached = None

        if cached:
            self._rates = cached
            return

        self._logger.info("Cache empty or unavailable, fetching ECB data...")
        self._fetch_and_cache()

    def _fetch_and_cache(self) -> None:
        """Fetch raw data, parse it into rates, store in cache, and set internal state.

        Exceptions during fetch/parse will be logged and re-raised to the caller.
        """
        try:
            raw = self._fetch_data()
            parsed = self._parse_data(raw)
            self._cache_set(parsed)
            self._rates = parsed
            self._logger.info("Fetched and cached latest ECB rates successfully.")
        except Exception:
            self._logger.exception("Failed to fetch or parse ECB data.")
            raise

    def _select_date_str(self, rates: Dict[str, Dict[str, float]], date_obj: Optional[datetime.datetime]) -> str:
        """Select the appropriate date string for lookup given the available rates.

        If date_obj is None the most recent available date is used. If the requested
        date is not available, the nearest prior date is selected and a warning is logged.

        Raises RateNotFound if no suitable date is available.
        """
        if not rates:
            raise RateNotFound("No rates data available to select a date from.")
        if date_obj is None:
            return max(rates.keys())
        requested_date_str = date_obj.strftime("%Y-%m-%d")
        all_dates = sorted(rates.keys(), reverse=True)
        for d in all_dates:
            if d <= requested_date_str:
                if d != requested_date_str:
                    self._logger.warning("Requested date %s not available, using %s", requested_date_str, d)
                return d
        raise RateNotFound(f"No rates found for {requested_date_str} or any prior date.")

    def _get_rate_for_currency(self, day_rates: Dict[str, float], currency: str, date_str: str) -> float:
        """Return the rate for a single currency on a specific date.

        EUR is treated as implicit with rate 1.0. Raises RateNotFound if the currency
        is not present in day_rates.
        """
        if currency == 'EUR':
            return 1.0
        rate = day_rates.get(currency)
        if rate is None:
            raise RateNotFound(f"Currency {currency} not found for {date_str}.")
        return rate

    def get_rate(self, base_cur: str, dest_cur: str = 'EUR', date_obj: Optional[datetime.datetime] = None) -> float:
        """
        Get the exchange rate between two currencies for a specific date.

        Args:
            base_cur: Base currency code (case-sensitive)
            dest_cur: Destination currency code (case-sensitive), defaults to 'EUR'
            date_obj: Date for the exchange rate, defaults to most recent available

        Returns:
            float: Exchange rate expressed as units of dest_cur per one unit of base_cur

        Raises:
            RateNotFound: If no rate can be found for the requested currencies and date
            Exception: Propagates lower-level exceptions (network/parsing/cache) after logging
        """
        self._ensure_rates()
        rates = self._rates
        if not rates:
            raise RateNotFound("No rates data available.")

        date_str = self._select_date_str(rates, date_obj)

        day_rates = rates.get(date_str)
        if not day_rates:
            raise RateNotFound(f"No rates found for {date_str}.")

        rate_base = self._get_rate_for_currency(day_rates, base_cur, date_str)
        rate_dest = self._get_rate_for_currency(day_rates, dest_cur, date_str)

        try:
            result = (1.0 / rate_base) * rate_dest
        except Exception as err:
            self._logger.exception("Failed to compute conversion rate for %s -> %s on %s: %s", base_cur, dest_cur, date_str, err)
            raise
        return result

    def refresh_cache(self) -> None:
        """Manually refresh the cache by fetching fresh data from the ECB.

        This clears any existing cache (via configured cache_clear), fetches and parses
        new data, and stores it into cache. Exceptions during this process are logged
        and re-raised.
        """
        self._logger.info("Manual cache refresh requested.")
        try:
            self._cache_clear()
        except Exception:
            self._logger.exception("Failed to clear cache during manual refresh.")
            raise
        self._fetch_and_cache()
        self._logger.info("Cache refreshed successfully.")