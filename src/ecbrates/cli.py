"""Command-line interface for the ecbrates package."""

import logging
import typer
from typing import Optional
from datetime import datetime
from ecbrates.core import CurrencyRates
from ecbrates.exceptions import RateNotFound

app = typer.Typer()

@app.callback()
def main(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """ECB Rates CLI."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    if debug:
        logging.getLogger().debug("Debug logging enabled.")

@app.command()
def query(
    base_cur: str = typer.Argument(..., help="Base currency code (case-sensitive)"),
    dest_cur: str = typer.Option("EUR", help="Destination currency code (case-sensitive)"),
    date: Optional[str] = typer.Option(None, help="Date in YYYY-MM-DD format")
):
    """Query for an exchange rate."""
    try:
        cr = CurrencyRates()
        date_obj = None
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                typer.echo(f"Invalid date format: {date}. Use YYYY-MM-DD.", err=True)
                raise typer.Exit(code=1)
        rate = cr.get_rate(base_cur, dest_cur, date_obj)
        # Determine effective date used
        effective_date = date_obj.strftime("%Y-%m-%d") if date_obj else max(cr._rates.keys())
        typer.echo(f"1.0 {base_cur} = {rate:.4f} {dest_cur} on {effective_date}")
    except RateNotFound as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def refresh():
    """Manually refresh the ECB rates cache."""
    try:
        cr = CurrencyRates()
        cr.refresh_cache()
        typer.echo("ECB rates cache refreshed successfully.")
    except Exception as e:
        typer.echo(f"Error refreshing cache: {e}", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app() 