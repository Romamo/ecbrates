"""Data source module for fetching and parsing ECB exchange rate data."""

import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"

def _fetch_data() -> str:
    """
    Fetch XML data from the ECB website.
    Returns:
        str: Raw XML data from the ECB
    Raises:
        requests.RequestException: If the network request fails
    """
    logger.info(f"Fetching ECB data from {ECB_URL}")
    try:
        response = requests.get(ECB_URL, timeout=10)
        response.raise_for_status()
        logger.info("ECB data fetched successfully.")
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch ECB data: {e}")
        raise

def _parse_data(xml_data: str) -> Dict[str, Any]:
    """
    Parse XML data into a nested dictionary structure:
    {
        'YYYY-MM-DD': {
            'USD': 1.2345,
            'JPY': 123.45,
            ...
        },
        ...
    }
    Args:
        xml_data: Raw XML data from the ECB
    Returns:
        Dict containing parsed exchange rate data
    """
    logger.info("Parsing ECB XML data...")
    ns = {'gesmes': 'http://www.gesmes.org/xml/2002-08-01', 'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'}
    root = ET.fromstring(xml_data)
    data = {}
    # Find all Cube elements with a time attribute (dates)
    for cube_time in root.findall('.//eurofxref:Cube[@time]', ns):
        date = cube_time.attrib['time']
        rates = {}
        for cube in cube_time.findall('eurofxref:Cube', ns):
            currency = cube.attrib['currency']
            rate = float(cube.attrib['rate'])
            rates[currency] = rate
        data[date] = rates
    logger.info(f"Parsed {len(data)} days of exchange rate data.")
    return data 