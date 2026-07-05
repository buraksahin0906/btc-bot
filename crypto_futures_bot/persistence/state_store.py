"""
state_store.py — SQLite ile kalıcı durum + işlem geçmişi.

Saklananlar:
  - runtime_state: ardışık zarar, günlük PnL (+ tarih), cooldown bitişi,
    gün başı bakiyesi. Tek satır.
  - open_position: açık pozisyonun TÜM detayları (giriş, stop, trailing durumu,
    tepe net kâr, kilitlenmiş net hedef, algo_id...). En fazla 1 satır.
  - trade_history: kapanan işlemler.
  - reentry: sembol → son giriş zamanı.

Bot açılışta buradan okuyup kaldığı yerden devam eder. Borsa ile çelişkide
borsa gerçeği esas alınır (senkron main.py'de yapılır, temizlik burada).
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import date


class StateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                consecutive_losses INTEGER NOT NULL DEFAULT 0,
                daily_pnl REAL NOT NULL DEFAULT 0,
                daily_pnl_date TEXT,
                cooldown_until REAL,
                day_start_balance REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS open_position (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                contracts REAL,
                gross_pnl REAL,
                fees REAL,
                net_pnl REAL,
                exit_reason TEXT,
                data TEXT
            );

            CREATE TABLE IF NOT EXISTS reentry (
                symbol TEXT PRIMARY KEY,
                last_entry_ts REAL NOT NULL
            );
            """
        )
        # runtime_state tek satırını garanti et
        cur = c.execute("SELECT COUNT(*) AS n FROM runtime_state")
        if cur.fetchone()["n"] == 0:
            c.execute(
                "INSERT INTO runtime_state (id, daily_pnl_date) VALUES (1, ?)",
                (date.today().isoformat(),),
            )
        c.commit()

    # ---------------- Runtime state ----------------

    def get_runtime_state(self) -> dict:
        row = self.conn.execute("SELECT * FROM runtime_state WHERE id = 1").fetchone()
        return {
            "consecutive_losses": row["consecutive_losses"],
            "daily_pnl": row["daily_pnl"],
            "daily_pnl_date": row["daily_pnl_date"],
            "cooldown_until": row["cooldown_until"],
            "day_start_balance": row["day_start_balance"],
        }

    def update_runtime_state(self, **fields) -> None:
        if not fields:
            return
        allowed = {"consecutive_losses", "daily_pnl", "daily_pnl_date",
                   "cooldown_until", "day_start_balance"}
        sets = [f"{k} = ?" for k in fields if k in allowed]
        vals = [fields[k] for k in fields if k in allowed]
        if not sets:
            return
        self.conn.execute(
            f"UPDATE runtime_state SET {', '.join(sets)} WHERE id = 1", vals
        )
        self.conn.commit()

    def reset_daily_if_new_day(self, current_balance: float) -> bool:
        """Yeni güne geçildiyse günlük PnL'i sıfırlar, gün başı bakiyesini set eder.

        Döndürür: yeni gün başladıysa True.
        """
        st = self.get_runtime_state()
        today = date.today().isoformat()
        if st["daily_pnl_date"] != today:
            self.update_runtime_state(
                daily_pnl=0.0,
                daily_pnl_date=today,
                day_start_balance=current_balance,
            )
            return True
        # Gün başı bakiyesi hiç set edilmemişse (ilk çalıştırma) set et
        if st["day_start_balance"] == 0 and current_balance > 0:
            self.update_runtime_state(day_start_balance=current_balance)
        return False

    # ---------------- Açık pozisyon ----------------

    def save_open_position(self, pos: dict) -> None:
        payload = json.dumps(pos)
        self.conn.execute(
            "INSERT INTO open_position (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (payload,),
        )
        self.conn.commit()

    def get_open_position(self) -> dict | None:
        row = self.conn.execute("SELECT data FROM open_position WHERE id = 1").fetchone()
        if not row:
            return None
        return json.loads(row["data"])

    def clear_open_position(self) -> None:
        self.conn.execute("DELETE FROM open_position WHERE id = 1")
        self.conn.commit()

    # ---------------- İşlem geçmişi ----------------

    def record_trade(self, trade: dict) -> None:
        self.conn.execute(
            """INSERT INTO trade_history
               (ts, symbol, direction, entry_price, exit_price, contracts,
                gross_pnl, fees, net_pnl, exit_reason, data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trade.get("ts", time.time()),
                trade.get("symbol"),
                trade.get("direction"),
                trade.get("entry_price"),
                trade.get("exit_price"),
                trade.get("contracts"),
                trade.get("gross_pnl"),
                trade.get("fees"),
                trade.get("net_pnl"),
                trade.get("exit_reason"),
                json.dumps(trade),
            ),
        )
        self.conn.commit()

    def get_trade_stats(self) -> dict:
        """Paper mod özet istatistikleri."""
        rows = self.conn.execute(
            "SELECT net_pnl FROM trade_history"
        ).fetchall()
        pnls = [r["net_pnl"] for r in rows if r["net_pnl"] is not None]
        if not pnls:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                    "total_net": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                    "profit_factor": 0.0}
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        return {
            "trades": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(pnls) * 100,
            "total_net": sum(pnls),
            "avg_win": (gross_win / len(wins)) if wins else 0.0,
            "avg_loss": (gross_loss / len(losses)) if losses else 0.0,
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        }

    # ---------------- Reentry ----------------

    def get_last_entry_time(self, symbol: str) -> float | None:
        row = self.conn.execute(
            "SELECT last_entry_ts FROM reentry WHERE symbol = ?", (symbol,)
        ).fetchone()
        return row["last_entry_ts"] if row else None

    def set_last_entry_time(self, symbol: str, ts: float | None = None) -> None:
        self.conn.execute(
            "INSERT INTO reentry (symbol, last_entry_ts) VALUES (?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET last_entry_ts = excluded.last_entry_ts",
            (symbol, ts if ts is not None else time.time()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
