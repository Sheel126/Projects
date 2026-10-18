# Tax fixtures (golden test vectors)

Two tax engines exist: Python (backtester, Phase 2) and Java (live ledger, Phase 6).
Both must produce identical results for every fixture here. If they disagree, one of them is wrong.

## Format (one JSON file per scenario)

```json
{
  "name": "wash_sale_basic_rebuy_within_30_days",
  "description": "Loss sale followed by repurchase 10 days later: loss disallowed, added to new lot basis.",
  "config": { "lot_method": "FIFO", "tax_reserve_rate": 0.30 },
  "trades": [
    { "date": "2026-03-02", "symbol": "XYZ", "side": "buy",  "qty": 10, "price": 100.00 },
    { "date": "2026-03-20", "symbol": "XYZ", "side": "sell", "qty": 10, "price": 90.00 },
    { "date": "2026-03-30", "symbol": "XYZ", "side": "buy",  "qty": 10, "price": 92.00 }
  ],
  "expected": {
    "realized_gain": 0.00,
    "disallowed_losses": [ { "sell_date": "2026-03-20", "symbol": "XYZ", "amount": 100.00 } ],
    "open_lots": [
      { "symbol": "XYZ", "qty": 10, "cost_basis": 1020.00, "acquired": "2026-03-30",
        "holding_period_start": "2026-03-12" }
    ],
    "tax_reserve": 0.00,
    "blacklist": [ { "symbol": "XYZ", "until": "2026-04-20" } ]
  }
}
```

## The 13 scenarios (Phase 2)

| File | What it pins down |
|---|---|
| `01-simple-gain` | Baseline round trip: basis, short-term classification, reserve rate |
| `02-wash-basic-rebuy-within-30-days` | The worked example below: full disallowance and holding-period tacking |
| `03-wash-partial-replacement` | Share-for-share matching: 40 replacement shares of 100 disallow exactly 40% |
| `04-wash-rebuy-before-loss-sale` | The "before" side of the window, which the 31-day blacklist cannot prevent |
| `05-tranche-scaling-creates-a-wash` | The bot's own tranching triggers §1091, then the raised basis gives the loss back |
| `06-fifo-multiple-lots` | Partial sell across three lots leaves exactly half of lot 2's basis |
| `07-gain-and-loss-net-in-the-reserve` | Netting is annual, not per trade |
| `08-net-loss-year-carryforward` | $3,000 ordinary-income limit; the rest carries forward and shields the next year |
| `09-holding-period-boundary` | Long term needs *more than* one year: 2027-03-02 short, 2027-03-03 long |
| `10-holding-period-tacking-flips-the-rate` | §1091(d) tacking turns a short-term gain into a long-term one |
| `11-wash-then-clean-exit-recovers-the-loss` | A wash **defers** a loss; the full cycle equals the economics exactly |
| `12-december-flush-undone-by-a-january-rebuy` | A January rebuy disallows the whole harvested loss: $480 of deferral lost |
| `13-fees-and-fractional-shares` | Fee allocation across fractional lots leaks no penny |

Run them with `cd quant && .venv/Scripts/python scripts/tax_fixtures.py`, or as part of `pytest`
(`tests/test_tax_engine.py` parametrises over every file).

Only the keys present in `expected` are compared, so a fixture can pin one behaviour without
restating the whole ledger. Recognised keys: `realized_gain`, `disallowed_losses`, `open_lots`,
`tax_reserve`, `blacklist`, `carryforward`, `deferred_loss_balance`. A `config` block may set
`lot_method`, `short_term_rate` (or `tax_reserve_rate`), `long_term_rate`,
`qualified_dividend_rate`, `wash_window_days`, `blacklist_days`, `payment_schedule` and
`same_lot_remainder_is_replacement`. An optional top-level `as_of` date advances the clock before
the ledger is snapshotted, which is how blacklist expiry and year-end netting get tested.

All amounts in USD, rounded half-up to cents; dates are trade dates (ISO-8601).

Note on `holding_period_start`: under §1091(d) the replacement lot inherits the *holding period*
of the washed shares (held 03-02 → 03-20 = 18 days), so its clock starts 18 days before
its acquisition date (03-30 − 18 days = 03-12). Irrelevant for a short-term bot in practice,
but the ledger must get it right.
