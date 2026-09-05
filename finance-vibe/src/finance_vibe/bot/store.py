"""SQLite persistence for bot cycles, decisions, and equity history."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Generator
from zoneinfo import ZoneInfo

from finance_vibe.bot import config

ET = ZoneInfo("America/New_York")


def _clean_status(status: Any) -> str:
    """Store 'pending_new', not 'OrderStatus.PENDING_NEW'.

    Alpaca hands back enums, and str() on one keeps the class prefix. Rows
    written that way do not match any status filter, which is what made the
    Day 5 trade count read as 27 instead of 167.

    Anything that is not an enum repr is stored verbatim, because this column
    also carries 'error:<exception>' strings that must not be mangled.
    """
    s = str(status)
    if "OrderStatus." not in s:
        return s
    from finance_vibe.bot.alpaca_client import AlpacaClient

    return AlpacaClient._normalize_status(s)


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

-- Full gate verdict for every ticker on every cycle. explain_buy_eligibility
-- already computes all of this; before, it was thrown away, so there was no
-- way to answer "why did we not buy X on a day we should have made money".
CREATE TABLE IF NOT EXISTS eligibility (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    passed INTEGER NOT NULL,
    reject_reason TEXT,          -- the single headline blocker
    reasons TEXT,                -- every blocker, comma separated
    price REAL,
    open_pct REAL,               -- change_from_open_pct, the entry band input
    vwap_pct REAL,
    quality_score REAL,
    score_floor REAL,
    exit_band_pct REAL,          -- what its target/stop would have been
    rvol REAL,
    rsi REAL,
    atr REAL,
    setup_type TEXT,
    cobra_grade TEXT,
    conviction REAL,
    vibe_score REAL,
    rs_63d REAL,
    in_position INTEGER,
    position_count INTEGER,
    day_pnl_pct REAL,
    qqq_from_open REAL,
    entries_blocked INTEGER,
    -- filled in after the close by scripts/postmortem.py
    close_price REAL,
    max_gain_after_pct REAL,     -- best it got, from here to the close
    max_drop_after_pct REAL,
    to_close_pct REAL,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);
CREATE INDEX IF NOT EXISTS idx_elig_date ON eligibility(trade_date, ticker);
CREATE INDEX IF NOT EXISTS idx_elig_cycle ON eligibility(cycle_id);

-- One row per round trip, so a trade is a single record instead of something
-- you reassemble from two orders.
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    qty REAL,
    entry_at TEXT,
    entry_price REAL,
    entry_order_id TEXT UNIQUE,
    exit_order_id TEXT,
    entry_cycle_id INTEGER,
    entry_reason TEXT,
    entry_score REAL,
    entry_open_pct REAL,
    entry_vwap_pct REAL,
    exit_band_pct REAL,          -- the ATR band this trade was given
    exit_at TEXT,
    exit_price REAL,
    exit_cycle_id INTEGER,
    exit_reason TEXT,            -- target / stop / EOD flat
    pnl REAL,
    pnl_pct REAL,
    hold_minutes REAL,
    status TEXT NOT NULL DEFAULT 'open',
    -- filled in after the close: did we exit too early or too late?
    mfe_pct REAL,                -- max favourable excursion while held
    mae_pct REAL,                -- max adverse excursion while held
    missed_after_exit_pct REAL,  -- how much more it ran after we sold
    close_price REAL
);
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date, ticker);
"""


def _json_safe(obj: Any) -> Any:
    """json.dumps helper — numpy/pandas scalars must not crash a cycle."""
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            return str(obj)
    return str(obj)


