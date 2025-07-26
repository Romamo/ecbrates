"""Core module containing the CurrencyRates class for exchange rate operations."""

import datetime
import logging
from typing import Optional

from .exceptions import RateNotFound
from .cache import get_rates_from_cache, set_rates_to_cache, clear_cache
from .datasource import _fetch_data, _parse_data

logger = logging.getLogger(__name__)


class CurrencyRates:
    """Main class for retrieving exchange rates from the European Central Bank."""
    
    def __init__(self):
        self._rates = None

    def _ensure_rates(self):
        if self._rates is not None:
            return
        self._rates = get_rates_from_cache()
        if self._rates is None:
            logger.info("Cache empty, fetching ECB data...")
            xml = _fetch_data()
            self._rates = _parse_data(xml)
            set_rates_to_cache(self._rates)

    def get_rate(self, base_cur: str, dest_cur: str = 'EUR', date_obj: Optional[datetime.datetime] = None) -> float:
        """
        Get the exchange rate between two currencies for a specific date.
        
        Args:
            base_cur: Base currency code (case-sensitive)
            dest_cur: Destination currency code (case-sensitive), defaults to 'EUR'
            date_obj: Date for the exchange rate, defaults to most recent available
            
        Returns:
            float: Exchange rate
            
        Raises:
            RateNotFound: If no rate can be found for the requested currencies and date
        """
        self._ensure_rates()
        rates = self._rates
        if not rates:
            raise RateNotFound(f"No rates data available.")
        
        # Determine date to use
        if date_obj is None:
            date_str = max(rates.keys())
        else:
            requested_date_str = date_obj.strftime("%Y-%m-%d")
            # Fallback to nearest prior date
            all_dates = sorted(rates.keys(), reverse=True)
            for d in all_dates:
                if d <= requested_date_str:
                    date_str = d
                    if d != requested_date_str:
                        logger.warning(f"Requested date {requested_date_str} not available, using {date_str}")
                    break
            else:
                raise RateNotFound(f"No rates found for {requested_date_str} or any prior date.")
        
        # Get rates for the date
        day_rates = rates.get(date_str)
        if not day_rates:
            raise RateNotFound(f"No rates found for {date_str}.")
        
        # EUR is implicit (1.0)
        if base_cur == 'EUR':
            rate_base = 1.0
        else:
            rate_base = day_rates.get(base_cur)
            if rate_base is None:
                raise RateNotFound(f"Base currency {base_cur} not found for {date_str}.")
        
        if dest_cur == 'EUR':
            rate_dest = 1.0
        else:
            rate_dest = day_rates.get(dest_cur)
            if rate_dest is None:
                raise RateNotFound(f"Destination currency {dest_cur} not found for {date_str}.")
        
        # Conversion: (1 / rate_base) * rate_dest
        return (1.0 / rate_base) * rate_dest

    def refresh_cache(self) -> None:
        """Manually refresh the cache by fetching fresh data from the ECB."""
        logger.info("Manual cache refresh requested.")
        clear_cache()
        xml = _fetch_data()
        self._rates = _parse_data(xml)
        set_rates_to_cache(self._rates)
        logger.info("Cache refreshed successfully.") 