"""
Logging configuration for the trading bot.
Sets up dual-output logging: structured file logs + clean console output.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure and return the root logger.

    - File handler: DEBUG level, includes timestamps, module, level.
    - Console handler: INFO level (or DEBUG if verbose), clean user-facing format.
    """
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # Already configured (avoid duplicate handlers)

    # ── File handler ────────────────────────────────────────────────────────
    file_fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)

    # ── Console handler ──────────────────────────────────────────────────────
    console_fmt = logging.Formatter(fmt="%(levelname)-8s %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(console_fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.debug("Logging initialised. Log file: %s", LOG_FILE.resolve())
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'trading_bot' namespace."""
    return logging.getLogger(f"trading_bot.{name}")
