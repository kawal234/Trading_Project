# Binance Futures Testnet Trading Bot

A clean, production-quality Python CLI application for placing orders on the
[Binance Futures Testnet (USDT-M)](https://testnet.binancefuture.com).

---

## Features

| Feature | Details |
|---|---|
| Order types | MARKET, LIMIT, STOP_MARKET (bonus) |
| Sides | BUY and SELL |
| CLI | Built with [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) |
| Logging | Dual output — structured `.log` file + clean console |
| Error handling | API errors, network failures, and invalid input are all caught and surfaced clearly |
| Validation | Symbol, side, type, quantity, and price are all validated before any API call is made |
| Dry-run mode | Validate and preview an order without submitting it |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (signing, HTTP, error handling)
│   ├── orders.py          # Order placement logic + OrderResult model
│   ├── validators.py      # Input validation
│   └── logging_config.py  # File + console logging setup
├── cli.py                 # CLI entry point (Typer)
├── logs/                  # Auto-created; one .log file per calendar day
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet API Credentials

1. Visit <https://testnet.binancefuture.com> and register / log in.
2. Navigate to **API Management** and generate a new key pair.
3. Copy the **API Key** and **Secret Key** — the secret is only shown once.

### 2. Clone / unzip the project

```bash
# If cloned from GitHub:
git clone https://github.com/kawal234/Trading_Project.git
cd Trading_Project
```

### 3. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 4. Set your API credentials (.env file)

Create a file named `.env` in the root directory of the project and paste your keys:

```env
BINANCE_TESTNET_API_KEY="your_api_key_here"
BINANCE_TESTNET_API_SECRET="your_api_secret_here"
```

The bot will automatically load these credentials on startup.

*(Alternatively, you can export them directly in your shell: `export BINANCE_TESTNET_API_KEY="your_api_key_here" && export BINANCE_TESTNET_API_SECRET="your_api_secret_here"`)*

---

## How to Run

All commands are run from the project root directory.

### Check connectivity

```bash
python cli.py ping
```

### Place a MARKET order

```bash
# Buy 0.01 BTC at market price
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

# Sell 0.1 ETH at market price
python cli.py place --symbol ETHUSDT --side SELL --type MARKET --qty 0.1
```

### Place a LIMIT order

```bash
# Sell 0.01 BTC with a limit price of 60,000 USDT
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --qty 0.01 --price 60000

# Buy 0.5 ETH with a limit price of 3,200 USDT, IOC fill
python cli.py place --symbol ETHUSDT --side BUY --type LIMIT --qty 0.5 --price 3200 --tif IOC
```

### Place a STOP_MARKET order (bonus)

```bash
# Trigger a market sell if BTC drops to 55,000
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 55000
```

### Dry-run (validate without submitting)

```bash
python cli.py place --symbol BTCUSDT --side BUY --type LIMIT --qty 0.01 --price 50000 --dry-run
```

### View account balances and open positions

```bash
python cli.py account
```

### Fetch the current mark price

```bash
python cli.py price BTCUSDT
```

### Enable verbose / debug output

Add `--verbose` (or `-v`) to any command:

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01 --verbose
```

### Get help

```bash
python cli.py --help
python cli.py place --help
```

---

## Log Files

Logs are written to `logs/trading_bot_YYYYMMDD.log` (one file per day, auto-created).

Each log entry includes:
- Timestamp
- Log level
- Module name
- Message (API params are logged at DEBUG; errors at ERROR)

The API **signature** is never written to the log file.

---

## Assumptions

1. **Authentication via `.env` file or environment variables.** Native support for `.env` files is now built-in to prevent the need for third-party libraries like `python-dotenv`.

2. **One-way position model.** The bot uses `positionSide=BOTH` (Binance's default hedge-mode-off setting). It does not manage hedge mode or dual-side positions.

3. **Quantity precision.** Quantity is passed as-is; Binance will reject orders where quantity precision exceeds the symbol's step size. Use the `price BTCUSDT` command to check the symbol is active, and consult exchange info for precision rules.

4. **Testnet only.** The base URL is hardcoded to `https://testnet.binancefuture.com`. To switch to mainnet, change `TESTNET_BASE_URL` in `bot/client.py` and use live credentials. **Do not use real funds without thorough testing.**

---

## Evaluation Criteria Checklist

| Criterion | Implementation |
|---|---|
| Places MARKET & LIMIT orders | `bot/orders.py` → `place_market_order`, `place_limit_order` |
| BUY and SELL sides | Validated in `bot/validators.py`, passed through to API |
| CLI with argparse-style flags | `cli.py` using Typer |
| Order request summary printed | `_print_order_request_summary()` in `cli.py` |
| Order response details printed | `_print_order_result()` in `cli.py` |
| Separate client / CLI layers | `bot/client.py` vs `cli.py` |
| Structured logging to file | `bot/logging_config.py` + `logs/*.log` |
| Exception handling | `BinanceAPIError`, `BinanceNetworkError`, `ValueError` all handled |
| Bonus: third order type | STOP_MARKET implemented in `bot/orders.py` |
| Bonus: enhanced CLI UX | Rich tables, colour-coded output, dry-run mode |
