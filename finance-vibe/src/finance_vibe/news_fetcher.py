from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List

import requests

try:
    from finance_vibe import config
    from finance_vibe.ai_models import NewsHeadline
except ImportError:
    from . import config
    from .ai_models import NewsHeadline


NEWS_MAX_HEADLINES_PER_TICKER = config.NEWS_MAX_HEADLINES_PER_TICKER
NEWS_LOOKBACK_DAYS = config.NEWS_LOOKBACK_DAYS
NEWS_SLEEP_SECONDS = config.NEWS_SLEEP_SECONDS


@dataclass
class TickerNews:
    symbol: str
    headlines: List[NewsHeadline]
    flags: List[str]


class NewsFetcher:
    """
    Very small wrapper around a news API. The exact provider is left
    configurable via environment so this module does not hard-code a
    vendor.

    ENV expectations (all optional):
      FINANCE_VIBE_NEWS_API_URL  - base URL of a news endpoint that
                                   accepts ?symbol= and ?days= params.
      FINANCE_VIBE_NEWS_API_KEY  - API key header value (if required).
      FINANCE_VIBE_NEWS_API_KEY_HEADER - header name for the key
                                         (default: Authorization).
    """

    def __init__(self) -> None:
        self._cache: Dict[str, TickerNews] = {}
        self.base_url = (
            os.getenv("FINANCE_VIBE_NEWS_API_URL")
            or os.getenv("NEWS_API_URL")
            or os.getenv("EVENTREGISTRY_API_URL")
            or ""
        )
        self.api_key = (
            os.getenv("FINANCE_VIBE_NEWS_API_KEY")
            or os.getenv("NEWS_API_KEY")
            or os.getenv("EVENTREGISTRY_API_KEY")
            or os.getenv("news.api.key")
            or ""
        )
        self.api_key_header = os.getenv(
            "FINANCE_VIBE_NEWS_API_KEY_HEADER", "Authorization"
        )
        self.provider = os.getenv("FINANCE_VIBE_NEWS_PROVIDER", "").strip().lower()
        if not self.provider and "eventregistry.org" in self.base_url.lower():
            self.provider = "eventregistry"

    def _from_cache(self, symbol: str) -> TickerNews | None:
        return self._cache.get(symbol.upper())

    def _save_cache(self, symbol: str, news: TickerNews) -> None:
        self._cache[symbol.upper()] = news

    def fetch_for_symbol(self, symbol: str) -> TickerNews:
        cached = self._from_cache(symbol)
        if cached:
            return cached

        flags: List[str] = []
        headlines: List[NewsHeadline] = []

        if not self.base_url:
            # No provider configured; return empty but mark as unavailable.
            flags.append("news_unavailable")
            news = TickerNews(symbol=symbol, headlines=headlines, flags=flags)
            self._save_cache(symbol, news)
            return news

        try:
            if self.provider == "eventregistry":
                headlines.extend(self._fetch_eventregistry(symbol, flags))
            else:
                headlines.extend(self._fetch_generic(symbol, flags))
        except Exception:  # noqa: BLE001
            flags.append("news_unavailable")

        news = TickerNews(symbol=symbol, headlines=headlines, flags=flags)
        self._save_cache(symbol, news)

        # naive pacing to be gentle on free-tier APIs
        time.sleep(NEWS_SLEEP_SECONDS)
        return news

    def _fetch_generic(self, symbol: str, flags: List[str]) -> List[NewsHeadline]:
        params = {
            "symbol": symbol.upper(),
            "days": str(NEWS_LOOKBACK_DAYS),
            "limit": str(NEWS_MAX_HEADLINES_PER_TICKER),
        }
        headers: Dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key

        resp = requests.get(self.base_url, params=params, headers=headers, timeout=15)
        if resp.status_code >= 400:
            flags.append(f"news_error_{resp.status_code}")
            return []

        payload = resp.json()
        items = payload if isinstance(payload, list) else payload.get("items", [])
        headlines: List[NewsHeadline] = []
        for item in items[:NEWS_MAX_HEADLINES_PER_TICKER]:
            parsed = self._parse_headline_item(item)
            if parsed:
                headlines.append(parsed)
        if not headlines:
            flags.append("news_no_headlines")
        return headlines

    def _fetch_eventregistry(self, symbol: str, flags: List[str]) -> List[NewsHeadline]:
        if not self.api_key:
            flags.append("news_missing_api_key")
            return []

        body = {
            "apiKey": self.api_key,
            "query": {
                "$query": {
                    "$and": [
                        {"keyword": symbol.upper()},
                        {"lang": "eng"},
                    ]
                }
            },
            "articlesSortBy": "date",
            "resultType": "articles",
            "articlesCount": NEWS_MAX_HEADLINES_PER_TICKER,
        }

        resp = requests.post(self.base_url, json=body, timeout=20)
        if resp.status_code >= 400:
            flags.append(f"news_error_{resp.status_code}")
            return []

        payload = resp.json()
        results = (
            payload.get("articles", {}).get("results", [])
            if isinstance(payload, dict)
            else []
        )
        headlines: List[NewsHeadline] = []
        for item in results[:NEWS_MAX_HEADLINES_PER_TICKER]:
            parsed = self._parse_headline_item(item)
            if parsed:
                headlines.append(parsed)
        if not headlines:
            flags.append("news_no_headlines")
        return headlines

    def _parse_headline_item(self, item: dict) -> NewsHeadline | None:
        if not isinstance(item, dict):
            return None

        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            return None

        raw_sent = str(item.get("sentiment", item.get("sentimentLabel", "unknown"))).lower()
        if raw_sent not in ("positive", "negative", "mixed", "unknown"):
            raw_sent = "unknown"
        return NewsHeadline(title=title, url=url, sentiment=raw_sent)

