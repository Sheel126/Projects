import os
import glob
from datetime import datetime
import pandas as pd
import yfinance as yf
from flask import Flask, render_template_string, request, abort

try:
    import markdown

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

app = Flask(__name__)

# Ensure absolute paths resolve relative to project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
LOGS_BASE_DIR = os.path.join(BASE_DIR, "data", "logs")

MODES = {
    "weekly": os.path.join(LOGS_BASE_DIR, "weekly"),
    "daily": os.path.join(LOGS_BASE_DIR, "daily"),
}


def render_md(text: str) -> str:
    """Renders Markdown to HTML using python-markdown with fallback."""
    if MARKDOWN_AVAILABLE:
        return markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    return f"<pre style='white-space: pre-wrap;'>{text}</pre>"


def get_trade_plans():
    """Scans weekly and daily log directories strictly for CSV Trade Plans."""
    plans = {"weekly": [], "daily": []}
    for mode, folder_path in MODES.items():
        if not os.path.exists(folder_path):
            continue
        plan_files = glob.glob(os.path.join(folder_path, "trade_plan_*.csv"))
        for file_path in sorted(plan_files, reverse=True):
            file_name = os.path.basename(file_path)
            date_part = (
                file_name.replace("trade_plan_clean_", "")
                .replace("trade_plan_", "")
                .replace(".csv", "")
            )
            try:
                datetime.strptime(date_part[:10], "%Y-%m-%d")
                plans[mode].append(
                    {
                        "date": date_part[:10],
                        "file_name": file_name,
                        "is_clean": "clean" in file_name,
                    }
                )
            except ValueError:
                continue
    return plans


def get_ai_reports():
    """Scans weekly and daily log directories strictly for Markdown AI Reports."""
    reports = []
    for mode, folder_path in MODES.items():
        if not os.path.exists(folder_path):
            continue
        report_files = glob.glob(os.path.join(folder_path, "ai_studio_report_*.md"))
        for file_path in sorted(report_files, reverse=True):
            file_name = os.path.basename(file_path)
            date_part = file_name.replace("ai_studio_report_", "").replace(".md", "")
            try:
                datetime.strptime(date_part[:10], "%Y-%m-%d")
                reports.append(
                    {
                        "date": date_part[:10],
                        "mode": mode,
                        "file_name": file_name,
                        "file_path": file_path,
                    }
                )
            except ValueError:
                continue
    return sorted(reports, key=lambda x: x["date"], reverse=True)


def fetch_live_prices(symbols):
    """Fetches real-time prices using yfinance fast_info."""
    if not symbols:
        return {}
    try:
        tickers_str = " ".join(symbols)
        tickers = yf.Tickers(tickers_str)
        prices = {}
        for sym in symbols:
            try:
                prices[sym] = round(tickers.tickers[sym].fast_info["last_price"], 2)
            except Exception:
                prices[sym] = "N/A"
        return prices
    except Exception as e:
        print(f"Error fetching live prices: {e}")
        return {sym: "N/A" for sym in symbols}


