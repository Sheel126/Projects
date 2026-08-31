"""SQLite persistence for bot cycles, decisions, and equity history."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Generator
from zoneinfo import ZoneInfo

from finance_vibe.bot import config


SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    context_json TEXT,
    llm_response_json TEXT,
    llm_summary TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    pct REAL,
    stop REAL,
    reason TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    risk_notes TEXT,
    qty REAL,
    notional REAL,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER,
    cycle_id INTEGER NOT NULL,
    alpaca_order_id TEXT,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL,
    status TEXT,
    filled_avg_price REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    day_pnl_pct REAL,
    cycle_id INTEGER,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

CREATE TABLE IF NOT EXISTS daily_reports (
    trade_date TEXT PRIMARY KEY,
    equity_start REAL,
    equity_end REAL,
    pnl REAL,
    pnl_pct REAL,
    num_trades INTEGER,
    num_cycles INTEGER,
    halted INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    phase TEXT,
    message TEXT NOT NULL,
    cycle_id INTEGER,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);
"""


class BotStore:
    def __init__(self, db_path: str | None = None) -> None:
        config.ensure_dirs()
        self.db_path = db_path or str(config.BOT_DB_PATH)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def get_state(self, key: str, default: str | None = None) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM bot_state WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO bot_state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def start_cycle(self, context: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO cycles(created_at, status, context_json) VALUES(?, ?, ?)",
                (now, "running", json.dumps(context)),
            )
            return int(cur.lastrowid)

    def finish_cycle(
        self,
        cycle_id: int,
        status: str,
        llm_response: dict[str, Any] | None = None,
        summary: str = "",
        error: str | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE cycles SET status = ?, llm_response_json = ?, "
                "llm_summary = ?, error = ? WHERE id = ?",
                (
                    status,
                    json.dumps(llm_response) if llm_response else None,
                    summary,
                    error,
                    cycle_id,
                ),
            )

    def save_decision(
        self,
        cycle_id: int,
        ticker: str,
        action: str,
        pct: float,
        stop: float | None,
        reason: str,
        approved: bool,
        risk_notes: str,
        qty: float = 0.0,
        notional: float = 0.0,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO decisions(
                    cycle_id, ticker, action, pct, stop, reason,
                    approved, risk_notes, qty, notional
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cycle_id, ticker, action, pct, stop, reason,
                    int(approved), risk_notes, qty, notional,
                ),
            )
            return int(cur.lastrowid)

    def save_order(
        self,
        cycle_id: int,
        ticker: str,
        side: str,
        qty: float,
        alpaca_order_id: str | None,
        status: str,
        decision_id: int | None = None,
        filled_avg_price: float | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO orders(
                    decision_id, cycle_id, alpaca_order_id, ticker, side,
                    qty, status, filled_avg_price, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision_id, cycle_id, alpaca_order_id, ticker, side,
                    qty, status, filled_avg_price, now,
                ),
            )
            return int(cur.lastrowid)

    def save_equity_snapshot(
        self,
        equity: float,
        cash: float,
        day_pnl_pct: float,
        cycle_id: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO equity_snapshots(
                    created_at, equity, cash, day_pnl_pct, cycle_id
                ) VALUES(?, ?, ?, ?, ?)""",
                (now, equity, cash, day_pnl_pct, cycle_id),
            )

    def save_daily_report(
        self,
        trade_date: date,
        equity_start: float,
        equity_end: float,
        num_trades: int,
        num_cycles: int,
        halted: bool,
        notes: str = "",
    ) -> None:
        pnl = equity_end - equity_start
        pnl_pct = (pnl / equity_start * 100) if equity_start else 0.0
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO daily_reports(
                    trade_date, equity_start, equity_end, pnl, pnl_pct,
                    num_trades, num_cycles, halted, notes, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    equity_end = excluded.equity_end,
                    pnl = excluded.pnl,
                    pnl_pct = excluded.pnl_pct,
                    num_trades = excluded.num_trades,
                    num_cycles = excluded.num_cycles,
                    halted = excluded.halted,
                    notes = excluded.notes,
                    created_at = excluded.created_at
                """,
                (
                    trade_date.isoformat(), equity_start, equity_end, pnl, pnl_pct,
                    num_trades, num_cycles, int(halted), notes, now,
                ),
            )

    def get_day_start_equity(self, trade_date: date) -> float | None:
        key = f"day_start_equity_{trade_date.isoformat()}"
        val = self.get_state(key)
        return float(val) if val else None

    def set_day_start_equity(self, trade_date: date, equity: float) -> None:
        key = f"day_start_equity_{trade_date.isoformat()}"
        self.set_state(key, str(equity))

    def is_halted_today(self, trade_date: date) -> bool:
        return self.get_state(f"halted_{trade_date.isoformat()}") == "1"

    def set_halted_today(self, trade_date: date, halted: bool = True) -> None:
        self.set_state(f"halted_{trade_date.isoformat()}", "1" if halted else "0")

    def recent_cycles(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT d.*, c.created_at AS cycle_time
                   FROM decisions d
                   JOIN cycles c ON c.id = d.cycle_id
                   ORDER BY d.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def equity_curve(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT created_at, equity, cash, day_pnl_pct FROM equity_snapshots "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def daily_reports(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_reports ORDER BY trade_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def log_activity(
        self,
        message: str,
        level: str = "info",
        phase: str | None = None,
        cycle_id: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO activity_log(created_at, level, phase, message, cycle_id)
                   VALUES(?, ?, ?, ?, ?)""",
                (now, level, phase, message, cycle_id),
            )
        self.set_state("last_activity_at", now)
        self.set_state("last_activity_msg", message[:500])

    def recent_activity(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_orders(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT o.*, c.created_at AS cycle_time
                   FROM orders o
                   LEFT JOIN cycles c ON c.id = o.cycle_id
                   ORDER BY o.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_runner_status(self) -> dict[str, Any]:
        return {
            "last_heartbeat": self.get_state("last_heartbeat"),
            "last_cycle_id": self.get_state("last_cycle_id"),
            "last_cycle_status": self.get_state("last_cycle_status"),
            "last_cycle_summary": self.get_state("last_cycle_summary"),
            "last_activity_at": self.get_state("last_activity_at"),
            "last_activity_msg": self.get_state("last_activity_msg"),
            "trading_mode": self.get_state("trading_mode"),
        }

    def set_runner_status(
        self,
        *,
        heartbeat: bool = False,
        cycle_id: int | None = None,
        cycle_status: str | None = None,
        cycle_summary: str | None = None,
        trading_mode: str | None = None,
    ) -> None:
        if heartbeat:
            self.set_state("last_heartbeat", datetime.now(timezone.utc).isoformat())
        if cycle_id is not None:
            self.set_state("last_cycle_id", str(cycle_id))
        if cycle_status is not None:
            self.set_state("last_cycle_status", cycle_status)
        if cycle_summary is not None:
            self.set_state("last_cycle_summary", cycle_summary[:500])
        if trading_mode is not None:
            self.set_state("trading_mode", trading_mode)

    def count_cycles_today(self, trade_date: date) -> int:
        start_et = datetime.combine(trade_date, time.min, tzinfo=ZoneInfo("America/New_York"))
        end_et = start_et + timedelta(days=1)
        start_utc = start_et.astimezone(timezone.utc).isoformat()
        end_utc = end_et.astimezone(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM cycles WHERE created_at >= ? AND created_at < ?",
                (start_utc, end_utc),
            ).fetchone()
        return int(row["c"]) if row else 0

    def count_orders_today(self, trade_date: date) -> int:
        start_et = datetime.combine(trade_date, time.min, tzinfo=ZoneInfo("America/New_York"))
        end_et = start_et + timedelta(days=1)
        start_utc = start_et.astimezone(timezone.utc).isoformat()
        end_utc = end_et.astimezone(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM orders WHERE created_at >= ? AND created_at < ?",
                (start_utc, end_utc),
            ).fetchone()
        return int(row["c"]) if row else 0
