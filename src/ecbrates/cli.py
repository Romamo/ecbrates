"""Command-line interface for the ecbrates package.

This module exposes a Typer-based CLI with commands to query exchange rates
from ECB data and to refresh a local cache.

Summary
-------
Provides a small CLI surface for end users and maintainers:
- main(debug: bool): CLI entrypoint callback that configures logging.
- query(base_cur: str, dest_cur: str, date: Optional[str]): Query a rate and print to stdout.
- refresh(): Manually refresh the ECB rates cache and print a success message.

Behavior and side effects
-------------------------
- Writes human-readable results to stdout on success.
- Writes error messages to stderr and terminates the process using typer.Exit
  (non-zero exit codes) on user or runtime errors.
- Configures the Python root logger when the CLI is started via main().
- Instantiates and calls into ecbrates.core.CurrencyRates, which may perform
  network I/O and/or mutate a local cache on disk. Any file or network side
  effects resulting from rate retrieval and cache refresh are performed by
  CurrencyRates and not by this module itself.

Environment variables
---------------------
- This CLI module does not directly read or write environment variables.
- Underlying components (for example, ecbrates.core.CurrencyRates) may consult
  environment variables for configuration (cache locations, API endpoints,
  authentication, etc.). Maintainters should inspect ecbrates.core for any
  environment variables that influence behavior before modifying this module.

Input expectations and validation
---------------------------------
- Currency codes are treated as case-sensitive strings by the CLI and by
  CurrencyRates. Validate codes upstream if a different behavior is required.
- Date strings (when supplied) must be in strict ISO-like YYYY-MM-DD format.
  Invalid date formats are rejected with a non-zero exit code.

Examples
--------
Common invocation patterns and expected outputs/exit codes.

1) Query the latest available rate for USD (default destination EUR).
   Shell:
       $ ecbrates query USD
   Possible stdout:
       1.0 USD = 0.8432 EUR on 2025-08-27
   Exit code:
       0 on success.

2) Query the rate for a specific date.
   Shell:
       $ ecbrates query USD --date 2020-01-02
   Possible stdout:
       1.0 USD = 0.8900 EUR on 2020-01-02
   Exit code:
       0 on success.

3) Query with an explicit destination currency.
   Shell:
       $ ecbrates query GBP --dest-cur USD
   Possible stdout:
       1.0 GBP = 1.3850 USD on 2025-08-27
   Exit code:
       0 on success.

4) Invalid date format (user error -> message on stderr and exit code 1).
   Shell:
       $ ecbrates query USD --date 01-02-2020
   Possible stderr:
       Invalid date format: 01-02-2020. Use YYYY-MM-DD.
   Exit code:
       1

5) Requested rate not available (RateNotFound -> message on stderr and exit code 1).
   Shell:
       $ ecbrates query ABC --date 1990-01-01
   Possible stderr:
       Error: Rate not found for ABC->EUR on 1990-01-01
   Exit code:
       1

6) Manually refresh the local cache.
   Shell:
       $ ecbrates refresh
   Possible stdout:
       ECB rates cache refreshed successfully.
   Exit code:
       0 on success; non-zero on failure.

Notes for maintainers
---------------------
- Keep CLI behavior stable: any changes to exit codes, stdout/stderr formats,
  or logging configuration can break scripts that depend on this tool.
- If extending this CLI to accept additional configuration via environment
  variables, document them here and avoid changing defaults that callers may
  rely upon.
- For implementation details about caching, network access, or environment
  variables used by the rates implementation, consult ecbrates.core.CurrencyRates.
"""

from datetime import datetime
import logging
from typing import Optional

import typer

from ecbrates.core import CurrencyRates
from ecbrates.exceptions import RateNotFound

app = typer.Typer()


def _configure_logging(debug_enabled: bool) -> None:
    """Configure root logging for the CLI.

    Args:
        debug_enabled: If True, set logging level to DEBUG; otherwise INFO.

    Side effects:
        Configures logging.basicConfig with a consistent format.
    """
    log_level = logging.DEBUG if debug_enabled else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    if debug_enabled:
        logging.getLogger().debug("Debug logging enabled.")


def _create_currency_rates_instance() -> CurrencyRates:
    """Factory helper to construct a CurrencyRates instance.

    Returns:
        A new CurrencyRates instance.

    Raises:
        Exception: Propagates any construction errors to the caller.
    """
    return CurrencyRates()


