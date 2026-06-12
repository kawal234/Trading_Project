"""
Binance Futures Testnet – low-level client wrapper.

Handles:
- HMAC-SHA256 request signing
- Timestamp synchronisation
- HTTP request/response lifecycle with structured logging
- Unified exception hierarchy
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import requests

from bot.logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000  # milliseconds


# ── Custom exceptions ────────────────────────────────────────────────────────

class BinanceClientError(Exception):
    """Base exception for all client-layer errors."""


class BinanceAPIError(BinanceClientError):
    """Raised when the Binance API returns a non-2xx status or error payload."""

    def __init__(self, code: int, message: str, http_status: int = 0):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"[{code}] {message} (HTTP {http_status})")


class BinanceNetworkError(BinanceClientError):
    """Raised on connection / timeout failures."""


# ── Client ───────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Parameters
    ----------
    api_key:    Testnet API key
    api_secret: Testnet API secret
    timeout:    Per-request timeout in seconds (default 10)
    """

    def __init__(self, api_key: str, api_secret: str, timeout: int = 10):
        if not api_key or not api_secret:
            raise BinanceClientError("API key and secret must not be empty.")
        self._api_key = api_key
        self._api_secret = api_secret
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.debug("BinanceFuturesClient initialised (testnet).")

    # ── Signing ──────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        """Append a timestamp and HMAC-SHA256 signature to a parameter dict."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        query = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> Any:
        """
        Execute an HTTP request and return the parsed JSON payload.

        Logs the outbound request (sanitised) and the raw response at DEBUG.
        Raises BinanceAPIError or BinanceNetworkError on failure.
        """
        params = params or {}
        if signed:
            params = self._sign(params)

        url = f"{TESTNET_BASE_URL}{endpoint}"

        # Sanitise log output — never log the signature itself
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug("→ %s %s  params=%s", method.upper(), endpoint, safe_params)

        try:
            response = self._session.request(
                method,
                url,
                params=params if method.upper() == "GET" else None,
                data=params if method.upper() != "GET" else None,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, endpoint)
            raise BinanceNetworkError(f"Request timed out ({self._timeout}s).") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s — %s", method, endpoint, exc)
            raise BinanceNetworkError(f"Connection error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected network error: %s", exc)
            raise BinanceNetworkError(f"Network error: {exc}") from exc

        logger.debug(
            "← HTTP %s  body=%s",
            response.status_code,
            response.text[:500],  # truncate large payloads
        )

        # Parse JSON
        try:
            payload = response.json()
        except json.JSONDecodeError:
            raise BinanceAPIError(
                code=-1,
                message=f"Non-JSON response: {response.text[:200]}",
                http_status=response.status_code,
            )

        # Binance signals errors via a top-level 'code' key (negative integer)
        if isinstance(payload, dict) and "code" in payload and payload["code"] < 0:
            raise BinanceAPIError(
                code=payload["code"],
                message=payload.get("msg", "Unknown error"),
                http_status=response.status_code,
            )

        if not response.ok:
            raise BinanceAPIError(
                code=response.status_code,
                message=response.text[:200],
                http_status=response.status_code,
            )

        return payload

    # ── Public endpoints ─────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the testnet is reachable."""
        try:
            self._request("GET", "/fapi/v1/ping")
            logger.info("Testnet reachable ✓")
            return True
        except BinanceClientError as exc:
            logger.error("Ping failed: %s", exc)
            return False

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds."""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self, symbol: str | None = None) -> dict:
        """Return exchange info, optionally filtered to a single symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/exchangeInfo", params=params)

    def get_ticker_price(self, symbol: str) -> float:
        """Return the latest mark price for *symbol*."""
        data = self._request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
        return float(data["price"])

    # ── Authenticated endpoints ───────────────────────────────────────────────

    def get_account(self) -> dict:
        """Return account information (balance, positions, etc.)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def place_order(self, **order_params) -> dict:
        """
        Submit an order to Binance Futures Testnet.

        Expected keyword arguments:
            symbol, side, type, quantity, price (LIMIT only),
            timeInForce (LIMIT only), stopPrice (STOP_MARKET only), etc.
        """
        logger.info(
            "Placing order — symbol=%s side=%s type=%s qty=%s price=%s",
            order_params.get("symbol"),
            order_params.get("side"),
            order_params.get("type"),
            order_params.get("quantity"),
            order_params.get("price", "N/A"),
        )
        response = self._request("POST", "/fapi/v1/order", params=order_params, signed=True)
        logger.info(
            "Order accepted — orderId=%s status=%s",
            response.get("orderId"),
            response.get("status"),
        )
        return response

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order by its orderId."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    def get_open_orders(self, symbol: str | None = None) -> list:
        """Return all open orders, optionally for a specific symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)
