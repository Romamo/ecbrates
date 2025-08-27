"""Data source module for fetching and parsing ECB exchange rate data.

Scalability notes (in-code):
- This module uses an in-memory XML parsing approach: the entire XML payload is
  loaded into memory (requests.response.text and defusedxml.ElementTree.fromstring).
  For the typical ECB exchange-rate feed this is small and efficient, but the
  approach has clear limits:
    * Memory: If the XML document grows to many megabytes or contains many
      thousands of dated <Cube> entries, memory usage grows linearly with the
      document size (O(N) space, where N is number of XML nodes/bytes). This can
      exhaust process memory on constrained systems.
    * Latency: Parsing large XML documents in-process is CPU-bound and can cause
      latency spikes. For very large datasets consider streaming parsers
      (iterparse) or offloading parsing to worker processes.
    * Single-process bottleneck: All parsing and in-memory operations happen on
      the calling thread/process. For high concurrency workloads, prefer
      asynchronous I/O for network fetches and dedicated workers (process pool)
      for CPU-bound parsing tasks.

- Algorithmic complexity:
    * The top-level loop in _parse_data iterates over all date nodes and for
      each date iterates over direct child currency nodes via
      _extract_rates_from_cube_time. Each XML node is visited once, so the
      effective time complexity is O(N) relative to the number of relevant XML
      nodes. Avoid re-running global findall queries inside inner loops which
      could accidentally create O(N^2) behavior.
    * Nested-loop areas to watch (documented inline): the date node iteration
      and the per-date currency iteration form a two-level traversal which is
      linear because each currency node belongs to a single date node. If code
      is modified to, for example, search the whole tree for each currency or
      date, it can degrade dramatically.

Async / I/O migration hooks:
- This module exposes lightweight adapter hooks to make future migration to
  asynchronous I/O or alternative parsing strategies easier without changing
  the module's external API:
    * FETCH_ADAPTER (callable) can be injected to replace the network fetch
      behavior. The default remains the synchronous requests-based fetch. A
      future async migration can set FETCH_ADAPTER to an async-capable callable
      and provide a small synchronous wrapper if backwards-compatibility is
      required by callers.
    * PARSER_ADAPTER (callable) can be injected to replace the XML parser.
      This enables swapping to a streaming parser or an async-friendly parser
      implementation without changing callers that use _parse_data.
- These adapter hooks are intentionally minimal and non-invasive: if they are
  None, the module uses the existing synchronous defaults. They are documented
  and invoked in-place where the I/O / parsing occurs (see call sites below).
"""

import logging
from typing import Any, Callable, Dict, Optional

import requests
from defusedxml import ElementTree as ET

logger = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"

# Adapter hooks for future async / alternative implementations.
# By default these are None and the module falls back to synchronous behavior.
# - FETCH_ADAPTER: Optional[Callable[[], str]] -> should return raw XML string.
# - PARSER_ADAPTER: Optional[Callable[[str], ET.Element]] -> should parse XML and return root Element.
# These are intentionally global so external code (or tests) can swap them in
# when migrating to async I/O or streaming parsers without changing public APIs.
FETCH_ADAPTER: Optional[Callable[[], str]] = None
PARSER_ADAPTER: Optional[Callable[[str], ET.Element]] = None


def _fetch_data(raw_data: Optional[str] = None) -> str:
    """
    Fetch XML data from the ECB website or return provided raw XML data.

    Parameters:
        raw_data: Optional raw XML string to use instead of performing an HTTP request.
                  This is intended as a test hook to isolate I/O during unit tests.

    Returns:
        Raw XML data as a string.

    Raises:
        TypeError: If raw_data is provided but is not a string.
        requests.RequestException: If the network request fails.
        OSError: If the response cannot be decoded as text.

    Notes on async migration:
        - This function calls FETCH_ADAPTER (if provided) to obtain the XML.
          In a future async migration FETCH_ADAPTER may be an async-capable
          callable. To preserve the synchronous API, a small synchronous wrapper
          can be supplied that runs the async fetcher on an event loop or a
          dedicated thread. The current default implementation uses requests.get.
    """
    if raw_data is not None:
        if not isinstance(raw_data, str):
            logger.error("raw_data provided to _fetch_data must be a string.")
            raise TypeError("raw_data must be a string")
        logger.debug("Using raw_data provided to _fetch_data (test hook).")
        return raw_data

    # If an adapter hook is provided, use it. This enables swapping in async or
    # alternative fetch implementations without changing callers.
    if FETCH_ADAPTER is not None:
        logger.debug("Using FETCH_ADAPTER to obtain ECB data (adapter hook).")
        return FETCH_ADAPTER()

    logger.info("Fetching ECB data from %s", ECB_URL)
    try:
        response = requests.get(ECB_URL, timeout=10)
        response.raise_for_status()
        # Ensure we can access response.text; may raise on decode issues
        try:
            text = response.text
        except (UnicodeDecodeError, OSError) as e:
            logger.error("Failed to decode ECB response text: %s", e)
            raise OSError("Failed to decode response text") from e
        logger.info("ECB data fetched successfully.")
        return text
    except requests.RequestException as e:
        logger.error("Failed to fetch ECB data: %s", e)
        raise


