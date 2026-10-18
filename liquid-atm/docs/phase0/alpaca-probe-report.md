# Alpaca paper probe report

Generated 2026-09-19T21:35:40+00:00 by `quant/scripts/alpaca_probe.py`.


## 1. Account flags (PDT, margin, buying power)

- **status:** `AccountStatus.ACTIVE`
- **account_blocked:** `False`
- **trading_blocked:** `False`
- **pattern_day_trader:** `None`
- **daytrade_count:** `None`
- **multiplier:** `4`
- **equity:** `97369.5`
- **cash:** `97369.5`
- **buying_power:** `389478`
- **daytrading_buying_power:** `None`
- **regt_buying_power:** `194739`
- **shorting_enabled:** `True`

> `multiplier` > 1 means a margin account. We still cap exposure at 1.0x equity in software.

## 2. Market clock and calendar

- **is_open:** `False`
- **next_open:** `2026-09-21 09:30:00-04:00`
- **next_close:** `2026-09-21 16:00:00-04:00`
- **next trading days:** `2026-09-21, 2026-09-22, 2026-09-23, 2026-09-24, 2026-09-25, 2026-09-28, 2026-09-29`

## 3. Rate-limit headers

- **x-ratelimit-limit:** `200`
- **x-ratelimit-remaining:** `199`
- **x-ratelimit-reset:** `1789853741`

## 4. Market data feeds (free tier)

- **SPY latest IEX trade:** `762.63`
- **daily bars feed=iex:** `7 bars; last 2026-09-18 close=761.62 vol=1293703.0`
- **daily bars feed=sip:** `7 bars; last 2026-09-18 close=761.69 vol=65377133.0`

> SIP volume is the consolidated tape; IEX is a single venue (~2-3% of volume). Volume-breakout signals must use SIP daily bars.

## 5. Limit-entry bracket order (submitted far from market, then cancelled)

- **accepted:** `True`
- **entry / TP / SL:** `381.31 / 419.44 / 362.24`
- **parent:** `type=OrderType.LIMIT class=OrderClass.BRACKET status=OrderStatus.ACCEPTED tif=TimeInForce.DAY`
- **child leg:** `type=OrderType.LIMIT side=OrderSide.SELL status=OrderStatus.HELD limit=419.44 stop=None`
- **child leg:** `type=OrderType.STOP side=OrderSide.SELL status=OrderStatus.HELD limit=None stop=362.24`
- **after cancel:** `status=OrderStatus.CANCELED`

## Notes

- OCO (exit-only) orders need an existing position, so they are probed in Phase 6 on paper fills.
- Brackets do not support extended hours; entries are regular-session only.
