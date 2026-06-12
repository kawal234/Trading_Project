"""
Input validation for CLI arguments.
All validation errors raise ValueError with a human-readable message.
"""

from __future__ import annotations

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Minimum notional / quantity guard-rails (conservative testnet values)
MIN_QUANTITY = 0.001
MAX_QUANTITY = 1_000.0
MIN_PRICE = 0.01
MAX_PRICE = 10_000_000.0


def validate_symbol(symbol: str) -> str:
    """Normalise and basic-validate a trading symbol string."""
    symbol = symbol.strip().upper()
    if not symbol.isalnum():
        raise ValueError(
            f"Symbol '{symbol}' contains invalid characters. "
            "Expected an alphanumeric string such as BTCUSDT."
        )
    if len(symbol) < 5 or len(symbol) > 12:
        raise ValueError(
            f"Symbol '{symbol}' has an unexpected length ({len(symbol)}). "
            "Typical symbols are 5-12 characters (e.g. BTCUSDT, ETHUSDT)."
        )
    return symbol


def validate_side(side: str) -> str:
    """Validate order side (BUY / SELL)."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Validate order type (MARKET / LIMIT / STOP_MARKET)."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: float) -> float:
    """Validate order quantity is a positive number within sane bounds."""
    if quantity <= 0:
        raise ValueError(f"Quantity must be a positive number. Got: {quantity}.")
    if quantity < MIN_QUANTITY:
        raise ValueError(
            f"Quantity {quantity} is below the minimum allowed ({MIN_QUANTITY})."
        )
    if quantity > MAX_QUANTITY:
        raise ValueError(
            f"Quantity {quantity} exceeds the maximum allowed ({MAX_QUANTITY})."
        )
    return quantity


def validate_price(price: float | None, order_type: str) -> float | None:
    """
    Validate the price field.

    - LIMIT orders: price is required and must be positive.
    - MARKET orders: price must be None (ignored if provided).
    - STOP_MARKET orders: price is treated as the stop trigger price (required).
    """
    if order_type in {"LIMIT", "STOP_MARKET"}:
        if price is None:
            raise ValueError(
                f"A price / stop-price is required for {order_type} orders."
            )
        if price <= 0:
            raise ValueError(f"Price must be a positive number. Got: {price}.")
        if price < MIN_PRICE:
            raise ValueError(
                f"Price {price} is below the minimum allowed ({MIN_PRICE})."
            )
        if price > MAX_PRICE:
            raise ValueError(
                f"Price {price} exceeds the maximum allowed ({MAX_PRICE})."
            )
        return price

    # MARKET order — price should not be supplied
    if price is not None:
        raise ValueError(
            "Price should not be provided for MARKET orders. "
            "Remove the --price flag or switch to a LIMIT order."
        )
    return None


def validate_stop_price(stop_price: float | None, order_type: str) -> float | None:
    """Validate stop_price for STOP_MARKET orders."""
    if order_type == "STOP_MARKET":
        if stop_price is None:
            raise ValueError("--stop-price is required for STOP_MARKET orders.")
        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive. Got: {stop_price}.")
        return stop_price
    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None = None,
    stop_price: float | None = None,
) -> dict:
    """Run all validators and return a clean, normalised parameter dict."""
    return {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, order_type.strip().upper()),
        "stop_price": validate_stop_price(stop_price, order_type.strip().upper()),
    }
