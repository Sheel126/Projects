"""Flask dashboard for paper trading bot."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_lp = Path(__file__).resolve().parent / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

import json

from flask import Flask, jsonify, render_template_string

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.health import run_health_check
from finance_vibe.bot.market_hours import is_market_open, now_et
from finance_vibe.bot.store import BotStore

app = Flask(__name__)
store = BotStore()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Finance-Vibe Paper Bot</title>
  <style>
    :root {
      --bg: #0f1419; --card: #1a2332; --text: #e7ecf3; --muted: #8b9cb3;
      --green: #3dd68c; --red: #f07178; --accent: #6cb6ff; --border: #2d3a4f;
      --amber: #ffb86c;
    }
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
           color: var(--text); margin: 0; padding: 1.5rem; }
    h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
    .sub { color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
    .health-banner {
      border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1.5rem;
      border: 1px solid var(--border);
    }
    .health-banner.ready { background: #1a2e24; border-color: #2d5a40; }
    .health-banner.warn { background: #2e2a1a; border-color: #5a4f2d; }
    .health-banner.error { background: #2e1a1a; border-color: #5a2d2d; }
    .health-banner h2 { margin: 0 0 0.35rem; font-size: 1.05rem; }
    .health-banner.ready h2 { color: var(--green); }
    .health-banner.warn h2 { color: var(--amber); }
    .health-banner.error h2 { color: var(--red); }
    .health-banner p { margin: 0.2rem 0; color: var(--muted); font-size: 0.85rem; }
    .svc-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
    .svc-pill {
      font-size: 0.72rem; padding: 0.25rem 0.55rem; border-radius: 999px;
      border: 1px solid var(--border); background: var(--card);
    }
    .svc-pill.ok { border-color: #2d5a40; color: var(--green); }
    .svc-pill.fail { border-color: #5a2d2d; color: var(--red); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; }
    .card label { display: block; color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .val { font-size: 1.5rem; font-weight: 600; margin-top: 0.25rem; }
    .pos { color: var(--green); } .neg { color: var(--red); }
    .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge.open { background: #1a3d2e; color: var(--green); }
    .badge.closed { background: #3d1a1a; color: var(--red); }
    .badge.halt { background: #3d2a1a; color: var(--amber); }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 500; }
    .section { margin-bottom: 1.5rem; }
    .section h2 { font-size: 1rem; margin: 0 0 0.75rem; color: var(--accent); }
    #chart { height: 120px; display: flex; align-items: flex-end; gap: 2px; }
    #chart .bar { flex: 1; background: var(--accent); border-radius: 2px 2px 0 0; min-height: 2px; opacity: 0.8; }
    .refresh { color: var(--muted); font-size: 0.75rem; }
    .hint { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; }
    .status-bar {
      background: var(--card); border: 1px solid var(--border); border-radius: 10px;
      padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem;
    }
    .status-bar .phase { color: var(--accent); font-weight: 600; }
    .activity-feed {
      max-height: 320px; overflow-y: auto; font-family: ui-monospace, monospace;
      font-size: 0.78rem; line-height: 1.5;
    }
    .activity-line { padding: 0.35rem 0; border-bottom: 1px solid var(--border); }
    .activity-line .ts { color: var(--muted); margin-right: 0.5rem; }
    .activity-line .ph { color: var(--accent); margin-right: 0.5rem; font-weight: 600; }
    .activity-line.warn .ph { color: var(--amber); }
    .activity-line.error .ph { color: var(--red); }
    .sig-up { color: var(--green); } .sig-down { color: var(--red); }
  </style>
</head>
<body>
  <h1>Finance-Vibe Paper Bot</h1>
  <p class="sub">
    <span class="badge {{ 'open' if market_open else 'closed' }}">{{ 'MARKET OPEN' if market_open else 'MARKET CLOSED' }}</span>
    {% if halted %}<span class="badge halt">HALTED</span>{% endif %}
    &nbsp; {{ now_et }} ET &nbsp;|&nbsp; Mode: <strong>{{ trading_mode }}</strong>
    &nbsp;|&nbsp; Watchlist: {{ watchlist|length }} tickers
    <span class="refresh"> — auto-refresh 15s</span>
  </p>

  <div class="status-bar">
    <span class="phase">Bot status:</span>
    {% if runner_status.last_activity_msg %}
      {{ runner_status.last_activity_msg }}
    {% else %}
      Waiting for first cycle — start the runner before market open.
    {% endif %}
    {% if runner_status.last_cycle_id %}
      &nbsp;|&nbsp; Last cycle #{{ runner_status.last_cycle_id }}
      ({{ runner_status.last_cycle_status or '?' }})
    {% endif %}
    {% if runner_status.last_heartbeat %}
      &nbsp;|&nbsp; Heartbeat {{ runner_status.last_heartbeat[:19] }}
    {% endif %}
  </div>

  <div class="health-banner {{ health_class }}">
    <h2>{{ health.headline }}</h2>
    <p>{{ health.subline }}</p>
    <p>{{ health.next_event }}</p>
    <div class="svc-grid">
      {% for s in health.services %}
      <span class="svc-pill {{ 'ok' if s.online else 'fail' }}" title="{{ s.detail }}">
        {{ s.name }}: {{ 'online' if s.online else 'offline' }}
      </span>
      {% endfor %}
    </div>
    {% if not health.all_ready %}
    <p class="hint">Run setup check: <code>python src/finance_vibe/bot/check_setup.py</code></p>
    {% elif market_phase in ['weekend', 'before_open', 'closed', 'after_close'] %}
    <p class="hint">Start the runner before 9:30 ET: <code>python src/finance_vibe/bot/runner.py daemon</code></p>
    {% endif %}
  </div>

  <div class="grid">
    <div class="card"><label>Equity</label><div class="val">${{ "%.2f"|format(equity) }}</div></div>
    <div class="card"><label>Cash</label><div class="val">${{ "%.2f"|format(cash) }}</div></div>
    <div class="card"><label>Day P&L</label>
      <div class="val {{ 'pos' if day_pnl >= 0 else 'neg' }}">${{ "%.2f"|format(day_pnl) }} ({{ "%.2f"|format(day_pnl_pct) }}%)</div></div>
    <div class="card"><label>Positions</label><div class="val">{{ positions|length }}</div></div>
    <div class="card"><label>Cycles Today</label><div class="val">{{ cycles_today }}</div></div>
    <div class="card"><label>Orders Today</label><div class="val">{{ orders_today }}</div></div>
  </div>

  <div class="section card">
    <h2>Live Activity Log</h2>
    <div class="activity-feed" id="activity-feed">
      {% for a in activity %}
      <div class="activity-line {{ a.level }}">
        <span class="ts">{{ a.created_at[11:19] }}</span>
        <span class="ph">[{{ a.phase or 'bot' }}]</span>
        {{ a.message }}
      </div>
      {% endfor %}
    </div>
    {% if not activity %}<p style="color:var(--muted)">No activity yet — log appears when runner starts.</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Watchlist Signals (last cycle)</h2>
    {% if signal_rows %}
    <table>
      <tr><th>Ticker</th><th>Active</th><th>Chg Open</th><th>RSI</th><th>VWAP%</th><th>IBS</th><th>ORB</th><th>In Pos</th></tr>
      {% for s in signal_rows %}
      <tr>
        <td>{{ s.ticker }}</td>
        <td><strong>{{ s.active_score }}</strong></td>
        <td class="{{ 'sig-down' if s.change_from_open_pct < 0 else 'sig-up' }}">{{ s.change_from_open_pct }}%</td>
        <td>{{ s.rsi }}</td>
        <td>{{ s.price_vs_vwap_pct or '-' }}</td>
        <td>{{ s.ibs or '-' }}</td>
        <td>{{ s.orb_signal or '-' }}</td>
        <td>{{ 'yes' if s.in_position else '-' }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}<p style="color:var(--muted)">Signals populate after first trading cycle.</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Recent Orders</h2>
    {% if orders %}
    <table>
      <tr><th>Time</th><th>Side</th><th>Symbol</th><th>Qty</th><th>Status</th></tr>
      {% for o in orders %}
      <tr>
        <td>{{ (o.created_at or '')[:19] }}</td>
        <td>{{ o.side }}</td>
        <td>{{ o.ticker }}</td>
        <td>{{ o.qty }}</td>
        <td>{{ o.status }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}<p style="color:var(--muted)">No orders yet.</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Equity Curve</h2>
    <div id="chart">
      {% for pt in equity_curve %}
      <div class="bar" title="{{ pt.created_at }}: ${{ pt.equity }}" style="height: {{ pt.height_pct }}%"></div>
      {% endfor %}
    </div>
    {% if not equity_curve %}<p style="color:var(--muted)">No cycles yet — equity updates after first trading cycle.</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Open Positions</h2>
    {% if positions %}
    <table>
      <tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Price</th><th>P&L</th></tr>
      {% for p in positions %}
      <tr>
        <td>{{ p.symbol }}</td><td>{{ p.qty }}</td>
        <td>${{ "%.2f"|format(p.avg_entry_price) }}</td>
        <td>${{ "%.2f"|format(p.current_price) }}</td>
        <td class="{{ 'pos' if p.unrealized_pl >= 0 else 'neg' }}">${{ "%.2f"|format(p.unrealized_pl) }} ({{ "%.2f"|format(p.unrealized_plpc) }}%)</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}<p style="color:var(--muted)">No open positions</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Recent LLM Decisions</h2>
    {% if decisions %}
    <table>
      <tr><th>Time</th><th>Ticker</th><th>Action</th><th>Pct</th><th>Approved</th><th>Reason</th></tr>
      {% for d in decisions %}
      <tr>
        <td>{{ d.cycle_time[:19] }}</td><td>{{ d.ticker }}</td><td>{{ d.action }}</td>
        <td>{{ d.pct }}</td>
        <td>{{ '✓' if d.approved else '✗' }}</td>
        <td>{{ d.reason[:60] }}{% if d.reason|length > 60 %}…{% endif %}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}<p style="color:var(--muted)">No decisions yet — waiting for first cycle.</p>{% endif %}
  </div>

  <div class="section card">
    <h2>Recent Cycles</h2>
    {% if cycles %}
    <table>
      <tr><th>ID</th><th>Time</th><th>Status</th><th>Summary</th></tr>
      {% for c in cycles %}
      <tr>
        <td>{{ c.id }}</td><td>{{ c.created_at[:19] }}</td><td>{{ c.status }}</td>
        <td>{{ (c.llm_summary or '')[:80] }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}<p style="color:var(--muted)">No cycles yet.</p>{% endif %}
  </div>

  <script>
    setTimeout(() => location.reload(), 15000);
    async function pollActivity() {
      try {
        const r = await fetch('/api/activity');
        const d = await r.json();
        const el = document.getElementById('activity-feed');
        if (!el || !d.activity) return;
        el.innerHTML = d.activity.map(a =>
          `<div class="activity-line ${a.level}"><span class="ts">${(a.created_at||'').slice(11,19)}</span>` +
          `<span class="ph">[${a.phase||'bot'}]</span> ${a.message}</div>`
        ).join('');
      } catch (e) {}
    }
    setInterval(pollActivity, 5000);
  </script>
</body>
</html>
"""


