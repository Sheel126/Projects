import json
from datetime import date

import pytest

from liquid_atm_quant.data.universe import (
    parse_ishares_csv,
    parse_ishares_json,
    parse_sp500_history,
    resolve_symbol,
    wayback_capture_urls,
)

IWB_CSV = """iShares Russell 1000 ETF
Fund Holdings as of,"Sep 17, 2026"
Inception Date,"May 15, 2000"
Shares Outstanding,"117,500,000.00"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency
"NVDA","NVIDIA","Information Technology","Equity","3,551,016,774.36","7.26","3,551,016,774.36","16,189,554.00","219.34","United States","NASDAQ","USD"
"BRKB","BERKSHIRE HATHAWAY INC CLASS B","Financials","Equity","100.00","1.42","100.00","1.00","500.00","United States","New York Stock Exchange Inc.","USD"
"XTSLA","BLK CSH FND TREASURY SL AGENCY","Cash and/or Derivatives","Money Market","1,000.00","0.01","1,000.00","1,000.00","1.00","United States","-","USD"
"-","USD CASH","Cash and/or Derivatives","Cash","5.00","-","5.00","5.00","1.00","United States","-","USD"
"""


def test_parse_ishares_csv_keeps_equities_only():
    as_of, holdings = parse_ishares_csv(IWB_CSV)
    assert as_of == date(2026, 9, 17)
    assert [h.ticker for h in holdings] == ["NVDA", "BRKB"]
    assert holdings[0].weight == pytest.approx(7.26)
    assert holdings[0].sector == "Information Technology"


def test_parse_ishares_csv_rejects_other_files():
    with pytest.raises(ValueError):
        parse_ishares_csv("<!DOCTYPE html><html>not a csv</html>")


def test_parse_ishares_json_handles_archived_format():
    body = json.dumps({"aaData": [
        ["AAPL", "APPLE INC", "Information Technology", "Equity",
         {"display": "$697,036,370.10", "raw": 697036370.1}, {"display": "3.42", "raw": 3.42124}],
        ["XL", "XL GROUP LTD", "Financials", "Equity",
         {"display": "$7,113,641.52", "raw": 7113641.52}, {"display": "0.03", "raw": 0.03492}],
        ["USD", "USD CASH", "Cash and/or Derivatives", "Cash", {"raw": 1.0}, {"raw": 0.0}],
    ]})
    holdings = parse_ishares_json(body)
    assert [h.ticker for h in holdings] == ["AAPL", "XL"]  # delisted names kept, cash dropped
    assert holdings[1].weight == pytest.approx(0.03492)


def test_parse_sp500_history():
    rows = parse_sp500_history("date,tickers\n1996-01-02,\"AAPL,ABT, AAL\"\n2026-01-02,\"AAPL,NVDA\"\n")
    assert rows[0] == (date(1996, 1, 2), ["AAL", "AAPL", "ABT"])
    assert rows[1][0] == date(2026, 1, 2)


def test_wayback_picks_newest_capture_per_as_of_date():
    base = "https://www.ishares.com/us/products/239707/x/1467271812596.ajax?tab=all&fileType=json&asOfDate="
    # Exactly the shape web.archive.org returns: header row first, then captures.
    payload = [
        ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"],
        ["k", "20201010000000", base + "20171229", "application/json", "200", "d", "1"],
        ["k", "20231008233211", base + "20171229", "application/json", "200", "d", "1"],  # newer capture wins
        ["k", "20231008233211", base + "20180330", "application/json", "200", "d", "1"],
        ["k", "20231008233211", base.replace("tab=all", "tab=top") + "20180330", "application/json", "200", "d", "1"],
        ["k", "20231008233211", base + "20180330", "text/html", "200", "d", "1"],       # not the data file
        ["k", "20231008233211", base.replace("asOfDate=", "x="), "application/json", "200", "d", "1"],
    ]
    urls = wayback_capture_urls(payload)
    assert set(urls) == {date(2017, 12, 29), date(2018, 3, 30)}
    assert urls[date(2017, 12, 29)].startswith("http://web.archive.org/web/20231008233211id_/")


def test_resolve_symbol_maps_share_classes():
    known = {"AAPL", "BRK.B", "BF.B"}
    assert resolve_symbol("AAPL", known) == "AAPL"
    assert resolve_symbol("BRKB", known) == "BRK.B"
    assert resolve_symbol("BF-B", known) == "BF.B"
    assert resolve_symbol("DELISTED", known) is None
