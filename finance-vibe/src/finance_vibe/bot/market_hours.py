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


def is_eod_flat_window(dt: datetime | None = None) -> bool:
    """3:55 PM ET — close intraday positions (research: flat by close)."""
    from finance_vibe.bot import config as bot_config

    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    flat_start = time(bot_config.EOD_FLAT_HOUR, bot_config.EOD_FLAT_MINUTE)
    return flat_start <= t < MARKET_CLOSE


def is_eod_window(dt: datetime | None = None) -> bool:
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        return False
    t = dt.time()
    return MARKET_CLOSE <= t < time(16, 15)


def next_cycle_time(cycle_minutes: int = 15, dt: datetime | None = None) -> datetime:
    """Next aligned cycle boundary during market hours, or next open."""
    dt = dt or now_et()
    if not is_weekday(dt.date()):
        n = dt
        while not is_weekday(n.date()):
            n = n + timedelta(days=1)
        return datetime.combine(n.date(), MARKET_OPEN, tzinfo=ET)

    if dt.time() < MARKET_OPEN:
        return datetime.combine(dt.date(), MARKET_OPEN, tzinfo=ET)
    if dt.time() >= MARKET_CLOSE:
        n = dt + timedelta(days=1)
        while not is_weekday(n.date()):
            n = n + timedelta(days=1)
        return datetime.combine(n.date(), MARKET_OPEN, tzinfo=ET)

    minute = (dt.minute // cycle_minutes + 1) * cycle_minutes
    hour = dt.hour
    if minute >= 60:
        minute = 0
        hour += 1
    nxt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    close_dt = datetime.combine(dt.date(), MARKET_CLOSE, tzinfo=ET)
    if nxt >= close_dt:
        return close_dt - timedelta(minutes=cycle_minutes)
    return nxt


def seconds_until(dt: datetime) -> float:
    return max(0.0, (dt - now_et()).total_seconds())
