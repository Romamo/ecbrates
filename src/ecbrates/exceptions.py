"""ecbrates.exceptions

Custom exception classes used by the ecbrates package.

This module defines exceptions raised by currency rate lookup and conversion logic.
Consumers should catch specific exceptions exported here (e.g., RateNotFound) to handle
error cases gracefully. Exceptions in this module inherit from LookupError to allow
broader lookup-related handling when appropriate.

Exported symbols:
- RateNotFound: raised when a requested exchange rate is missing from data sources.
"""

__all__ = ["RateNotFound"]


class RateNotFound(LookupError):
    """Raised when an exchange rate cannot be found for the given currencies.

    This exception is raised by functions that attempt to look up historical or current
    exchange rates when the requested rate is not present in the available data sources
    (e.g., a missing currency pair, absent date in historical records, or incomplete feed).

    Expected consumer behavior:
    - Catch RateNotFound to provide a fallback mechanism such as using an alternative
      data source, prompting the user for different input, or returning a clear error
      message to the caller.
    - Prefer catching RateNotFound (or LookupError) specifically rather than a broad
      Exception to avoid hiding unrelated errors.

    Note:
    Instances of this exception may be raised without additional attributes. Callers
    that need contextual information (like currency codes or timestamps) should rely on
    surrounding API behavior or wrap this exception with additional context where needed.
    """
    pass