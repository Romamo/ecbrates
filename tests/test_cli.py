"""Tests for the CLI module."""

import pytest
from typer.testing import CliRunner
from ecbrates.cli import app
from unittest.mock import patch
import logging

runner = CliRunner()

@patch("ecbrates.core.CurrencyRates.get_rate", return_value=1.2345)
def test_query_command_success(mock_get_rate):
    result = runner.invoke(app, ["query", "USD", "--date", "2024-06-07"])
    assert result.exit_code == 0
    assert "1.0 USD = 1.2345 EUR on 2024-06-07" in result.stdout

@patch("ecbrates.core.CurrencyRates.get_rate", return_value=1.2345)
def test_query_command_dest_cur(mock_get_rate):
    result = runner.invoke(app, ["query", "USD", "--dest-cur", "JPY", "--date", "2024-06-07"])
    assert result.exit_code == 0
    assert "1.0 USD = 1.2345 JPY on 2024-06-07" in result.stdout

@patch("ecbrates.core.CurrencyRates.get_rate", side_effect=Exception("Unexpected error"))
def test_query_command_unexpected_error(mock_get_rate):
    result = runner.invoke(app, ["query", "USD", "--date", "2024-06-07"])
    assert result.exit_code == 1
    assert "Unexpected error: Unexpected error" in result.stderr

@patch("ecbrates.core.CurrencyRates.get_rate", side_effect=ValueError("Invalid date format"))
def test_query_command_invalid_date(mock_get_rate):
    result = runner.invoke(app, ["query", "USD", "--date", "not-a-date"])
    assert result.exit_code == 1
    assert "Invalid date format: not-a-date. Use YYYY-MM-DD." in result.stderr

@patch("ecbrates.core.CurrencyRates.get_rate", side_effect=Exception("Error: Base currency not found"))
def test_query_command_invalid_currency(mock_get_rate):
    result = runner.invoke(app, ["query", "XXX", "--date", "2024-06-07"])
    assert result.exit_code == 1
    assert "Unexpected error: Error: Base currency not found" in result.stderr

@patch("ecbrates.core.CurrencyRates.refresh_cache")
def test_refresh_command_success(mock_refresh):
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 0
    assert "ECB rates cache refreshed successfully." in result.stdout

@patch("ecbrates.core.CurrencyRates.refresh_cache", side_effect=Exception("Refresh failed"))
def test_refresh_command_error(mock_refresh):
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 1
    assert "Error refreshing cache: Refresh failed" in result.stderr

def test_debug_flag_enables_debug_logging(caplog):
    caplog.set_level(logging.DEBUG)
    with patch("ecbrates.core.CurrencyRates.get_rate", return_value=1.2345):
        result = runner.invoke(app, ["--debug", "query", "USD", "--date", "2024-06-07"])
        assert result.exit_code == 0
        # Should see debug log in caplog
        assert any("Debug logging enabled." in m for m in caplog.messages) 