"""Custom exceptions for the ecbrates package."""


class RateNotFound(Exception):
    """Raised when an exchange rate cannot be found for the given currencies in the historical data."""
    pass 