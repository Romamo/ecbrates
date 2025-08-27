"""Tests for the cache module."""

import pytest
import os
import logging
from unittest.mock import patch
from freezegun import freeze_time
from ecbrates.cache import get_rates_from_cache, set_rates_to_cache, clear_cache, _get_cache_directory, _get_next_update_ttl


class TestCache:
    """Test cases for the cache module."""
    
    def test_get_cache_directory_default(self, monkeypatch):
        """Ensure cache directory defaults to .cache/ecbrates when ECB_CACHE is not set."""
        monkeypatch.delenv("ECB_CACHE", raising=False)
        cache_dir = _get_cache_directory()
        assert cache_dir == ".cache/ecbrates"
    
    def test_get_cache_directory_custom(self, tmp_path, monkeypatch):
        """Ensure cache directory uses ECB_CACHE environment variable when set."""
        test_cache_dir = str(tmp_path / "test_cache")
        monkeypatch.setenv("ECB_CACHE", test_cache_dir)
        cache_dir = _get_cache_directory()
        assert cache_dir == test_cache_dir
    
    def test_cache_functions_exist(self):
        """Verify that cache functions are present and callable."""
        assert callable(get_rates_from_cache)
        assert callable(set_rates_to_cache)
        assert callable(clear_cache)
    
    @freeze_time("2024-06-07 10:00:00")
    def test_dynamic_ttl_weekday_morning(self):
        """Calculate TTL on a weekday morning and verify it is approximately 6 hours."""
        ttl = _get_next_update_ttl()
        assert ttl > 21000
        assert ttl < 22200
    
    @freeze_time("2024-06-07 18:00:00")
    def test_dynamic_ttl_weekday_evening(self):
        """Calculate TTL on a weekday evening and verify it is approximately 3 days."""
        ttl = _get_next_update_ttl()
        assert ttl > 250000
        assert ttl < 270000
    
    @freeze_time("2024-06-08 10:00:00")
    def test_dynamic_ttl_weekend(self):
        """Calculate TTL on a weekend and verify it is approximately 2 days."""
        ttl = _get_next_update_ttl()
        assert ttl > 170000
        assert ttl < 200000
    
    def test_clear_cache(self, caplog):
        """Test that clear_cache deletes the 'ecb_rates' key and logs the action."""
        caplog.set_level(logging.INFO)
        with patch('ecbrates.cache._get_cache') as mock_cache:
            mock_cache_instance = mock_cache.return_value
            clear_cache()
            mock_cache_instance.delete.assert_called_once_with("ecb_rates")
            assert "ECB rates cache cleared." in caplog.text