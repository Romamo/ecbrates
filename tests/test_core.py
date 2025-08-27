"""Tests for the core module."""

import pytest
import datetime
import logging
from unittest.mock import patch, Mock
import ecbrates.core as core_mod
from ecbrates.core import CurrencyRates
from ecbrates.exceptions import RateNotFound

MOCK_RATES = {
    "2024-06-07": {"USD": 1.09, "JPY": 170.12},
    "2024-06-06": {"USD": 1.08, "JPY": 169.50},
}

@pytest.fixture
def mock_rates():
    """Provide deterministic mock exchange rates for tests."""
    return MOCK_RATES

@pytest.fixture
def currency_rates(mock_rates):
    """CurrencyRates instance with injected mock rate data for isolation from I/O."""
    cr = CurrencyRates()
    cr._rates = mock_rates
    return cr

@pytest.fixture
def mocked_external_functions(monkeypatch):
    """Monkeypatch external functions used by refresh_cache to avoid network or filesystem I/O.

    Returns tuple(mock_set_cache, mock_clear_cache) so tests can assert they were called.
    """
    mock_fetch = Mock(return_value="<xml>test</xml>")
    mock_parse = Mock(return_value={"2024-06-08": {"USD": 1.10}})
    mock_set_cache = Mock()
    mock_clear_cache = Mock()

    monkeypatch.setattr(core_mod, '_fetch_data', mock_fetch)
    monkeypatch.setattr(core_mod, '_parse_data', mock_parse)
    monkeypatch.setattr(core_mod, 'set_rates_to_cache', mock_set_cache)
    monkeypatch.setattr(core_mod, 'clear_cache', mock_clear_cache)

    return mock_fetch, mock_parse, mock_set_cache, mock_clear_cache

def test_get_rate_simple_lookup(currency_rates):
    """Simple lookup for a known date and currency pair returns expected conversion."""
    rate = currency_rates.get_rate("USD", "JPY", datetime.datetime(2024, 6, 7))
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6  # nosec

def test_get_rate_latest_when_no_date_provided(currency_rates):
    """When no date is provided, the latest available rate is used."""
    rate = currency_rates.get_rate("USD", "JPY")
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6  # nosec

def test_get_rate_fallback_to_prior_date_logs_that_action(currency_rates, caplog):
    """If the requested date is missing, the implementation should fallback to the most recent prior date and log the fallback."""
    caplog.set_level(logging.INFO)
    # 2024-06-08 is missing, should fallback to 2024-06-07
    rate = currency_rates.get_rate("USD", "JPY", datetime.datetime(2024, 6, 8))
    expected = (1.0 / 1.09) * 170.12
    assert abs(rate - expected) < 1e-6  # nosec
    assert "Requested date 2024-06-08 not available, using 2024-06-07" in caplog.text  # nosec

def test_conversion_from_eur_returns_direct_rate(currency_rates):
    """Rates expressed relative to EUR should convert correctly from EUR to a target currency."""
    rate = currency_rates.get_rate("EUR", "USD", datetime.datetime(2024, 6, 7))
    assert abs(rate - 1.09) < 1e-6  # nosec

def test_conversion_to_eur_returns_inverse_rate(currency_rates):
    """Converting a non-EUR currency to EUR uses the inverse of the stored EUR-based rate."""
    rate = currency_rates.get_rate("USD", "EUR", datetime.datetime(2024, 6, 7))
    assert abs(rate - (1.0 / 1.09)) < 1e-6  # nosec

def test_rate_not_found_for_unknown_currency(currency_rates):
    """Requesting a rate for a currency that doesn't exist in the data should raise RateNotFound."""
    with pytest.raises(RateNotFound):
        currency_rates.get_rate("GBP", "USD", datetime.datetime(2024, 6, 7))

def test_rate_not_found_for_old_date_includes_context_in_exception(currency_rates):
    """Requests for dates older than available data should raise RateNotFound with contextual information."""
    # All dates before 2024-06-06 are missing
    with pytest.raises(RateNotFound) as excinfo:
        currency_rates.get_rate("USD", "JPY", datetime.datetime(2024, 6, 1))
    assert "No rates available for requested date" in str(excinfo.value) or "not available" in str(excinfo.value)

def test_refresh_cache_uses_injected_external_functions_and_logs(caplog, mocked_external_functions):
    """Ensure refresh_cache delegates to external functions and logs the refresh operation."""
    caplog.set_level(logging.INFO)
    mock_fetch, mock_parse, mock_set_cache, mock_clear_cache = mocked_external_functions

    cr = CurrencyRates()
    # Ensure starting with some rates so clear_cache has something to clear logically
    cr._rates = MOCK_RATES.copy()

    cr.refresh_cache()

    mock_clear_cache.assert_called_once()
    mock_fetch.assert_called_once()
    mock_parse.assert_called_once_with("<xml>test</xml>")
    mock_set_cache.assert_called_once_with({"2024-06-08": {"USD": 1.10}})

    assert "Manual cache refresh requested." in caplog.text  # nosec
    assert "Cache refreshed successfully." in caplog.text  # nosec

def test_same_currency_returns_one_even_if_rates_present(currency_rates):
    """Converting a currency to itself should always return a rate of 1.0."""
    rate = currency_rates.get_rate("USD", "USD", datetime.datetime(2024, 6, 7))
    assert abs(rate - 1.0) < 1e-9  # nosec

def test_missing_base_currency_raises_with_message(currency_rates):
    """If the base currency is missing from the rates on the chosen date, raise RateNotFound with helpful message."""
    # Remove USD from a specific date to simulate missing base currency
    rates = dict(mock_rates())
    rates["2024-06-07"] = {"JPY": 170.12}  # USD missing
    currency_rates = CurrencyRates()
    currency_rates._rates = rates

    with pytest.raises(RateNotFound) as excinfo:
        currency_rates.get_rate("USD", "JPY", datetime.datetime(2024, 6, 7))

    assert "USD" in str(excinfo.value) and ("2024-06-07" in str(excinfo.value) or "requested date" in str(excinfo.value))