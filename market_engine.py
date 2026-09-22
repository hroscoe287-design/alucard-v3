# ALUCARD V3 CLEAN BUILD — deterministic technical analysis
"""ALUCARD V3 market-data and technical-analysis core.

This module is deliberately independent of the legacy ALUCARD V2 code.
It consumes normalized OHLC candles and produces deterministic indicators
and a transparent CALL/PUT/WAIT assessment. It does not place trades.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
import math

import numpy as np
import pandas as pd


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Signal:
    direction: str
    confidence: float
    reasons: list[str]
    indicators: dict[str, float | None]


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    rows = [asdict(c) for c in candles]
    frame = pd.DataFrame(rows).sort_values("timestamp")
    frame = frame.drop_duplicates("timestamp", keep="last")
    frame = frame.set_index("timestamp")
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = ema(series, 12)
    slow = ema(series, 26)
    line = fast - slow
    signal = line.ewm(span=9, adjust=False, min_periods=9).mean()
    histogram = line - signal
    return line, signal, histogram


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def cci(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    mean = typical.rolling(period, min_periods=period).mean()
    deviation = typical.rolling(period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (typical - mean) / (0.015 * deviation.replace(0, np.nan))


def adx(frame: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    previous_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_value = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_value
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_value
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_value = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return adx_value, plus_di, minus_di


def bollinger(series: pd.Series, period: int = 20, deviations: float = 2.0):
    middle = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std(ddof=0)
    return middle, middle + deviations * std, middle - deviations * std


def stochastic(frame: pd.DataFrame, period: int = 14, smooth: int = 3):
    low = frame["low"].rolling(period, min_periods=period).min()
    high = frame["high"].rolling(period, min_periods=period).max()
    k = 100 * (frame["close"] - low) / (high - low).replace(0, np.nan)
    d = k.rolling(smooth, min_periods=smooth).mean()
    return k, d


def compute_indicators(frame: pd.DataFrame) -> dict[str, float | None]:
    if frame.empty:
        return {}

    close = frame["close"]
    e9 = ema(close, 9)
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    macd_line, macd_signal, macd_hist = macd(close)
    adx_line, plus_di, minus_di = adx(frame)
    bb_mid, bb_upper, bb_lower = bollinger(close)
    stoch_k, stoch_d = stochastic(frame)

    latest = lambda series: None if series.empty or pd.isna(series.iloc[-1]) else float(series.iloc[-1])

    return {
        "price": latest(close),
        "ema9": latest(e9),
        "ema20": latest(e20),
        "ema50": latest(e50),
        "rsi14": latest(rsi(close)),
        "macd": latest(macd_line),
        "macd_signal": latest(macd_signal),
        "macd_hist": latest(macd_hist),
        "cci20": latest(cci(frame)),
        "atr14": latest(atr(frame)),
        "adx14": latest(adx_line),
        "plus_di": latest(plus_di),
        "minus_di": latest(minus_di),
        "bb_middle": latest(bb_mid),
        "bb_upper": latest(bb_upper),
        "bb_lower": latest(bb_lower),
        "stoch_k": latest(stoch_k),
        "stoch_d": latest(stoch_d),
    }


def generate_signal(frame: pd.DataFrame, minimum_candles: int = 60) -> Signal:
    if len(frame) < minimum_candles:
        return Signal("WAIT", 0.0, [f"Need at least {minimum_candles} candles"], {})

    values = compute_indicators(frame)
    score = 0.0
    reasons: list[str] = []

    price = values.get("price")
    e9, e20, e50 = values.get("ema9"), values.get("ema20"), values.get("ema50")
    r = values.get("rsi14")
    mh = values.get("macd_hist")
    c = values.get("cci20")
    a = values.get("adx14")
    pk, pdv = values.get("plus_di"), values.get("minus_di")
    sk, sd = values.get("stoch_k"), values.get("stoch_d")

    if None in (price, e9, e20, e50, r, mh, c, a, pk, pdv, sk, sd):
        return Signal("WAIT", 0.0, ["Indicators are not ready"], values)

    if e9 > e20 > e50:
        score += 2
        reasons.append("EMA trend aligned bullish")
    elif e9 < e20 < e50:
        score -= 2
        reasons.append("EMA trend aligned bearish")

    if mh > 0:
        score += 1
        reasons.append("MACD histogram positive")
    elif mh < 0:
        score -= 1
        reasons.append("MACD histogram negative")

    if 50 <= r <= 70:
        score += 1
        reasons.append("RSI supports bullish momentum")
    elif 30 <= r < 50:
        score -= 1
        reasons.append("RSI supports bearish momentum")

    if c > 0:
        score += 1
    elif c < 0:
        score -= 1

    if a >= 20:
        if pk > pdv:
            score += 1
            reasons.append("ADX confirms directional strength")
        elif pdv > pk:
            score -= 1
            reasons.append("ADX confirms bearish directional strength")

    if sk > sd and sk < 80:
        score += 1
    elif sk < sd and sk > 20:
        score -= 1

    max_score = 7.0
    confidence = min(99.0, max(0.0, 50.0 + abs(score) / max_score * 45.0))

    if score >= 3:
        direction = "CALL"
    elif score <= -3:
        direction = "PUT"
    else:
        direction = "WAIT"
        confidence = min(confidence, 59.0)
        reasons.append("Evidence is mixed; no directional signal")

    return Signal(direction, round(confidence, 1), reasons, values)
