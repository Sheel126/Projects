"""Unified Finance-Vibe signal layer for the trading bot."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from finance_vibe.analysis_engine import (
    build_features,
    market_regime_ok,
    relative_strength,
    score_last_row,
    sentiment_action,
)
from finance_vibe.bot import config as bot_config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.daily_activity import (
    compute_active_score,
    compute_tight_stop,
    sector_for,
)
from finance_vibe.bot.intraday_signals import enrich_intraday_metrics
from finance_vibe.bot.models import TickerSnapshot
from finance_vibe.coiled_cobra import add_macro_indicators, evaluate_coiled_cobra
from finance_vibe.coiled_cobra_backtest import detect_cobra_setup_at_bar
from finance_vibe.ml_ranker import ML_PRED_COL, ML_RANK_COL, attach_ml_ranks, predict_returns
from finance_vibe.swing_scanner import add_indicators, detect_setup_at_bar, evaluate_setup
from finance_vibe.trade_planner import calculate_stock_levels

logger = logging.getLogger(__name__)

COBRA_MODE = "daily"  # bot uses daily OHLCV for coil scoring


def compute_conviction(snap: TickerSnapshot) -> float:
    """0-100 composite from Finance-Vibe layers (higher = stronger long bias)."""
    score = 0.0
    if snap.vibe_score is not None:
        score += max(0, snap.vibe_score) * 2.0
    if snap.setup_type == "SETUP_LONG":
        score += 35.0
    elif snap.setup_type and str(snap.setup_type).startswith("PENDING_"):
        score += 15.0
    if snap.coiled_cobra_grade:
        score += 25.0 if "A" in snap.coiled_cobra_grade else 15.0
    if snap.ml_rank is not None and snap.ml_rank <= 5:
        score += max(0, 21 - snap.ml_rank * 4)
    if snap.regime_ok:
        score += 10.0
    if snap.rs_63d is not None and snap.rs_63d > 0:
        score += min(12.0, snap.rs_63d * 60.0)
    if snap.vs_qqq_pct is not None and snap.vs_qqq_pct > 0:
        score += 5.0
    if snap.rvol is not None and snap.rvol >= 1.2:
        score += 6.0
    if snap.in_position:
        if snap.position_pnl_pct is not None and snap.position_pnl_pct >= 3:
            score -= 12.0
        elif snap.position_pnl_pct is not None and snap.position_pnl_pct <= -2:
            score -= 8.0
    if snap.rsi is not None and snap.rsi > 72:
        score -= 10.0
    return round(max(0.0, min(100.0, score)), 1)


def compute_relative_volume(df: pd.DataFrame, lookback: int = 20) -> float | None:
    """Today's volume / average of prior N sessions."""
    if df is None or df.empty or "Volume" not in df.columns or len(df) < lookback + 1:
        return None
    vols = df["Volume"].astype(float)
    today = float(vols.iloc[-1])
    avg = float(vols.iloc[-(lookback + 1):-1].mean())
    if avg <= 0:
        return None
    return round(today / avg, 3)