def _equity_bars(curve: list[dict]) -> list[dict]:
    if not curve:
        return []
    vals = [c["equity"] for c in curve]
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1
    out = []
    for c in curve[-60:]:
        h = (c["equity"] - lo) / span * 100
        out.append({**c, "height_pct": max(2, h)})
    return out


def _health_banner_class(health) -> str:
    if not health.all_ready:
        return "error"
    if health.market_phase in ("weekend", "before_open", "closed", "after_close"):
        return "ready"
    return "ready" if health.market_phase == "market_open" else "warn"


def _last_signal_rows(store: BotStore) -> list[dict]:
    cycles = store.recent_cycles(1)
    if not cycles:
        return []
    raw = cycles[0].get("context_json")
    if not raw:
        return []
    try:
        ctx = json.loads(raw) if isinstance(raw, str) else raw
        rows = ctx.get("watchlist", [])
        rows.sort(key=lambda r: r.get("active_score", 0), reverse=True)
        return rows[:20]
    except Exception:
        return []


@app.route("/")
def index():
    today = now_et().date()
    health = run_health_check()
    equity = cash = 0.0
    day_pnl = day_pnl_pct = 0.0
    positions: list = []

    client = AlpacaClient()
    if client.configured:
        try:
            acct = client.get_account()
            equity = acct["equity"]
            cash = acct["cash"]
            positions = client.get_positions()
        except Exception:
            pass

    day_start = store.get_day_start_equity(today) or equity
    if day_start:
        day_pnl = equity - day_start
        day_pnl_pct = (day_pnl / day_start * 100) if day_start else 0.0

    return render_template_string(
        DASHBOARD_HTML,
        equity=equity,
        cash=cash,
        day_pnl=day_pnl,
        day_pnl_pct=day_pnl_pct,
        positions=positions,
        cycles_today=store.count_cycles_today(today),
        orders_today=store.count_orders_today(today),
        halted=store.is_halted_today(today),
        market_open=is_market_open(),
        now_et=now_et().strftime("%Y-%m-%d %H:%M"),
        watchlist=config.WATCHLIST,
        trading_mode=config.TRADING_MODE,
        equity_curve=_equity_bars(store.equity_curve(200)),
        decisions=store.recent_decisions(30),
        cycles=store.recent_cycles(15),
        activity=store.recent_activity(50),
        orders=store.recent_orders(20),
        signal_rows=_last_signal_rows(store),
        runner_status=store.get_runner_status(),
        health=health,
        health_class=_health_banner_class(health),
        market_phase=health.market_phase,
    )


@app.route("/api/activity")
def api_activity():
    return jsonify({
        "activity": store.recent_activity(60),
        "runner": store.get_runner_status(),
        "market_open": is_market_open(),
        "now_et": now_et().isoformat(),
    })


@app.route("/api/health")
def api_health():
    return jsonify(run_health_check().to_dict())


@app.route("/api/status")
def api_status():
    client = AlpacaClient()
    data = run_health_check().to_dict()
    data["alpaca_configured"] = client.configured
    if client.configured:
        try:
            data["account"] = client.get_account()
            data["positions"] = client.get_positions()
        except Exception as exc:
            data["alpaca_error"] = str(exc)
    data["cycles"] = store.recent_cycles(10)
    data["equity_curve"] = store.equity_curve(100)
    data["daily_reports"] = store.daily_reports(14)
    data["market_open"] = is_market_open()
    return jsonify(data)


def main() -> None:
    config.ensure_dirs()
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
