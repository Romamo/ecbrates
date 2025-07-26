"""Caching module for storing and retrieving ECB exchange rate data."""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, time, timedelta
import holidays
from diskcache import Cache

logger = logging.getLogger(__name__)

CACHE_KEY = "ecb_rates"
ECB_UPDATE_TIME = time(16, 0)  # 16:00 CET

def _get_next_update_ttl() -> int:
    """
    Calculate TTL until next ECB update (16:00 CET on weekdays, excluding TARGET2 holidays).
    Returns:
        int: Seconds until next update
    """
    now = datetime.now()
    # Use German holidays as a proxy for TARGET2 holidays (most TARGET2 holidays align with German holidays)
    target_holidays = holidays.country_holidays('DE')
    
    # Find next update time
    next_update = now.replace(hour=ECB_UPDATE_TIME.hour, minute=ECB_UPDATE_TIME.minute, second=0, microsecond=0)
    
    # If today's update time has passed, move to next day
    if now.time() >= ECB_UPDATE_TIME:
        next_update += timedelta(days=1)
    
    # Skip weekends and TARGET2 holidays
    while next_update.weekday() >= 5 or next_update.date() in target_holidays:
        next_update += timedelta(days=1)
    
    ttl_seconds = int((next_update - now).total_seconds())
    logger.debug(f"Calculated TTL: {ttl_seconds} seconds until next ECB update at {next_update}")
    return ttl_seconds

def get_rates_from_cache() -> Optional[Dict[str, Any]]:
    """
    Retrieve exchange rate data from the cache.
    Returns:
        Dict containing cached exchange rate data, or None if not found/expired
    """
    cache = _get_cache()
    data = cache.get(CACHE_KEY, default=None)
    if data is not None:
        logger.info("Cache hit for ECB rates.")
    else:
        logger.info("Cache miss for ECB rates.")
    return data

def set_rates_to_cache(data: Dict[str, Any]) -> None:
    """
    Store exchange rate data in the cache with dynamic TTL.
    Args:
        data: Exchange rate data to cache
    """
    cache = _get_cache()
    ttl = _get_next_update_ttl()
    cache.set(CACHE_KEY, data, expire=ttl)
    logger.info(f"ECB rates cached with dynamic TTL of {ttl} seconds.")

def clear_cache() -> None:
    """Clear the ECB rates cache."""
    cache = _get_cache()
    cache.delete(CACHE_KEY)
    logger.info("ECB rates cache cleared.")

def _get_cache_directory() -> str:
    return os.environ.get("ECB_CACHE", ".cache/ecbrates")

def _get_cache() -> Cache:
    cache_dir = _get_cache_directory()
    os.makedirs(cache_dir, exist_ok=True)
    return Cache(cache_dir) 