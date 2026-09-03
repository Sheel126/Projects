"""US equity regular-session helpers (Eastern Time)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
PREMARKET_PLAN = time(9, 0)
EOD_REPORT = time(16, 5)


def now_et() -> datetime:
    return datetime.now(ET)


def is_weekday(d: date | None = None) -> bool:
    d = d or now_et().date()
    return d.weekday() < 5


def is_market_open(dt: datetime | None = None) -> bool:
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    return MARKET_OPEN <= t < MARKET_CLOSE


def is_premarket_plan_window(dt: datetime | None = None) -> bool:
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    return PREMARKET_PLAN <= t < MARKET_OPEN


def eod_flat_datetime(trade_date: date | None = None) -> datetime:
    """Configured EOD flatten start (default 3:55 PM ET)."""
    from finance_vibe.bot import config as bot_config

    d = trade_date or now_et().date()
    return datetime.combine(
        d,
        time(bot_config.EOD_FLAT_HOUR, bot_config.EOD_FLAT_MINUTE),
        tzinfo=ET,
    )


def is_eod_flat_window(dt: datetime | None = None) -> bool:
    """3:55 PM ET — close intraday positions (research: flat by close)."""
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    flat_start = eod_flat_datetime(dt.date()).time()
    return flat_start <= t < MARKET_CLOSE


def is_late_entry_window(dt: datetime | None = None) -> bool:
    """After 3:30 PM ET — no new dip-buy entries."""
    from finance_vibe.bot import config as bot_config

    dt = dt or now_et()
    if not is_weekday(dt.date()) or not is_market_open(dt):
        return False
    cutoff = time(bot_config.LATE_ENTRY_HOUR, bot_config.LATE_ENTRY_MINUTE)
    return dt.time() >= cutoff


def is_eod_window(dt: datetime | None = None) -> bool:
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    return MARKET_CLOSE <= t < time(16, 15)


def next_weekday_open(dt: datetime | None = None) -> datetime:
    """Next regular-session open (9:30 ET) on a weekday."""
    dt = dt or now_et()
    n = dt
    if is_weekday(n.date()) and n.time() < MARKET_OPEN:
        return datetime.combine(n.date(), MARKET_OPEN, tzinfo=ET)
    n = n + timedelta(days=1)
    while not is_weekday(n.date()):
        n = n + timedelta(days=1)
    return datetime.combine(n.date(), MARKET_OPEN, tzinfo=ET)


def next_cycle_time(cycle_minutes: int = 15, dt: datetime | None = None) -> datetime:
    """Next cycle boundary aligned from 9:30 ET open (e.g. 20m -> 9:30, 9:50, 10:10)."""
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return next_weekday_open(dt)

    open_dt = datetime.combine(dt.date(), MARKET_OPEN, tzinfo=ET)
    if dt.time() < MARKET_OPEN:
        return open_dt
    if dt.time() >= MARKET_CLOSE:
        return next_weekday_open(dt)

    elapsed_min = (dt - open_dt).total_seconds() / 60.0
    slot = int(elapsed_min // cycle_minutes) + 1
    nxt = open_dt + timedelta(minutes=slot * cycle_minutes)
    close_dt = datetime.combine(dt.date(), MARKET_CLOSE, tzinfo=ET)
    if nxt >= close_dt:
        return next_weekday_open(dt)
    return nxt


def should_preemptive_eod_flatten(
    dt: datetime | None = None, cycle_minutes: int = 20,
) -> bool:
    """True when the next scheduled cycle would miss the EOD flat window."""
    dt = dt or now_et()
    if not is_weekday(dt.date()) or not is_market_open(dt) or is_eod_flat_window(dt):
        return False
    eod = eod_flat_datetime(dt.date())
    if dt >= eod:
        return False
    nxt = next_cycle_time(cycle_minutes, dt)
    return nxt >= eod


def next_daemon_wakeup(cycle_minutes: int = 20, dt: datetime | None = None) -> datetime:
    """When the daemon should wake next — never skip the EOD flat window."""
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return next_weekday_open(dt)

    if is_eod_flat_window(dt):
        close_dt = datetime.combine(dt.date(), MARKET_CLOSE, tzinfo=ET)
        if dt >= close_dt:
            return next_weekday_open(dt)
        return min(dt + timedelta(seconds=30), close_dt)

    if dt.time() >= MARKET_CLOSE:
        return next_weekday_open(dt)

    if dt.time() < MARKET_OPEN:
        return datetime.combine(dt.date(), MARKET_OPEN, tzinfo=ET)

    nxt = next_cycle_time(cycle_minutes, dt)
    eod = eod_flat_datetime(dt.date())
    if dt < eod and nxt > eod:
        return eod
    return nxt


def session_elapsed_fraction(dt: datetime | None = None) -> float:
    """Fraction of the regular session elapsed, floored at 0.05 (~20 min).

    Today's daily bar is partial intraday, so volume must be scaled by this to
    compare against full prior sessions.
    """
    dt = dt or now_et()
    open_dt = datetime.combine(dt.date(), MARKET_OPEN, tzinfo=ET)
    close_dt = datetime.combine(dt.date(), MARKET_CLOSE, tzinfo=ET)
    if dt <= open_dt or dt >= close_dt:
        return 1.0
    total = (close_dt - open_dt).total_seconds()
    return max(0.05, (dt - open_dt).total_seconds() / total)


def seconds_until(dt: datetime) -> float:
    return max(0.0, (dt - now_et()).total_seconds())
