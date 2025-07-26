# ecbrates

> **Note:** This is an unofficial package and is not affiliated with or endorsed by the European Central Bank (ECB).

European Central Bank Foreign Exchange Rates - A Python package for retrieving historical and current foreign exchange rates against the Euro (EUR).

## Features

- Fetch exchange rate data directly from the European Central Bank (ECB)
- Intelligent caching with dynamic TTL based on ECB update schedule
- Automatic fallback to previous working day for weekends/holidays
- Simple programmatic API and command-line interface
- Support for all major currencies
- Robust error handling and logging

## Installation

```bash
pip install ecbrates
```

## Library Usage

### Basic Usage

```python
from ecbrates import CurrencyRates
from datetime import datetime

# Initialize the rates object
rates = CurrencyRates()

# Get the latest USD to EUR rate
rate = rates.get_rate("USD", "EUR")
print(f"1 USD = {rate:.4f} EUR")

# Get a specific date's rate
date = datetime(2023, 10, 27)
rate = rates.get_rate("USD", "EUR", date)
print(f"1 USD = {rate:.4f} EUR on 2023-10-27")

# Convert between two non-EUR currencies
rate = rates.get_rate("USD", "JPY")
print(f"1 USD = {rate:.4f} JPY")

# Manual cache refresh
rates.refresh_cache()
```

### Advanced Usage

```python
# Handle missing rates
try:
    rate = rates.get_rate("XXX", "EUR")  # Invalid currency
except RateNotFound:
    print("Currency not found")

# Weekend/holiday fallback (automatic)
# If you request a weekend date, it will use the previous working day
weekend_date = datetime(2023, 10, 28)  # Saturday
rate = rates.get_rate("USD", "EUR", weekend_date)
# Will automatically use Friday's rate
```

## Command-Line Interface

### Query Exchange Rates

```bash
# Basic query (USD to EUR, latest rate)
ecbrates query USD

# Query with specific destination currency
ecbrates query USD --dest-cur JPY

# Query with specific date
ecbrates query USD --date 2023-10-27

# Query with both destination currency and date
ecbrates query USD --dest-cur JPY --date 2023-10-27

# Enable debug logging
ecbrates --debug query USD
```

### Refresh Cache

```bash
# Manually refresh the cache
ecbrates refresh

# Refresh with debug logging
ecbrates --debug refresh
```

### Output Examples

```bash
$ ecbrates query USD
1.0 USD = 0.9523 EUR on 2024-06-07

$ ecbrates query USD --dest-cur JPY
1.0 USD = 170.12 JPY on 2024-06-07

$ ecbrates query USD --date 2023-10-27
1.0 USD = 0.9432 EUR on 2023-10-27

$ ecbrates --debug query USD
DEBUG: Debug logging enabled.
INFO: Cache miss for ECB rates.
INFO: Fetching ECB data from https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml
INFO: ECB data fetched successfully.
INFO: Parsing ECB XML data...
INFO: Parsed 1000 days of exchange rate data.
INFO: ECB rates cached with dynamic TTL of 21600 seconds.
1.0 USD = 0.9523 EUR on 2024-06-07
```

## Configuration

### Cache Location

The cache location can be configured using the `ECB_CACHE` environment variable:

```bash
export ECB_CACHE="/path/to/custom/cache"
```

By default, the cache is stored in `.cache/ecbrates/`.

## Error Handling

The package provides specific error handling:

- `RateNotFound`: Raised when an exchange rate cannot be found for the requested currencies and date
- Network errors are handled gracefully with fallback to cached data
- Invalid date formats are caught and reported clearly

## Requirements

- Python 3.10 or newer
- Internet connection for initial data fetch
- Disk space for caching (typically < 1MB)

## License

This project is open source and available under the MIT License. 