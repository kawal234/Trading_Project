"""
Order placement logic — sits between the client layer and the CLI.

Each function builds the correct parameter payload, calls the client,
and returns a normalised OrderResult dataclass for consistent downstream handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bot.client import BinanceFuturesClient, BinanceClientError
from bot.logging_config import get_logger

logger = get_logger("orders")


# ── Result model ─────────────────────────────────────────────────────────────

@dataclass
class OrderResult:
    """Normalised representation of a placed order."""

    success: bool
    order_id: int | None = None
    client_order_id: str | None = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    status: str = ""
    orig_qty: float = 0.0
    executed_qty: float = 0.0
    avg_price: float = 0.0
    price: float = 0.0
    stop_price: float = 0.0
    time_in_force: str = ""
    error_message: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: dict) -> "OrderResult":
        """Build an OrderResult from a raw Binance API order response."""
        return cls(
            success=True,
            order_id=data.get("orderId"),
            client_order_id=data.get("clientOrderId", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            order_type=data.get("type", ""),
            status=data.get("status", ""),
            orig_qty=float(data.get("origQty", 0)),
            executed_qty=float(data.get("executedQty", 0)),
            avg_price=float(data.get("avgPrice", 0)),
            price=float(data.get("price", 0)),
            stop_price=float(data.get("stopPrice", 0)),
            time_in_force=data.get("timeInForce", ""),
            raw=data,
        )

    @classmethod
    def from_error(cls, message: str) -> "OrderResult":
        return cls(success=False, error_message=message)


# ── Order placement functions ─────────────────────────────────────────────────

def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
) -> OrderResult:
    """
    Place a MARKET order on Binance Futures Testnet.

    Parameters
    ----------
    client:   Authenticated BinanceFuturesClient
    symbol:   Trading pair, e.g. 'BTCUSDT'
    side:     'BUY' or 'SELL'
    quantity: Contract quantity
    """
    logger.info("Preparing MARKET order: %s %s qty=%s", side, symbol, quantity)

    params: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity,
    }

    try:
        raw = client.place_order(**params)
        result = OrderResult.from_api_response(raw)
        logger.info(
            "MARKET order SUCCESS — orderId=%s status=%s executedQty=%s avgPrice=%s",
            result.order_id,
            result.status,
            result.executed_qty,
            result.avg_price,
        )
        return result
    except BinanceClientError as exc:
        logger.error("MARKET order FAILED — %s", exc)
        return OrderResult.from_error(str(exc))


def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    time_in_force: str = "GTC",
) -> OrderResult:
    """
    Place a LIMIT order on Binance Futures Testnet.

    Parameters
    ----------
    client:        Authenticated BinanceFuturesClient
    symbol:        Trading pair, e.g. 'BTCUSDT'
    side:          'BUY' or 'SELL'
    quantity:      Contract quantity
    price:         Limit price
    time_in_force: 'GTC' (default) | 'IOC' | 'FOK'
    """
    logger.info(
        "Preparing LIMIT order: %s %s qty=%s price=%s tif=%s",
        side, symbol, quantity, price, time_in_force,
    )

    params: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": "LIMIT",
        "quantity": quantity,
        "price": price,
        "timeInForce": time_in_force,
    }

    try:
        raw = client.place_order(**params)
        result = OrderResult.from_api_response(raw)
        logger.info(
            "LIMIT order SUCCESS — orderId=%s status=%s price=%s qty=%s",
            result.order_id,
            result.status,
            result.price,
            result.orig_qty,
        )
        return result
    except BinanceClientError as exc:
        logger.error("LIMIT order FAILED — %s", exc)
        return OrderResult.from_error(str(exc))


def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
) -> OrderResult:
    """
    Place a STOP_MARKET order (bonus order type).

    The order is triggered when the market reaches *stop_price*,
    then executes as a market order.

    Parameters
    ----------
    client:     Authenticated BinanceFuturesClient
    symbol:     Trading pair, e.g. 'BTCUSDT'
    side:       'BUY' or 'SELL'
    quantity:   Contract quantity
    stop_price: Trigger price
    """
    logger.info(
        "Preparing STOP_MARKET order: %s %s qty=%s stopPrice=%s",
        side, symbol, quantity, stop_price,
    )

    params: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "quantity": quantity,
        "stopPrice": stop_price,
    }

    try:
        raw = client.place_order(**params)
        result = OrderResult.from_api_response(raw)
        logger.info(
            "STOP_MARKET order SUCCESS — orderId=%s status=%s stopPrice=%s",
            result.order_id,
            result.status,
            result.stop_price,
        )
        return result
    except BinanceClientError as exc:
        logger.error("STOP_MARKET order FAILED — %s", exc)
        return OrderResult.from_error(str(exc))


# ── Dispatcher ────────────────────────────────────────────────────────────────

def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None = None,
    stop_price: float | None = None,
    time_in_force: str = "GTC",
) -> OrderResult:
    """
    Unified dispatcher — routes to the correct placement function
    based on *order_type*.
    """
    if order_type == "MARKET":
        return place_market_order(client, symbol, side, quantity)
    elif order_type == "LIMIT":
        return place_limit_order(client, symbol, side, quantity, price, time_in_force)  # type: ignore[arg-type]
    elif order_type == "STOP_MARKET":
        return place_stop_market_order(client, symbol, side, quantity, stop_price)  # type: ignore[arg-type]
    else:
        msg = f"Unsupported order type: {order_type}"
        logger.error(msg)
        return OrderResult.from_error(msg)