class SignalEngine:
    """Finance-Vibe + live market data -> per-ticker snapshots for the LLM."""

    def __init__(
        self,
        alpaca: AlpacaClient | None = None,
        swing_profile: str | None = None,
        benchmark: str | None = None,
    ) -> None:
        self.alpaca = alpaca or AlpacaClient()
        self.swing_profile = swing_profile or bot_config.SWING_PROFILE
        self.benchmark = (benchmark or bot_config.BENCHMARK).upper()
        self._bench_swing_df: pd.DataFrame | None = None

    def _bench_df(self) -> pd.DataFrame | None:
        if self._bench_swing_df is not None:
            return self._bench_swing_df
        raw = self.alpaca.get_daily_bars(self.benchmark, days=220)
        if raw.empty or len(raw) < 60:
            return None
        self._bench_swing_df = add_indicators(raw.copy(), mode=self.swing_profile)
        if not self._bench_swing_df.empty:
            self._bench_swing_df["EMA50_rising"] = (
                self._bench_swing_df["EMA50"] > self._bench_swing_df["EMA50"].shift(1)
            )
        return self._bench_swing_df

    def _load_bars(self, ticker: str) -> pd.DataFrame:
        df = self.alpaca.get_daily_bars(ticker, days=220)
        if df.empty or len(df) < 60:
            try:
                import yfinance as yf
                hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
                if not hist.empty:
                    hist = hist.reset_index()
                    if "Datetime" in hist.columns:
                        hist.rename(columns={"Datetime": "Date"}, inplace=True)
                    df = hist[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
            except Exception as exc:
                logger.warning("yfinance fallback %s: %s", ticker, exc)
        return df

    def _apply_levels_from_row(self, row: dict, snap: TickerSnapshot) -> None:
        try:
            levels = calculate_stock_levels(row, mode=self.swing_profile)
            snap.entry = round(float(levels[0]), 2)
            snap.stop = round(float(levels[1]), 2)
            snap.target1 = round(float(levels[2]), 2)
            snap.target2 = round(float(levels[3]), 2)
        except Exception as exc:
            logger.debug("levels failed %s: %s", snap.ticker, exc)

    def build_snapshot(
        self,
        ticker: str,
        price_info: dict[str, float],
        position: dict[str, Any] | None = None,
        order_flags: dict[str, bool] | None = None,
    ) -> TickerSnapshot:
        ticker = ticker.upper()
        order_flags = order_flags or {}
        df = self._load_bars(ticker)
        bench = self._bench_df()

        snap = TickerSnapshot(
            ticker=ticker,
            price=round(price_info.get("price", 0), 2),
            change_pct=round(price_info.get("change_pct", 0), 3),
            change_from_open_pct=round(price_info.get("change_from_open_pct", 0), 3),
            rsi=None,
            ema20=None,
            ema50=None,
            atr=None,
            setup_type=None,
            setup_notes=None,
            entry=None,
            stop=None,
            target1=None,
            target2=None,
            vs_qqq_pct=None,
            regime_ok=None,
            in_position=bool(position),
            position_qty=float(position["qty"]) if position else 0.0,
            position_pnl_pct=float(position.get("pnl_pct", 0)) if position else None,
            vibe_score=None,
            vibe_sentiment=None,
            vibe_action=None,
            coiled_cobra_score=None,
            coiled_cobra_grade=None,
            coiled_cobra_checks=None,
            ml_pred_return=None,
            ml_rank=None,
            conviction=0.0,
            signal_sources=[],
            rs_63d=None,
            has_open_buy_order=order_flags.get("buy", False),
            has_open_sell_order=order_flags.get("sell", False),
        )

        bench_chg = price_info.get("_benchmark_change_pct")
        if bench_chg is not None:
            snap.vs_qqq_pct = round(snap.change_pct - bench_chg, 3)

        if len(df) < 60:
            snap.conviction = compute_conviction(snap)
            snap.sector = sector_for(ticker)
            snap.active_score = compute_active_score(snap)
            snap.tight_stop = compute_tight_stop(snap)
            return snap

        snap.rvol = compute_relative_volume(df)

        # Always attach RS vs QQQ when possible (even without confirmed setup)
        if bench is not None and not bench.empty:
            try:
                ok_rs, rel = relative_strength(df, bench)
                if rel is not None:
                    snap.rs_63d = rel
                if snap.regime_ok is None:
                    snap.regime_ok = market_regime_ok(bench, bench.iloc[-1].get("Date"))
            except Exception as exc:
                logger.debug("RS %s: %s", ticker, exc)

        # --- Macro Vibe Score (analysis_engine) ---
        try:
            feat = build_features(df.copy())
            if not feat.empty:
                last = feat.iloc[-1]
                vibe = score_last_row(last)
                sent, action = sentiment_action(vibe)
                snap.vibe_score = vibe
                snap.vibe_sentiment = sent
                snap.vibe_action = action
                snap.signal_sources.append("macro_vibe")
        except Exception as exc:
            logger.debug("vibe score %s: %s", ticker, exc)

        # --- Swing scanner (high_beta) ---
        indicated = add_indicators(df.copy(), mode=self.swing_profile)
        if not indicated.empty:
            latest = indicated.iloc[-1]
            snap.rsi = round(float(latest["RSI"]), 2)
            snap.ema20 = round(float(latest["EMA20"]), 2)
            snap.ema50 = round(float(latest["EMA50"]), 2)
            snap.atr = round(float(latest["ATR"]), 2)

        swing_row = detect_setup_at_bar(df, ticker, mode=self.swing_profile, benchmark_df=bench)
        if swing_row:
            snap.setup_type = swing_row.get("Setup Type")
            snap.setup_notes = swing_row.get("Notes")
            snap.regime_ok = swing_row.get("Regime OK")
            snap.rs_63d = swing_row.get("RS 63d")
            snap.signal_sources.append("swing_confirmed")
            self._apply_levels_from_row(swing_row, snap)
        else:
            near = evaluate_setup(indicated.iloc[:-1], mode=self.swing_profile) if len(indicated) >= 3 else None
            if near:
                snap.setup_type = f"PENDING_{near['Setup Type']}"
                snap.setup_notes = near.get("Notes", "") + " (unconfirmed)"
                snap.signal_sources.append("swing_pending")

        # --- Coiled Cobra ---
        try:
            cobra_row = detect_cobra_setup_at_bar(df, ticker, benchmark_df=bench)
            if cobra_row:
                snap.coiled_cobra_score = float(cobra_row.get("Score", 0))
                snap.coiled_cobra_grade = str(cobra_row.get("Grade", ""))
                snap.coiled_cobra_checks = str(cobra_row.get("Checks Met", ""))
                snap.rs_63d = cobra_row.get("RS 63d") or snap.rs_63d
                snap.signal_sources.append("coiled_cobra")
                if not snap.setup_type or snap.setup_type.startswith("PENDING"):
                    snap.setup_type = snap.setup_type or "SETUP_LONG"
                    cobra_row["Source"] = "coiled_cobra"
                    cobra_row["Mode"] = self.swing_profile
                    self._apply_levels_from_row(cobra_row, snap)
            else:
                cobra_df = add_macro_indicators(df.copy())
                if len(cobra_df) >= 25:
                    cobra_eval = evaluate_coiled_cobra(cobra_df, bench)
                    if cobra_eval:
                        snap.coiled_cobra_score = float(cobra_eval["Score"])
                        snap.coiled_cobra_grade = str(cobra_eval["Grade"])
                        snap.coiled_cobra_checks = str(cobra_eval.get("Checks Met", ""))
                        snap.rs_63d = cobra_eval.get("RS 63d") or snap.rs_63d
                        snap.signal_sources.append("coiled_cobra_watch")
        except Exception as exc:
            logger.debug("coiled cobra %s: %s", ticker, exc)

        snap.conviction = compute_conviction(snap)
        snap.sector = sector_for(ticker)
        if bot_config.USE_INTRADAY_SIGNALS and snap.price > 0:
            try:
                ibars = self.alpaca.get_intraday_bars(ticker)
                metrics = enrich_intraday_metrics(snap.price, ibars)
                snap.vwap = metrics.get("vwap")
                snap.price_vs_vwap_pct = metrics.get("price_vs_vwap_pct")
                snap.ibs = metrics.get("ibs")
                snap.orb_signal = metrics.get("orb_signal")
                snap.day_high = metrics.get("day_high")
                snap.day_low = metrics.get("day_low")
            except Exception as exc:
                logger.debug("intraday metrics %s: %s", ticker, exc)
        snap.active_score = compute_active_score(snap)
        snap.tight_stop = compute_tight_stop(snap)
        return snap

    def _attach_ml_ranks(self, snapshots: list[TickerSnapshot]) -> None:
        rows = []
        for s in snapshots:
            if s.coiled_cobra_score is None:
                continue
            close = s.price or 1.0
            rows.append({
                "Symbol": s.ticker,
                "Score": s.coiled_cobra_score,
                "Close": close,
                "EMA20": s.ema20 or close,
                "EMA50": s.ema50 or close,
                "ATR": s.atr or 1.0,
                "Fib 61.8%": None,
                "Fib 78.6%": None,
            })
        if not rows:
            return
        frame = pd.DataFrame(rows)
        try:
            ranked = attach_ml_ranks(frame, mode=COBRA_MODE)
        except Exception:
            preds = predict_returns(frame, mode=COBRA_MODE)
            ranked = frame.copy()
            ranked[ML_PRED_COL] = preds
            ranked[ML_RANK_COL] = preds.rank(method="dense", ascending=False)

        by_sym = {str(r["Symbol"]).upper(): r for _, r in ranked.iterrows()}
        for s in snapshots:
            row = by_sym.get(s.ticker)
            if row is None:
                continue
            pred = row.get(ML_PRED_COL)
            rank = row.get(ML_RANK_COL)
            if pd.notna(pred):
                s.ml_pred_return = round(float(pred), 4)
            if pd.notna(rank):
                s.ml_rank = int(rank)
                s.signal_sources.append("ml_rank")
            s.conviction = compute_conviction(s)

    def build_market_regime(self, benchmark_price: dict[str, float]) -> dict[str, Any]:
        bench = self._bench_df()
        regime_ok = None
        if bench is not None and not bench.empty:
            regime_ok = market_regime_ok(bench, bench.iloc[-1].get("Date"))
        return {
            "benchmark": self.benchmark,
            "change_pct": benchmark_price.get("change_pct"),
            "change_from_open_pct": benchmark_price.get("change_from_open_pct"),
            "regime_bull_ok": regime_ok,
            "interpretation": (
                "BULL: QQQ above rising EMA50/100 — favor longs"
                if regime_ok
                else "CAUTIOUS: QQQ regime weak — reduce new long size"
            ),
        }

    def build_watchlist(
        self,
        tickers: list[str],
        positions: list[dict[str, Any]] | None = None,
        open_orders: list[dict[str, Any]] | None = None,
    ) -> list[TickerSnapshot]:
        positions = positions or []
        open_orders = open_orders or []
        pos_map = {p["symbol"].upper(): p for p in positions}

        order_flags: dict[str, dict[str, bool]] = {}
        for o in open_orders:
            sym = str(o.get("symbol", "")).upper()
            if not sym:
                continue
            flags = order_flags.setdefault(sym, {"buy": False, "sell": False})
            side = str(o.get("side", "")).upper()
            if "BUY" in side:
                flags["buy"] = True
            if "SELL" in side:
                flags["sell"] = True

        symbols = list(dict.fromkeys(
            [t.upper() for t in tickers if t.upper() != self.benchmark]
            + list(pos_map.keys())
        ))

        all_prices = self.alpaca.get_latest_prices(symbols + [self.benchmark])
        bench = all_prices.get(self.benchmark, {})
        bench_change = bench.get("change_pct", 0.0)

        snapshots: list[TickerSnapshot] = []
        for sym in symbols:
            pinfo = all_prices.get(sym, {"price": 0, "change_pct": 0, "change_from_open_pct": 0})
            pinfo["_benchmark_change_pct"] = bench_change
            snapshots.append(
                self.build_snapshot(
                    sym, pinfo, pos_map.get(sym), order_flags.get(sym, {}),
                )
            )

        self._attach_ml_ranks(snapshots)
        for s in snapshots:
            s.sector = sector_for(s.ticker)
            s.active_score = compute_active_score(s)
            s.tight_stop = compute_tight_stop(s)
        snapshots.sort(
            key=lambda s: (
                s.active_score if bot_config.TRADING_MODE == "daily_active" else s.conviction
            ),
            reverse=True,
        )
        return snapshots

    @staticmethod
    def conviction_ranking(snapshots: list[TickerSnapshot]) -> list[dict[str, Any]]:
        return [
            {
                "rank": i + 1,
                "ticker": s.ticker,
                "conviction": s.conviction,
                "setup": s.setup_type,
                "vibe_score": s.vibe_score,
                "cobra_grade": s.coiled_cobra_grade,
                "ml_rank": s.ml_rank,
                "in_position": s.in_position,
            }
            for i, s in enumerate(sorted(snapshots, key=lambda x: x.conviction, reverse=True))
        ]
