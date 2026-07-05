"""
trade_logger.py — Dosya loglama: bot.log (döner) + trades.csv.

- bot.log: genel çalışma logu (RotatingFileHandler).
- trades.csv: her kapanan işlem bir satır (Excel/analiz için).
"""

from __future__ import annotations

import csv
import logging
import os
from logging.handlers import RotatingFileHandler

from config import CONFIG


def setup_logger(name: str = "bot") -> logging.Logger:
    """Konsol + döner dosya handler'lı logger döndürür."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(CONFIG.log_path) or ".", exist_ok=True)
    fh = RotatingFileHandler(CONFIG.log_path, maxBytes=2_000_000, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


class TradeLogger:
    """Kapanan işlemleri trades.csv'ye ekler."""

    FIELDS = ["ts", "symbol", "direction", "entry_price", "exit_price",
              "contracts", "gross_pnl", "fees", "net_pnl", "exit_reason",
              "net_target", "peak_net"]

    def __init__(self, csv_path: str | None = None):
        self.csv_path = csv_path or CONFIG.trades_csv_path
        os.makedirs(os.path.dirname(self.csv_path) or ".", exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()

    def log_trade(self, trade: dict) -> None:
        row = {k: trade.get(k, "") for k in self.FIELDS}
        with open(self.csv_path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.FIELDS).writerow(row)
