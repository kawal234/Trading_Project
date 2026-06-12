"""
cli.py — Command-line entry point for the Binance Futures Testnet trading bot.

Usage examples
--------------
# Market buy
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

# Limit sell
python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 3500

# Stop-market (bonus)
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 58000

# Account info
python cli.py account

# Check connectivity
python cli.py ping
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from bot.client import BinanceFuturesClient, BinanceClientError
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderResult, place_order
from bot.validators import validate_all

# ── App setup ────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet trading bot — place orders via the command line.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_env_file() -> None:
    """Load environment variables from a .env file if it exists."""
    for path in [".env", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key:
                                os.environ[key] = val
                break
            except Exception:
                pass


def _get_client(verbose: bool = False) -> BinanceFuturesClient:
    """
    Build a BinanceFuturesClient from environment variables.
    Exits with a clear error message if credentials are missing.
    """
    _load_env_file()
    setup_logging(verbose=verbose)
    logger = get_logger("cli")

    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        console.print(
            Panel(
                "[bold red]Missing API credentials.[/bold red]\n\n"
                "Set the following environment variables before running:\n\n"
                "  [cyan]export BINANCE_TESTNET_API_KEY=<your-key>[/cyan]\n"
                "  [cyan]export BINANCE_TESTNET_API_SECRET=<your-secret>[/cyan]\n\n"
                "Get credentials at: [link]https://testnet.binancefuture.com[/link]",
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    logger.debug("Credentials loaded from environment.")
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _print_order_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    stop_price: float | None,
) -> None:
    """Print a formatted summary of the order about to be placed."""
    table = Table(title="Order Request Summary", box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="bold cyan", width=18)
    table.add_column("Value", style="white")

    table.add_row("Symbol", symbol)
    table.add_row("Side", f"[green]{side}[/green]" if side == "BUY" else f"[red]{side}[/red]")
    table.add_row("Type", order_type)
    table.add_row("Quantity", str(quantity))

    if order_type == "LIMIT" and price:
        table.add_row("Limit Price", f"{price:,.4f}")
    if order_type == "STOP_MARKET" and stop_price:
        table.add_row("Stop Price", f"{stop_price:,.4f}")

    console.print(table)


def _print_order_result(result: OrderResult) -> None:
    """Print a formatted response table for a completed order."""
    if not result.success:
        console.print(
            Panel(
                f"[bold red]{result.error_message}[/bold red]",
                title="[red]✗ Order Failed[/red]",
                border_style="red",
            )
        )
        return

    color = "green" if result.side == "BUY" else "red"
    title = f"[bold {color}]✓ Order Placed Successfully[/bold {color}]"

    table = Table(title="Order Response", box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Order ID", str(result.order_id))
    table.add_row("Client Order ID", result.client_order_id or "—")
    table.add_row("Symbol", result.symbol)
    table.add_row(
        "Side",
        f"[green]{result.side}[/green]" if result.side == "BUY" else f"[red]{result.side}[/red]",
    )
    table.add_row("Type", result.order_type)
    table.add_row("Status", result.status)
    table.add_row("Orig Qty", str(result.orig_qty))
    table.add_row("Executed Qty", str(result.executed_qty))

    if result.avg_price:
        table.add_row("Avg Fill Price", f"{result.avg_price:,.4f}")
    if result.price:
        table.add_row("Limit Price", f"{result.price:,.4f}")
    if result.stop_price:
        table.add_row("Stop Price", f"{result.stop_price:,.4f}")
    if result.time_in_force:
        table.add_row("Time In Force", result.time_in_force)

    console.print(Panel(table, title=title, border_style=color))


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def place(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="MARKET | LIMIT | STOP_MARKET"),
    qty: float = typer.Option(..., "--qty", "-q", help="Order quantity"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (LIMIT orders)"),
    stop_price: Optional[float] = typer.Option(
        None, "--stop-price", help="Stop trigger price (STOP_MARKET orders)"
    ),
    time_in_force: str = typer.Option("GTC", "--tif", help="Time in force: GTC | IOC | FOK"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG console output"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate inputs and print summary without submitting"
    ),
) -> None:
    """
    Place an order on Binance Futures Testnet.

    \b
    Examples:
      python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
      python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 3500
      python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 58000
    """
    logger = get_logger("cli")
    setup_logging(verbose=verbose)

    # ── 1. Validate inputs ───────────────────────────────────────────────────
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=qty,
            price=price,
            stop_price=stop_price,
        )
    except ValueError as exc:
        console.print(f"\n[bold red]Validation Error:[/bold red] {exc}\n")
        logger.error("Validation failed: %s", exc)
        raise typer.Exit(code=1)

    # ── 2. Print request summary ─────────────────────────────────────────────
    console.print()
    _print_order_request_summary(
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params["price"],
        stop_price=params["stop_price"],
    )

    if dry_run:
        console.print("\n[yellow]Dry-run mode — order not submitted.[/yellow]\n")
        raise typer.Exit(code=0)

    # ── 3. Build client & submit ─────────────────────────────────────────────
    client = _get_client(verbose=verbose)

    console.print("\n[dim]Submitting order to Binance Futures Testnet…[/dim]")

    result = place_order(
        client=client,
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params["price"],
        stop_price=params["stop_price"],
        time_in_force=time_in_force,
    )

    # ── 4. Display result ────────────────────────────────────────────────────
    console.print()
    _print_order_result(result)
    console.print()

    raise typer.Exit(code=0 if result.success else 1)


@app.command()
def ping(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Check connectivity to the Binance Futures Testnet."""
    client = _get_client(verbose=verbose)
    if client.ping():
        console.print("[bold green]✓ Testnet is reachable.[/bold green]")
    else:
        console.print("[bold red]✗ Could not reach testnet.[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def account(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Display account balances and open positions."""
    logger = get_logger("cli")
    setup_logging(verbose=verbose)
    client = _get_client(verbose=verbose)

    try:
        data = client.get_account()
    except BinanceClientError as exc:
        console.print(f"[red]Failed to fetch account info: {exc}[/red]")
        logger.error("account command failed: %s", exc)
        raise typer.Exit(code=1)

    # ── Balances ─────────────────────────────────────────────────────────────
    bal_table = Table(title="Account Balances (non-zero)", box=box.ROUNDED)
    bal_table.add_column("Asset", style="cyan")
    bal_table.add_column("Wallet Balance", justify="right")
    bal_table.add_column("Available Balance", justify="right")
    bal_table.add_column("Unrealised PnL", justify="right")

    for asset in data.get("assets", []):
        wallet = float(asset.get("walletBalance", 0))
        available = float(asset.get("availableBalance", 0))
        pnl = float(asset.get("unrealizedProfit", 0))
        if wallet == 0 and available == 0:
            continue
        pnl_fmt = f"[green]{pnl:+.4f}[/green]" if pnl >= 0 else f"[red]{pnl:+.4f}[/red]"
        bal_table.add_row(asset["asset"], f"{wallet:.4f}", f"{available:.4f}", pnl_fmt)

    console.print(bal_table)

    # ── Open positions ────────────────────────────────────────────────────────
    positions = [p for p in data.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
    if positions:
        pos_table = Table(title="Open Positions", box=box.ROUNDED)
        pos_table.add_column("Symbol", style="cyan")
        pos_table.add_column("Side", justify="center")
        pos_table.add_column("Size", justify="right")
        pos_table.add_column("Entry Price", justify="right")
        pos_table.add_column("Unrealised PnL", justify="right")

        for pos in positions:
            amt = float(pos.get("positionAmt", 0))
            pnl = float(pos.get("unrealizedProfit", 0))
            side_label = "[green]LONG[/green]" if amt > 0 else "[red]SHORT[/red]"
            pnl_fmt = f"[green]{pnl:+.4f}[/green]" if pnl >= 0 else f"[red]{pnl:+.4f}[/red]"
            pos_table.add_row(
                pos["symbol"],
                side_label,
                str(abs(amt)),
                f"{float(pos.get('entryPrice', 0)):,.4f}",
                pnl_fmt,
            )
        console.print(pos_table)
    else:
        console.print("[dim]No open positions.[/dim]")


@app.command()
def price(
    symbol: str = typer.Argument(..., help="Symbol to query, e.g. BTCUSDT"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch the latest mark price for a symbol."""
    logger = get_logger("cli")
    setup_logging(verbose=verbose)
    client = _get_client(verbose=verbose)

    try:
        mark_price = client.get_ticker_price(symbol.upper())
        console.print(f"\n[bold cyan]{symbol.upper()}[/bold cyan]  →  [bold white]{mark_price:,.4f}[/bold white] USDT\n")
        logger.info("Price fetched: %s = %.4f", symbol.upper(), mark_price)
    except BinanceClientError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("price command failed: %s", exc)
        raise typer.Exit(code=1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
