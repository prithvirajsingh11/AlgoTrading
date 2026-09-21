"""Deterministic market context builder for Jev AI decision engine.

Converts strictly historical market data (up to timestamp t), portfolio state,
and active strategy signals into a compact machine-readable state.
Zero future information is included.
"""

from __future__ import annotations
import json
import hashlib
from typing import Dict, Any, Optional, List, Union
import numpy as np
import pandas as pd

from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.orders import SignalEvent


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Calculates Relative Strength Index strictly on historical series."""
    if len(series) < 2:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean().iloc[-1]
    avg_loss = loss.rolling(window=period, min_periods=1).mean().iloc[-1]
    if avg_loss == 0 or np.isnan(avg_loss):
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(round(rsi, 2))


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    """Calculates MACD line, signal, and histogram strictly on historical series."""
    if len(series) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {
        "macd": float(round(macd_line.iloc[-1], 4)),
        "signal": float(round(signal_line.iloc[-1], 4)),
        "histogram": float(round(hist.iloc[-1], 4)),
    }


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates Average True Range (ATR) strictly on historical bars."""
    if len(df) < 2 or "high" not in df or "low" not in df or "close" not in df:
        return 0.0
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean().iloc[-1]
    return float(round(atr, 4)) if not np.isnan(atr) else 0.0


def compute_context_hash(context: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash of the canonical market context."""
    canonical_json = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_market_context(
    symbol: str,
    historical_slice: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    portfolio: Optional[Portfolio] = None,
    signals: Optional[List[SignalEvent]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a deterministic, compact machine-readable market context at decision timestamp.
    
    Guarantees zero future data lookahead bias. All indicators are derived
    exclusively from bars up to and including the current bar.
    """
    is_multi = isinstance(historical_slice, dict)

    if is_multi:
        symbols = list(historical_slice.keys())
        primary_sym = symbol if symbol in historical_slice else symbols[0]
        primary_df = historical_slice[primary_sym]
        last_row = primary_df.iloc[-1]
        timestamp = str(last_row["timestamp"])

        sym_a = symbols[0]
        sym_b = symbols[1] if len(symbols) > 1 else symbols[0]
        df_a = historical_slice[sym_a]
        df_b = historical_slice[sym_b]
        price_a = float(round(df_a["close"].iloc[-1], 4))
        price_b = float(round(df_b["close"].iloc[-1], 4))

        # Hedge ratio and spread (strictly historical)
        hedge_ratio = 1.0
        spread = 0.0
        spread_z_score = 0.0
        lookback = 30
        if len(df_a) >= lookback and len(df_b) >= lookback:
            s_a = df_a["close"].iloc[-lookback:]
            s_b = df_b["close"].iloc[-lookback:]
            var_b = float(s_b.var())
            if var_b > 1e-8:
                cov = float(s_a.cov(s_b))
                hedge_ratio = float(cov / var_b)
            spread_series = s_a - (hedge_ratio * s_b)
            spread = float(spread_series.iloc[-1])
            std_sp = float(spread_series.std())
            mean_sp = float(spread_series.mean())
            if std_sp > 1e-8:
                spread_z_score = float((spread - mean_sp) / std_sp)

        pos_a = portfolio.get_position(sym_a) if portfolio else None
        pos_b = portfolio.get_position(sym_b) if portfolio else None

        pairs_info = {
            "symbol_a": sym_a,
            "symbol_b": sym_b,
            "price_a": price_a,
            "price_b": price_b,
            "hedge_ratio": round(hedge_ratio, 4),
            "spread": round(spread, 4),
            "spread_z_score": round(spread_z_score, 4),
            "position_a": pos_a.quantity if pos_a else 0,
            "position_b": pos_b.quantity if pos_b else 0,
        }
        df_main = primary_df
    else:
        df_main = historical_slice
        last_row = df_main.iloc[-1]
        timestamp = str(last_row["timestamp"])
        pairs_info = None

    # Base indicators on current evaluated symbol
    close = df_main["close"]
    current_price = float(round(close.iloc[-1], 4))
    recent_return = float(round((close.iloc[-1] / close.iloc[-2] - 1.0), 6)) if len(close) >= 2 else 0.0
    volatility = float(round(close.pct_change().iloc[-20:].std() * np.sqrt(252), 4)) if len(close) >= 20 else 0.0
    volume = float(last_row.get("volume", 0.0))

    sma_10 = float(round(close.iloc[-10:].mean(), 4)) if len(close) >= 10 else current_price
    sma_30 = float(round(close.iloc[-30:].mean(), 4)) if len(close) >= 30 else current_price
    ema_12 = float(round(close.ewm(span=12, adjust=False).mean().iloc[-1], 4))
    ema_26 = float(round(close.ewm(span=26, adjust=False).mean().iloc[-1], 4))
    rsi = compute_rsi(close, period=14)
    macd = compute_macd(close)
    atr = compute_atr(df_main, period=14)

    # Portfolio state
    pos = portfolio.get_position(symbol) if portfolio else None
    position_qty = pos.quantity if pos else 0
    pos_entry = round(pos.avg_entry_price, 4) if pos else 0.0
    pos_unrealized_pnl = round(pos.unrealized_pnl(current_price), 2) if pos else 0.0
    available_cash = round(portfolio.cash, 2) if portfolio else 0.0
    portfolio_equity = round(portfolio.get_total_equity(current_prices={symbol: current_price}), 2) if portfolio else 0.0
    exposure_pct = round((abs(position_qty) * current_price) / portfolio_equity, 4) if portfolio_equity > 0 else 0.0

    # Strategy signals
    active_signals = []
    if signals:
        for s in signals:
            active_signals.append({
                "symbol": s.symbol,
                "type": s.signal_type.value if hasattr(s.signal_type, "value") else str(s.signal_type),
                "strength": s.strength,
                "stop_loss": s.stop_loss_price,
            })

    context: Dict[str, Any] = {
        "symbol": symbol,
        "timestamp": timestamp,
        "price": current_price,
        "recent_return": recent_return,
        "volatility": volatility,
        "volume": volume,
        "sma_10": sma_10,
        "sma_30": sma_30,
        "ema_12": ema_12,
        "ema_26": ema_26,
        "rsi_14": rsi,
        "macd": macd,
        "atr_14": atr,
        "position": {
            "quantity": position_qty,
            "entry_price": pos_entry,
            "unrealized_pnl": pos_unrealized_pnl,
        },
        "portfolio": {
            "cash": available_cash,
            "equity": portfolio_equity,
            "exposure_pct": exposure_pct,
        },
        "strategy_signals": active_signals,
    }

    if pairs_info:
        context["pairs_trading"] = pairs_info

    if metadata:
        context["metadata"] = metadata

    return context
