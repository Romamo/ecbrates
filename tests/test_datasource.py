"""Tests for the datasource module."""

import pytest
import logging
from unittest.mock import patch, Mock
from ecbrates.datasource import _fetch_data, _parse_data
import requests

SAMPLE_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <gesmes:Sender>
    <gesmes:name>European Central Bank</gesmes:name>
  </gesmes:Sender>
  <Cube>
    <Cube time="2024-06-07">
      <Cube currency="USD" rate="1.09"/>
      <Cube currency="JPY" rate="170.12"/>
    </Cube>
    <Cube time="2024-06-06">
      <Cube currency="USD" rate="1.08"/>
      <Cube currency="JPY" rate="169.50"/>
    </Cube>
  </Cube>
</gesmes:Envelope>
'''

@pytest.fixture
def sample_xml():
    """Fixture providing a valid sample ECB XML payload for parsing tests."""
    return SAMPLE_XML

@pytest.fixture
def malformed_xml():
    """Fixture providing a deliberately malformed XML string to test negative parsing paths."""
    return "<invalid><unclosed>"

@pytest.fixture
def mocked_requests_get(monkeypatch):
    """Fixture to mock requests.get with deterministic behavior and automatic cleanup.

    Returns a factory function that will set requests.get to return a mock response
    with the provided text and status_code.
    """
    def _mock(response_text, status_code=200):
        mock_resp = Mock()
        mock_resp.status_code = status_code
        mock_resp.text = response_text
        def _get(*args, **kwargs):
            return mock_resp
        monkeypatch.setattr(requests, "get", _get)
        return mock_resp
    return _mock

def test_parse_data_valid_xml_parses_rates(sample_xml):
    """Arrange: a valid ECB XML feed; Act: parse it; Assert: expected dates and rates are present."""
    parsed = _parse_data(sample_xml)
    assert "2024-06-07" in parsed  # nosec
    assert parsed["2024-06-07"]["USD"] == 1.09  # nosec
    assert parsed["2024-06-07"]["JPY"] == 170.12  # nosec
    assert "2024-06-06" in parsed  # nosec
    assert parsed["2024-06-06"]["USD"] == 1.08  # nosec
    assert parsed["2024-06-06"]["JPY"] == 169.50  # nosec

def test_fetch_data_success(mocked_requests_get, caplog):
    """Ensure _fetch_data returns XML text and logs expected messages on successful HTTP response."""
    caplog.set_level(logging.INFO)
    mocked_requests_get(SAMPLE_XML, 200)
    data = _fetch_data()
    assert data == SAMPLE_XML  # nosec
    assert "Fetching ECB data from" in caplog.text  # nosec
    assert "ECB data fetched successfully." in caplog.text  # nosec

def test_fetch_data_network_error_raises_and_logs(monkeypatch, caplog):
    """Simulate a network error during fetch and verify that an exception is raised and logged."""
    caplog.set_level(logging.INFO)
    def _raise(*args, **kwargs):
        raise requests.RequestException("Network error")
    monkeypatch.setattr(requests, "get", _raise)
    with pytest.raises(requests.RequestException):
        _fetch_data()
    assert "Failed to fetch ECB data: Network error" in caplog.text  # nosec

def test_parse_data_logging(sample_xml, caplog):
    """Verify that parsing logs both start and summary messages for the provided sample XML."""
    caplog.set_level(logging.INFO)
    parsed = _parse_data(sample_xml)
    assert "Parsing ECB XML data..." in caplog.text  # nosec
    assert "Parsed 2 days of exchange rate data." in caplog.text  # nosec

def test_parse_data_malformed_xml_returns_empty_or_raises(malformed_xml):
    """Negative test: malformed XML input should either raise an error or result in an empty mapping."""
    try:
        parsed = _parse_data(malformed_xml)
    except Exception:
        # Acceptable behavior is to raise an exception for malformed input
        return
    # If no exception is raised, the parser should return an empty dictionary-like mapping
    assert isinstance(parsed, dict)
    assert len(parsed) == 0