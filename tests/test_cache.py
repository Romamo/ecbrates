"""Tests for the cache module."""

import pytest
import os
import logging
from unittest.mock import patch
from freezegun import freeze_time
from ecbrates.cache import get_rates_from_cache, set_rates_to_cache, clear_cache, _get_cache_directory, _get_next_update_ttl


class TestCache:
    """Test cases for the cache module."""
    
    def test_get_cache_directory_default(self):
        """Test that cache directory defaults to .cache/ecbrates when ECB_CACHE is not set."""
        # Clear environment variable for test
        if "ECB_CACHE" in os.environ:
            del os.environ["ECB_CACHE"]
        
        cache_dir = _get_cache_directory()
        assert cache_dir == ".cache/ecbrates"
    
    def test_get_cache_directory_custom(self):
        """Test that cache directory uses ECB_CACHE environment variable when set."""
        test_cache_dir = "/tmp/test_cache"
        os.environ["ECB_CACHE"] = test_cache_dir
        
        cache_dir = _get_cache_directory()
        assert cache_dir == test_cache_dir
        
        # Clean up
        del os.environ["ECB_CACHE"]
    
    def test_cache_functions_exist(self):
        """Test that cache functions are callable."""
        assert callable(get_rates_from_cache)
        assert callable(set_rates_to_cache)
        assert callable(clear_cache)
    
    @freeze_time("2024-06-07 10:00:00")  # Friday morning
    def test_dynamic_ttl_weekday_morning(self):
        """Test TTL calculation on a weekday morning."""
        ttl = _get_next_update_ttl()
        # Should be approximately 6 hours (21600 seconds) until 16:00
        assert 21000 < ttl < 22200
    
    @freeze_time("2024-06-07 18:00:00")  # Friday evening
    def test_dynamic_ttl_weekday_evening(self):
        """Test TTL calculation on a weekday evening."""
        ttl = _get_next_update_ttl()
        # Should be approximately 3 days until next Monday 16:00
        assert 250000 < ttl < 270000
    
    @freeze_time("2024-06-08 10:00:00")  # Saturday
    def test_dynamic_ttl_weekend(self):
        """Test TTL calculation on a weekend."""
        ttl = _get_next_update_ttl()
        # Should be approximately 2 days until Monday 16:00
        assert 170000 < ttl < 200000
    
    def test_clear_cache(self, caplog):
        """Test that clear_cache function works and logs appropriately."""
        caplog.set_level(logging.INFO)
        with patch('ecbrates.cache._get_cache') as mock_cache:
            mock_cache_instance = mock_cache.return_value
            clear_cache()
            mock_cache_instance.delete.assert_called_once_with("ecb_rates")
            assert "ECB rates cache cleared." in caplog.text 