# --- TEMPLATES ---

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Finance Vibe Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #fdfdfd; color: #333; }
        h1 { color: #111; border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }
        h2 { color: #444; margin-top: 20px; text-transform: uppercase; font-size: 1.0em; letter-spacing: 0.5px;}
        .ai-banner { background: #f0f4ff; border: 1px solid #d0e0ff; border-radius: 8px; padding: 18px 24px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
        .ai-banner-text h3 { margin: 0 0 5px 0; color: #1a73e8; font-size: 1.2em; }
        .ai-banner-text p { margin: 0; color: #5f6368; font-size: 0.95em; }
        .ai-btn { background: #1a73e8; color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.95em; transition: background 0.2s; }
        .ai-btn:hover { background: #1557b0; }
        .container { display: flex; gap: 40px; }
        .column { flex: 1; background: #fff; padding: 20px; border-radius: 6px; border: 1px solid #e1e4e8; }
        ul { list-style: none; padding: 0; }
        li { padding: 10px; border-bottom: 1px solid #f1f1f1; display: flex; justify-content: space-between; align-items: center; }
        li:last-child { border: none; }
        a { color: #0366d6; text-decoration: none; font-weight: 500; }
        a:hover { text-decoration: underline; }
        .badge { font-size: 0.8em; padding: 3px 8px; border-radius: 12px; background: #e1f5fe; color: #0288d1; font-weight: bold; }
        .badge.clean { background: #e8f5e9; color: #2e7d32; }
    </style>
</head>
<body>
    <h1>🚀 Finance Vibe Execution Hub</h1>
    
    <div class="ai-banner">
        <div class="ai-banner-text">
            <h3>🤖 AI Studio Market Analyst Reports</h3>
            <p>Access automated daily momentum scans, setup evaluations, and market contextual breakdowns.</p>
        </div>
        <a href="/ai-reports" class="ai-btn">View AI Reports →</a>
    </div>

    <div class="container">
        <div class="column">
            <h2>📅 Weekly Framework (10Y Lookback)</h2>
            {% if plans['weekly'] %}
                <ul>
                {% for item in plans['weekly'] %}
                    <li>
                        <a href="/view/weekly/{{ item['date'] }}?file={{ item['file_name'] }}">Trade Plan ({{ item['date'] }})</a>
                        <span class="badge {% if item['is_clean'] %}clean{% endif %}">{{ 'Cleaned' if item['is_clean'] else 'Raw' }}</span>
                    </li>
                {% endfor %}
                </ul>
            {% else %}
                <p style="color:#777;">No weekly trade plans discovered.</p>
            {% endif %}
        </div>
        
        <div class="column">
            <h2>⚡ Daily Framework (2Y Lookback)</h2>
            {% if plans['daily'] %}
                <ul>
                {% for item in plans['daily'] %}
                    <li>
                        <a href="/view/daily/{{ item['date'] }}?file={{ item['file_name'] }}">Trade Plan ({{ item['date'] }})</a>
                        <span class="badge {% if item['is_clean'] %}clean{% endif %}">{{ 'Cleaned' if item['is_clean'] else 'Raw' }}</span>
                    </li>
                {% endfor %}
                </ul>
            {% else %}
                <p style="color:#777;">No daily trade plans discovered.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

REPORTS_HUB_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Studio Reports - Finance Vibe</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #fdfdfd; color: #333; }
        h1 { color: #111; border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }
        .back { display: inline-block; margin-bottom: 20px; color: #0366d6; text-decoration: none; font-weight: 500; }
        .report-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; margin-top: 20px; }
        .card { background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card h3 { margin: 0 0 10px 0; font-size: 1.1em; color: #1b1f23; }
        .card-meta { font-size: 0.85em; color: #586069; margin-bottom: 15px; }
        .badge-mode { text-transform: uppercase; font-weight: bold; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; }
        .badge-mode.daily { background: #fff3cd; color: #856404; }
        .badge-mode.weekly { background: #d4edda; color: #155724; }
        .view-btn { display: inline-block; background: #f6f8fa; border: 1px solid #d1d5da; color: #24292e; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: 600; font-size: 0.9em; }
        .view-btn:hover { background: #eef1f4; }
    </style>
</head>
<body>
    <a class="back" href="/">← Back to Main Dashboard</a>
    <h1>🤖 AI Studio Market Analyst Reports</h1>
    <p>Select a generated report to review AI-driven technical evaluations and scanner insights.</p>

    {% if reports %}
        <div class="report-grid">
            {% for report in reports %}
                <div class="card">
                    <h3>Report: {{ report['date'] }}</h3>
                    <div class="card-meta">
                        Timeframe: <span class="badge-mode {{ report['mode'] }}">{{ report['mode'] }}</span> | File: <code>{{ report['file_name'] }}</code>
                    </div>
                    <a class="view-btn" href="/view-report/{{ report['mode'] }}/{{ report['file_name'] }}">Read Full Report →</a>
                </div>
            {% endfor %}
        </div>
    {% else %}
        <p style="color:#777; margin-top: 30px;">No AI Studio reports generated yet. Run <code>ai_studio_scanner_analyst.py</code> to generate analysis.</p>
    {% endif %}
</body>
</html>
"""

REPORT_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Report - {{ date }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 30px; background: #fdfdfd; color: #24292e; }
        .back { display: inline-block; margin-bottom: 20px; color: #0366d6; text-decoration: none; font-weight: 500; }
        .report-container { background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 35px; line-height: 1.6; max-width: 1000px; margin: 0 auto; }
        .report-container h1, .report-container h2, .report-container h3 { color: #1b1f23; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 1.5em; }
        .report-container code { background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }
        .report-container pre { background: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }
        .report-container table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        .report-container th, .report-container td { border: 1px solid #dfe2e5; padding: 8px 12px; }
        .report-container th { background: #f6f8fa; }
    </style>
</head>
<body>
    <a class="back" href="/ai-reports">← Back to AI Reports Hub</a>
    <div class="report-container">
        {{ content_html|safe }}
    </div>
</body>
</html>
"""

VIEW_CSV_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Trade Plan - {{ date }} ({{ mode }})</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 30px; background: #fdfdfd; color: #24292e; }
        h1 { color: #111; margin-bottom: 5px; }
        .meta { color: #666; margin-bottom: 20px; font-size: 0.95em; }
        .back { display: inline-block; margin-bottom: 20px; color: #0366d6; text-decoration: none; font-weight: 500; }
        .table-container { width: 100%; overflow-x: auto; background: #fff; border: 1px solid #e1e4e8; border-radius: 6px; }
        table.csv-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9em; }
        table.csv-table th { background: #f6f8fa; padding: 12px; border-bottom: 2px solid #e1e4e8; font-weight: 600; }
        table.csv-table td { padding: 10px 12px; border-bottom: 1px solid #eaecef; }
        .ticker-link { color: #0056b3; text-decoration: none; font-weight: bold; }
        .ticker-link:hover { text-decoration: underline; }
        .live-price-cell { font-weight: 600; color: #2e7d32; background-color: #f4faf4; }
    </style>
</head>
<body>
    <a class="back" href="/">← Back to Dashboard</a>
    <h1>📋 Trade Plan Preview</h1>
    <div class="meta">Execution Cadence: <strong>{{ mode|upper }}</strong> | Log Date: <strong>{{ date }}</strong> | Source File: <code>{{ file_name }}</code></div>
    <div class="table-container">
        {{ content_html|safe }}
    </div>
</body>
</html>
"""

# --- ROUTES ---


@app.route("/")
def index():
    plans = get_trade_plans()
    return render_template_string(INDEX_TEMPLATE, plans=plans)


@app.route("/ai-reports")
def ai_reports_hub():
    reports = get_ai_reports()
    return render_template_string(REPORTS_HUB_TEMPLATE, reports=reports)


@app.route("/view-report/<mode>/<file_name>")
def view_report(mode, file_name):
    if mode not in MODES:
        abort(404, "Invalid mode.")
    target_path = os.path.abspath(os.path.join(MODES[mode], file_name))
    if not target_path.startswith(MODES[mode]) or not os.path.exists(target_path):
        abort(404, "Report file not found.")

    with open(target_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    date_str = file_name.replace("ai_studio_report_", "").replace(".md", "")[:10]
    content_html = render_md(md_text)
    return render_template_string(
        REPORT_VIEW_TEMPLATE, date=date_str, content_html=content_html
    )


@app.route("/view/<mode>/<date>")
def view_csv(mode, date):
    if mode not in MODES:
        abort(404, "Invalid mode.")
    requested_file = request.args.get("file")
    if not requested_file:
        abort(400, "Missing file parameter.")

    target_path = os.path.abspath(os.path.join(MODES[mode], requested_file))
    if not os.path.exists(target_path):
        abort(404, "File not found.")

    try:
        df = pd.read_csv(target_path)
        df.columns = df.columns.str.strip()

        symbol_col = next(
            (col for col in df.columns if col.lower() in ["symbol", "ticker"]), None
        )
        if symbol_col is not None:
            raw_symbols = [
                str(x).strip().upper() for x in df[symbol_col].dropna().unique()
            ]
            live_price_map = fetch_live_prices(raw_symbols)

            df["Live Price"] = df[symbol_col].apply(
                lambda x: (
                    f'<span class="live-price-cell">${live_price_map.get(str(x).strip().upper(), "N/A")}</span>'
                    if pd.notna(x)
                    else ""
                )
            )

            cols = list(df.columns)
            symbol_idx = cols.index(symbol_col)
            cols.insert(symbol_idx + 1, cols.pop(cols.index("Live Price")))
            df = df[cols]

            df[symbol_col] = df[symbol_col].apply(
                lambda x: (
                    f'<a href="https://finance.yahoo.com/quote/{str(x).strip().upper()}" target="_blank" rel="noopener noreferrer" class="ticker-link">{x}</a>'
                    if pd.notna(x)
                    else ""
                )
            )

        content_html = df.to_html(
            classes="csv-table", index=False, border=0, escape=False
        )
        return render_template_string(
            VIEW_CSV_TEMPLATE,
            mode=mode,
            date=date,
            file_name=requested_file,
            content_html=content_html,
        )
    except Exception as e:
        return f"<h3>❌ Error loading trade plan:</h3><pre>{str(e)}</pre>", 500


if __name__ == "__main__":
    for path in MODES.values():
        os.makedirs(path, exist_ok=True)
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=5000, debug=debug)