class BotStore:
    def __init__(self, db_path: str | None = None) -> None:
        config.ensure_dirs()
        self.db_path = db_path or str(config.BOT_DB_PATH)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=30)
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
                (now, "running", json.dumps(context, default=_json_safe)),
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
                    json.dumps(llm_response, default=_json_safe) if llm_response else None,
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

    def save_eligibility(
        self, cycle_id: int, details: list[dict[str, Any]],
    ) -> int:
        """Persist the full gate verdict for every ticker this cycle.

        Cheap (one row per ticker per cycle, ~14 rows every 20 minutes) and it
        is the only record of *why* a trade did not happen.
        """
        if not details:
            return 0
        now = datetime.now(timezone.utc)
        trade_date = now.astimezone(ET).date().isoformat()
        rows = []
        for d in details:
            reasons = d.get("reasons") or []
            rows.append((
                cycle_id, now.isoformat(), trade_date, d.get("ticker"),
                int(bool(d.get("pass"))), d.get("reject_reason"),
                ",".join(str(r) for r in reasons),
                d.get("price"), d.get("open_pct"), d.get("vwap_pct"),
                d.get("quality_score"), d.get("score_floor"),
                d.get("exit_band_pct"), d.get("rvol"), d.get("rsi"),
                d.get("atr"), d.get("setup"), d.get("cobra"),
                d.get("conviction"), d.get("vibe_score"), d.get("rs_63d"),
                int(bool(d.get("in_position"))), d.get("position_count"),
                d.get("day_pnl_pct"), d.get("qqq_from_open"),
                int(bool(d.get("entries_blocked"))),
            ))
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO eligibility(
                    cycle_id, created_at, trade_date, ticker, passed,
                    reject_reason, reasons, price, open_pct, vwap_pct,
                    quality_score, score_floor, exit_band_pct, rvol, rsi, atr,
                    setup_type, cobra_grade, conviction, vibe_score, rs_63d,
                    in_position, position_count, day_pnl_pct, qqq_from_open,
                    entries_blocked
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
        return len(rows)

    def reconcile_trades(self, fills: list[dict[str, Any]]) -> dict[str, int]:
        """Rebuild round trips from authoritative Alpaca fills.

        Walks fills oldest-first per ticker, pairing buys with the sells that
        close them. Keyed on the entry order id so it is idempotent and safe
        to re-run every cycle; enrichment columns added later by the
        post-mortem are preserved.

        Partial exits are handled by closing the trade on the first sell and
        recording the remainder as a new open lot, which matches how the bot
        actually behaves (it sells whole positions).
        """
        if not fills:
            return {"opened": 0, "closed": 0}
        by_ticker: dict[str, list[dict[str, Any]]] = {}
        for f in fills:
            by_ticker.setdefault(f["symbol"], []).append(f)

        opened = closed = 0
        with self._conn() as conn:
            for ticker, rows in by_ticker.items():
                rows.sort(key=lambda r: r["filled_at"])
                lot: dict[str, Any] | None = None
                for f in rows:
                    if f["side"] == "BUY":
                        lot = f
                        cur = conn.execute(
                            """INSERT INTO trades(
                                ticker, trade_date, qty, entry_at, entry_price,
                                entry_order_id, status
                            ) VALUES(?,?,?,?,?,?,'open')
                            ON CONFLICT(entry_order_id) DO NOTHING""",
                            (
                                ticker,
                                f["filled_at"].astimezone(ET).date().isoformat(),
                                f["qty"], f["filled_at"].isoformat(),
                                f["price"], f["id"],
                            ),
                        )
                        opened += cur.rowcount if cur.rowcount > 0 else 0
                    elif lot is not None:
                        entry = float(lot["price"])
                        qty = min(float(lot["qty"]), float(f["qty"]))
                        pnl_pct = (f["price"] / entry - 1) * 100 if entry else 0.0
                        held = (
                            f["filled_at"] - lot["filled_at"]
                        ).total_seconds() / 60
                        cur = conn.execute(
                            """UPDATE trades SET exit_at = ?, exit_price = ?,
                               exit_order_id = ?, pnl = ?, pnl_pct = ?,
                               hold_minutes = ?, status = 'closed'
                               WHERE entry_order_id = ? AND status != 'closed'""",
                            (
                                f["filled_at"].isoformat(), f["price"], f["id"],
                                (f["price"] - entry) * qty, pnl_pct, held,
                                lot["id"],
                            ),
                        )
                        closed += max(cur.rowcount, 0)
                        lot = None
        return {"opened": opened, "closed": closed}

    def annotate_trade_entries(self) -> int:
        """Attach the entry rationale to each trade from the eligibility log.

        Kept separate from reconciliation because the fills come from Alpaca
        while the reasoning comes from our own cycle log; they are matched on
        ticker and the closest preceding eligibility row.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, ticker, entry_at FROM trades "
                "WHERE entry_reason IS NULL AND entry_at IS NOT NULL"
            ).fetchall()
            n = 0
            for r in rows:
                e = conn.execute(
                    """SELECT quality_score, open_pct, vwap_pct, exit_band_pct,
                              reasons, setup_type, cobra_grade
                       FROM eligibility
                       WHERE ticker = ? AND created_at <= ?
                       ORDER BY created_at DESC LIMIT 1""",
                    (r["ticker"], r["entry_at"]),
                ).fetchone()
                if e is None:
                    continue
                conn.execute(
                    """UPDATE trades SET entry_reason = ?, entry_score = ?,
                       entry_open_pct = ?, entry_vwap_pct = ?, exit_band_pct = ?
                       WHERE id = ?""",
                    (
                        f"setup={e['setup_type']} cobra={e['cobra_grade']} "
                        f"{e['reasons']}",
                        e["quality_score"], e["open_pct"], e["vwap_pct"],
                        e["exit_band_pct"], r["id"],
                    ),
                )
                n += 1
        return n

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
                    qty, _clean_status(status), filled_avg_price, now,
                ),
            )
            return int(cur.lastrowid)

    def update_order_status(
        self,
        order_id: int,
        status: str,
        filled_avg_price: float | None = None,
        alpaca_order_id: str | None = None,
    ) -> None:
        status = _clean_status(status)
        with self._conn() as conn:
            if alpaca_order_id is not None:
                conn.execute(
                    "UPDATE orders SET status = ?, filled_avg_price = ?, "
                    "alpaca_order_id = ? WHERE id = ?",
                    (status, filled_avg_price, alpaca_order_id, order_id),
                )
            else:
                conn.execute(
                    "UPDATE orders SET status = ?, filled_avg_price = ? WHERE id = ?",
                    (status, filled_avg_price, order_id),
                )

    def get_pending_sell_symbols(self) -> list[str]:
        import json
        raw = self.get_state("pending_sell_symbols", "[]")
        try:
            return list(json.loads(raw or "[]"))
        except json.JSONDecodeError:
            return []

    def add_pending_sell(self, symbol: str) -> None:
        import json
        syms = self.get_pending_sell_symbols()
        sym = symbol.upper()
        if sym not in syms:
            syms.append(sym)
            self.set_state("pending_sell_symbols", json.dumps(syms))

    def clear_pending_sell(self, symbol: str) -> None:
        import json
        syms = [s for s in self.get_pending_sell_symbols() if s != symbol.upper()]
        self.set_state("pending_sell_symbols", json.dumps(syms))

    def clear_all_pending_sells(self) -> None:
        self.set_state("pending_sell_symbols", "[]")

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
