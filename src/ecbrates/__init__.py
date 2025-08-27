"""ECB foreign exchange rates package.

This package provides a small, focused interface for retrieving and working
with European Central Bank (ECB) foreign exchange rates.

Public API (available at the package level):
- CurrencyRates: Primary class to fetch and convert currency rates.

Importing CurrencyRates from this package (for example `from ecb import CurrencyRates`)
preserves any import-time side effects from the underlying modules.
"""

from .core import CurrencyRates

__all__ = ["CurrencyRates"]