def _get_namespace_map() -> Dict[str, str]:
    """
    Return the namespace mapping used when parsing ECB XML.

    Abstracted to a helper to keep parsing logic centralized and testable.
    """
    return {
        'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
        'eurofxref': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'
    }


def _extract_rates_from_cube_time(cube_time: ET.Element, ns: Dict[str, str]) -> Dict[str, float]:
    """
    Extract a mapping of currency -> rate from a Cube element that represents a date.

    Parameters:
        cube_time: XML element corresponding to <Cube time="YYYY-MM-DD">...</Cube>
        ns: Namespace mapping for XML queries.

    Returns:
        Dictionary of currency codes to float rates.

    Notes:
        We iterate the direct child Cube elements and build a dict comprehension to
        avoid explicit nested loops with repeated lookups. This yields linear time
        relative to the number of currency nodes under a given date node.

    Scalability note:
        - This function iterates only the direct children of a date node and thus
          visits each currency node exactly once. This keeps complexity linear.
          Be cautious of changes that might, for example, search the whole tree
          for each currency, which could degrade to O(N^2).
    """
    rates: Dict[str, float] = {}
    # Iterate direct Cube children under the date node. Each child should have
    # 'currency' and 'rate' attributes; we validate and convert safely.
    for cube in cube_time.findall('eurofxref:Cube', ns):
        try:
            currency = cube.attrib['currency']
            rate_str = cube.attrib['rate']
            rate = float(rate_str)
        except KeyError as e:
            # Missing expected attribute on a Cube element; log and skip this entry.
            logger.warning("Skipping Cube with missing attribute %s under date %s", e, cube_time.attrib.get('time'))
            continue
        except ValueError as e:
            # Rate could not be converted to float; log and skip.
            logger.warning("Skipping Cube with invalid rate '%s' for currency %s: %s", cube.attrib.get('rate'), currency, e)
            continue
        rates[currency] = rate
    return rates


def _parse_data(xml_data: str, parser: Callable[[str], ET.Element] = ET.fromstring) -> Dict[str, Any]:
    """
    Parse ECB XML data into a nested dictionary structure:
        {
            'YYYY-MM-DD': {
                'USD': 1.2345,
                'JPY': 123.45,
                ...
            },
            ...
        }

    Parameters:
        xml_data: Raw XML data from the ECB as a string.
        parser: Optional callable that converts XML string to an ElementTree Element.
                This provides lightweight dependency injection for testing. Defaults to
                defusedxml.ElementTree.fromstring.

    Returns:
        Dict mapping dates (YYYY-MM-DD) to dictionaries of currency rates.

    Raises:
        TypeError: If xml_data is not a string.
        ValueError: If xml_data is empty.
        defusedxml.ElementTree.ParseError: If XML parsing fails.

    Notes on parsing adapter:
        - If PARSER_ADAPTER is set and the caller left the default parser unchanged,
          the module will use PARSER_ADAPTER. This allows swapping in streaming
          or async-capable parsers for future scalability improvements without
          changing the public signature of this function.
    """
    logger.info("Parsing ECB XML data...")

    # Input validation
    if not isinstance(xml_data, str):
        logger.error("xml_data must be a string, got %s", type(xml_data))
        raise TypeError("xml_data must be a string")
    if not xml_data.strip():
        logger.error("xml_data is empty or whitespace")
        raise ValueError("xml_data is empty")

    ns = _get_namespace_map()

    # Choose effective parser: respect explicitly provided parser; otherwise use
    # PARSER_ADAPTER when available. This makes it easy to swap parsing
    # implementations without callers needing to change.
    effective_parser = parser
    if parser is ET.fromstring and PARSER_ADAPTER is not None:
        logger.debug("Using PARSER_ADAPTER for XML parsing (adapter hook).")
        effective_parser = PARSER_ADAPTER

    # Parse XML into an Element root using the chosen parser callable.
    try:
        root = effective_parser(xml_data)
    except ET.ParseError as e:
        logger.error("Failed to parse ECB XML data: %s", e)
        raise

    data: Dict[str, Dict[str, float]] = {}

    # Find all <Cube time="..."> elements which represent dated rate sets.
    # Using a single findall for the time nodes and then extracting rates
    # from their direct children avoids repeated global searches and keeps
    # complexity linear with respect to the number of nodes.
    #
    # Scalability note:
    # - This traversal visits each date node and each currency node once. If the
    #   XML payload grows extremely large, consider a streaming parser (iterparse)
    #   to limit peak memory usage, or process dates in batches.
    for cube_time in root.findall('.//eurofxref:Cube[@time]', ns):
        # Validate presence of the 'time' attribute; skip if missing.
        time_attr = cube_time.attrib.get('time')
        if not time_attr:
            logger.debug("Encountered Cube element without 'time' attribute; skipping.")
            continue

        # Extract rates for this date using a focused helper to keep single responsibility.
        rates = _extract_rates_from_cube_time(cube_time, ns)
        if rates:
            data[time_attr] = rates
        else:
            # It's possible a date has no valid currency entries; log at debug level.
            logger.debug("No valid currency rates found for date %s", time_attr)

    logger.info("Parsed %d days of exchange rate data.", len(data))
    return data