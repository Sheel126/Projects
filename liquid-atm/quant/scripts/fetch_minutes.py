"""Download 1-minute SIP bars into data/cache/intraday (Phase 3d, lesson 03d §2).

    python scripts/fetch_minutes.py SPY --years 2016-2024
    python scripts/fetch_minutes.py --orb-opening      # 09:30 5-minute bar, every R1000 member
    python scripts/fetch_minutes.py --orb-days         # 1-minute bars for each day's top 20

Stops at the day before the lockbox (2024-10-01): the lockbox is not even downloaded.
"""

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.data.alpaca_data import AlpacaData  # noqa: E402
from liquid_atm_quant.infra.rate_limiter import alpaca_limiter  # noqa: E402
from liquid_atm_quant.infra.redis_client import make_redis  # noqa: E402
from liquid_atm_quant.intraday import bars  # noqa: E402
from liquid_atm_quant.strategy import LOCKBOX_START  # noqa: E402


def fetch_orb(client, through, opening: bool, days: bool, newest_first: bool = False) -> None:
    from datetime import date

    import psycopg

    from liquid_atm_quant.backtest.panel import Panel
    from liquid_atm_quant.intraday import orb

    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        panel = Panel.from_db(conn, date(2015, 12, 1), through, index_name="russell1000")
    if opening:
        members = {day: [s for j, s in enumerate(panel.symbols) if panel.member[t, j]]
                   for t, day in enumerate(panel.sessions) if day >= date(2016, 1, 1)}
        orb.fetch_opening_bars(client, sorted(members), members, newest_first=newest_first)
    if days:
        from concurrent.futures import ThreadPoolExecutor

        picks = orb.select(orb.load_opening_bars(), panel, orb.OrbParams())
        # ~2 s per request; the shared Redis limiter keeps the threads under 190 a minute.
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda kv: orb.fetch_day_minutes(client, kv[0],
                                                           [c.symbol for c in kv[1]]),
                          sorted(picks.items())))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("symbols", nargs="*")
    parser.add_argument("--orb-opening", action="store_true")
    parser.add_argument("--orb-days", action="store_true")
    parser.add_argument("--newest-first", action="store_true",
                        help="--orb-opening from 2024 backwards (a second worker)")
    parser.add_argument("--years", default="2016-2024")
    parser.add_argument("--force", action="store_true", help="re-download cached years")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    first, last = (int(y) for y in args.years.split("-"))
    settings = get_settings()
    client = AlpacaData(settings.alpaca_api_key, settings.alpaca_secret_key,
                        alpaca_limiter(make_redis(settings)))
    through = LOCKBOX_START - timedelta(days=1)
    if args.orb_opening or args.orb_days:
        fetch_orb(client, through, args.orb_opening, args.orb_days, args.newest_first)
    for symbol in args.symbols:
        for year in range(first, min(last, through.year) + 1):
            if bars._path(symbol, year, bars.CACHE).exists() and not args.force:
                continue
            bars.download_year(client, symbol, year, through=through)
    return 0


if __name__ == "__main__":
    sys.exit(main())
