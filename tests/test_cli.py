"""Tests for the CLI module."""

import pytest
from typer.testing import CliRunner
from ecbrates.cli import app
from unittest.mock import patch
import logging

@pytest.fixture
def cli_runner():
    """Provide a CliRunner instance for invoking the application CLI."""
    return CliRunner()

@pytest.fixture
def mock_get_rate_default():
    """Mock CurrencyRates.get_rate to return a deterministic conversion rate."""
    with patch("ecbrates.core.CurrencyRates.get_rate", return_value=1.2345) as mocked:
        yield mocked

@pytest.fixture
def mock_get_rate_unexpected_error():
    """Mock CurrencyRates.get_rate to raise a generic unexpected error."""
    with patch("ecbrates.core.CurrencyRates.get_rate", side_effect=Exception("Unexpected error")) as mocked:
        yield mocked

@pytest.fixture
def mock_get_rate_invalid_date():
    """Mock CurrencyRates.get_rate to raise a ValueError for invalid date input."""
    with patch("ecbrates.core.CurrencyRates.get_rate", side_effect=ValueError("Invalid date format")) as mocked:
        yield mocked

@pytest.fixture
def mock_get_rate_invalid_currency():
    """Mock CurrencyRates.get_rate to raise an exception for unknown currency."""
    with patch("ecbrates.core.CurrencyRates.get_rate", side_effect=Exception("Error: Base currency not found")) as mocked:
        yield mocked

@pytest.fixture
def mock_refresh_success():
    """Mock CurrencyRates.refresh_cache to simulate a successful refresh."""
    with patch("ecbrates.core.CurrencyRates.refresh_cache") as mocked:
        yield mocked

@pytest.fixture
def mock_refresh_error():
    """Mock CurrencyRates.refresh_cache to simulate a refresh failure."""
    with patch("ecbrates.core.CurrencyRates.refresh_cache", side_effect=Exception("Refresh failed")) as mocked:
        yield mocked

def test_query_command_returns_rate_on_valid_input(cli_runner, mock_get_rate_default):
    """CLI 'query' returns the correct converted amount for valid base currency and date."""
    result = cli_runner.invoke(app, ["query", "USD", "--date", "2024-06-07"])
    assert result.exit_code == 0
    assert "1.0 USD = 1.2345 EUR on 2024-06-07" in result.stdout

def test_query_command_respects_dest_currency_option(cli_runner, mock_get_rate_default):
    """CLI 'query' uses the provided destination currency flag when supplied."""
    result = cli_runner.invoke(app, ["query", "USD", "--dest-cur", "JPY", "--date", "2024-06-07"])
    assert result.exit_code == 0
    assert "1.0 USD = 1.2345 JPY on 2024-06-07" in result.stdout

def test_query_command_handles_unexpected_errors(cli_runner, mock_get_rate_unexpected_error):
    """CLI 'query' surfaces unexpected exceptions as error output and non-zero exit code."""
    result = cli_runner.invoke(app, ["query", "USD", "--date", "2024-06-07"])
    assert result.exit_code == 1
    assert "Unexpected error: Unexpected error" in result.stderr

def test_query_command_validates_date_format(cli_runner, mock_get_rate_invalid_date):
    """CLI 'query' reports a clear error message when an invalid date is provided."""
    result = cli_runner.invoke(app, ["query", "USD", "--date", "not-a-date"])
    assert result.exit_code == 1
    assert "Invalid date format: not-a-date. Use YYYY-MM-DD." in result.stderr

def test_query_command_reports_unknown_currency(cli_runner, mock_get_rate_invalid_currency):
    """CLI 'query' reports when a base currency cannot be found or resolved."""
    result = cli_runner.invoke(app, ["query", "XXX", "--date", "2024-06-07"])
    assert result.exit_code == 1
    assert "Unexpected error: Error: Base currency not found" in result.stderr

def test_refresh_command_reports_success(cli_runner, mock_refresh_success):
    """CLI 'refresh' completes successfully and reports a success message."""
    result = cli_runner.invoke(app, ["refresh"])
    assert result.exit_code == 0
    assert "ECB rates cache refreshed successfully." in result.stdout

def test_refresh_command_reports_failure(cli_runner, mock_refresh_error):
    """CLI 'refresh' reports an error and returns non-zero exit code when refresh fails."""
    result = cli_runner.invoke(app, ["refresh"])
    assert result.exit_code == 1
    assert "Error refreshing cache: Refresh failed" in result.stderr

def test_debug_flag_enables_debug_logging(cli_runner, caplog, mock_get_rate_default):
    """Using --debug enables debug logging and emits the expected debug message."""
    caplog.set_level(logging.DEBUG)
    result = cli_runner.invoke(app, ["--debug", "query", "USD", "--date", "2024-06-07"])
    assert result.exit_code == 0
    assert any("Debug logging enabled." in message for message in caplog.messages)