def _parse_date_string(date_string: Optional[str]) -> Optional[datetime]:
    """Parse an optional YYYY-MM-DD date string into a datetime object.

    Args:
        date_string: Date string provided by the user or None.

    Returns:
        A datetime object representing the parsed date, or None if no date was provided.

    Raises:
        ValueError: If the date_string is provided but not in YYYY-MM-DD format.
    """
    if not date_string:
        return None
    # Accept only strict ISO-like YYYY-MM-DD format
    return datetime.strptime(date_string, "%Y-%m-%d")


def _determine_effective_date_string(
    currency_rates: CurrencyRates, supplied_date: Optional[datetime]
) -> str:
    """Return the effective date string used for the rate output.

    If the user supplied a date, return it in YYYY-MM-DD format. Otherwise,
    attempt to infer the latest available date from the CurrencyRates cache.
    As a fallback, use today's date.

    Args:
        currency_rates: The CurrencyRates instance to inspect for cached dates.
        supplied_date: The parsed date provided by the user or None.

    Returns:
        A date string formatted as YYYY-MM-DD.
    """
    if supplied_date:
        return supplied_date.strftime("%Y-%m-%d")
    try:
        # Accessing protected member _rates is a pragmatic fallback for the CLI.
        available_dates = currency_rates._rates.keys()
        return max(available_dates)
    except Exception:
        # If the cache is not populated or structure differs, fall back to today.
        return datetime.today().strftime("%Y-%m-%d")


def _handle_cli_error(message: str, exit_code: int = 1) -> None:
    """Standardized CLI error handler: print message to stderr and exit.

    Args:
        message: Human-readable error message to display.
        exit_code: Process exit code to use when exiting.

    Side effects:
        Writes to stderr and raises typer.Exit to terminate the process.
    """
    typer.echo(message, err=True)
    raise typer.Exit(code=exit_code)


@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """ECB Rates CLI entrypoint.

    Args:
        debug: If True, enable debug-level logging for troubleshooting.

    Side effects:
        Configures global logging for the CLI process.
    """
    _configure_logging(debug)


@app.command()
def query(
    base_cur: str = typer.Argument(..., help="Base currency code (case-sensitive)"),
    dest_cur: str = typer.Option("EUR", help="Destination currency code (case-sensitive)"),
    date: Optional[str] = typer.Option(None, help="Date in YYYY-MM-DD format")
):
    """Query for an exchange rate.

    Parameters:
        base_cur: The base currency code to convert from.
        dest_cur: The destination currency code to convert to (default "EUR").
        date: Optional date string (YYYY-MM-DD) specifying which rate to query.

    Side effects:
        Writes the resulting rate to stdout. On error, writes an error message to stderr
        and exits with a non-zero status.
    """
    # Map CLI-provided argument names into descriptive local variables
    base_currency_code = base_cur
    destination_currency_code = dest_cur
    date_string = date

    # Argument parsing flow: parse date string if provided
    try:
        parsed_date = _parse_date_string(date_string)
    except ValueError:
        _handle_cli_error(f"Invalid date format: {date_string}. Use YYYY-MM-DD.", exit_code=1)

    # Construct CurrencyRates instance and fetch rate
    try:
        currency_rates = _create_currency_rates_instance()
        rate_value = currency_rates.get_rate(base_currency_code, destination_currency_code, parsed_date)
        effective_date_str = _determine_effective_date_string(currency_rates, parsed_date)
        typer.echo(f"1.0 {base_currency_code} = {rate_value:.4f} {destination_currency_code} on {effective_date_str}")
    except RateNotFound as err:
        _handle_cli_error(f"Error: {err}", exit_code=1)
    except Exception as err:
        logging.getLogger().debug("Unexpected exception in query command", exc_info=err)
        _handle_cli_error(f"Unexpected error: {err}", exit_code=1)


@app.command()
def refresh():
    """Manually refresh the ECB rates cache.

    Side effects:
        Refreshes whatever cache CurrencyRates manages and writes a success message
        to stdout. On error, writes an error message to stderr and exits non-zero.
    """
    try:
        currency_rates = _create_currency_rates_instance()
        currency_rates.refresh_cache()
        typer.echo("ECB rates cache refreshed successfully.")
    except Exception as err:
        logging.getLogger().debug("Unexpected exception in refresh command", exc_info=err)
        _handle_cli_error(f"Error refreshing cache: {err}", exit_code=1)


if __name__ == "__main__":
    app()