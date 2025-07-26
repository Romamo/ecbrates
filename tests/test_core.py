"""Tests for the core module."""

import pytest
import datetime
import logging
from unittest.mock import patch
from ecbrates.core import CurrencyRates
from ecbrates.exceptions import RateNotFound

MOCK_RATES = {
    "2024-06-07": {"USD": 1.09, "JPY": 170.12},
    "2024-06-06": {"USD": 1.08, "JPY": 169.50},
}

def make_currency_rates_with_mock():
    cr = CurrencyRates()
    cr._rates = MOCK_RATES
    return cr

def test_simple_rate_lookup():
    cr = make_currency_rates_with_mock()
    rate = cr.get_rate("USD", "JPY", datetime.datetime(2024, 6, 7))
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6

def test_latest_rate_lookup():
    cr = make_currency_rates_with_mock()
    rate = cr.get_rate("USD", "JPY")
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6

def test_fallback_to_prior_date(caplog):
    cr = make_currency_rates_with_mock()
    # 2024-06-08 is missing, should fallback to 2024-06-07
    rate = cr.get_rate("USD", "JPY", datetime.datetime(2024, 6, 8))
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6
    assert "Requested date 2024-06-08 not available, using 2024-06-07" in caplog.text

def test_conversion_from_eur():
    cr = make_currency_rates_with_mock()
    rate = cr.get_rate("EUR", "USD", datetime.datetime(2024, 6, 7))
    assert abs(rate - 1.09) < 1e-6

def test_conversion_to_eur():
    cr = make_currency_rates_with_mock()
    rate = cr.get_rate("USD", "EUR", datetime.datetime(2024, 6, 7))
    assert abs(rate - (1.0 / 1.09)) < 1e-6

def test_rate_not_found_for_currency():
    cr = make_currency_rates_with_mock()
    with pytest.raises(RateNotFound):
        cr.get_rate("GBP", "USD", datetime.datetime(2024, 6, 7))

def test_rate_not_found_for_date():
    cr = make_currency_rates_with_mock()
    # All dates before 2024-06-06 are missing
    with pytest.raises(RateNotFound):
        cr.get_rate("USD", "JPY", datetime.datetime(2024, 6, 1))

def test_refresh_cache(caplog):
    """Test that refresh_cache method works and logs appropriately."""
    caplog.set_level(logging.INFO)
    cr = make_currency_rates_with_mock()
    with patch('ecbrates.core._fetch_data') as mock_fetch, \
         patch('ecbrates.core._parse_data') as mock_parse, \
         patch('ecbrates.core.set_rates_to_cache') as mock_set_cache, \
         patch('ecbrates.core.clear_cache') as mock_clear_cache:
        
        mock_fetch.return_value = "<xml>test</xml>"
        mock_parse.return_value = {"2024-06-08": {"USD": 1.10}}
        
        cr.refresh_cache()
        
        mock_clear_cache.assert_called_once()
        mock_fetch.assert_called_once()
        mock_parse.assert_called_once_with("<xml>test</xml>")
        mock_set_cache.assert_called_once_with({"2024-06-08": {"USD": 1.10}})
        
        assert "Manual cache refresh requested." in caplog.text
        assert "Cache refreshed successfully." in caplog.text 