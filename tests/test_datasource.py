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

def test_parse_data_with_sample_xml():
    parsed = _parse_data(SAMPLE_XML)
    assert "2024-06-07" in parsed
    assert parsed["2024-06-07"]["USD"] == 1.09
    assert parsed["2024-06-07"]["JPY"] == 170.12
    assert "2024-06-06" in parsed
    assert parsed["2024-06-06"]["USD"] == 1.08
    assert parsed["2024-06-06"]["JPY"] == 169.50

def test_fetch_data_success(caplog):
    caplog.set_level(logging.INFO)
    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_XML
        mock_get.return_value = mock_response
        data = _fetch_data()
        assert data == SAMPLE_XML
        mock_get.assert_called_once()
        assert "Fetching ECB data from" in caplog.text
        assert "ECB data fetched successfully." in caplog.text

def test_fetch_data_network_error(caplog):
    caplog.set_level(logging.INFO)
    with patch("requests.get", side_effect=requests.RequestException("Network error")):
        with pytest.raises(requests.RequestException):
            _fetch_data()
        assert "Failed to fetch ECB data: Network error" in caplog.text

def test_parse_data_logging(caplog):
    caplog.set_level(logging.INFO)
    parsed = _parse_data(SAMPLE_XML)
    assert "Parsing ECB XML data..." in caplog.text
    assert "Parsed 2 days of exchange rate data." in caplog.text 