from datetime import date, datetime, timezone

import pytest

from liquid_atm_quant.data.edgar import Edgar, parse_submissions

SUBMISSIONS = {
    "filings": {"recent": {
        "accessionNumber": ["0000320193-26-000079", "0000320193-26-000070", "0000320193-15-000001"],
        "form": ["8-K", "S-8", "8-K"],
        "filingDate": ["2026-07-30", "2026-07-15", "2015-01-05"],
        "acceptanceDateTime": ["2026-07-30T20:30:28.000Z", "2026-07-15T12:00:00.000Z", "2015-01-05T21:00:00.000Z"],
        "reportDate": ["2026-06-27", "", ""],
        "items": ["2.02,9.01", "", "8.01"],
        "primaryDocument": ["aapl-20260627.htm", "s8.htm", "old.htm"],
    }}
}


def test_parse_submissions_filters_and_keeps_utc_acceptance():
    filings = parse_submissions("0000320193", SUBMISSIONS, since=date(2016, 1, 1))
    assert len(filings) == 1  # S-8 dropped (form), 2015 8-K dropped (before `since`)
    f = filings[0]
    assert f.form == "8-K" and f.items == "2.02,9.01"
    # 20:30:28Z is 16:30:28 ET: the filing is public AFTER that Thursday's close.
    assert f.accepted_at == datetime(2026, 7, 30, 20, 30, 28, tzinfo=timezone.utc)
    assert f.report_date == date(2026, 6, 27)
    assert f.url.endswith("/320193/000032019326000079/aapl-20260627.htm")


def test_user_agent_must_carry_contact_email(redis_client):
    from liquid_atm_quant.infra.rate_limiter import edgar_limiter
    with pytest.raises(ValueError):
        Edgar("liquid-atm", edgar_limiter(redis_client))
