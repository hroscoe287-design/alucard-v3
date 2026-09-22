# ALUCARD V4 CLEAN BUILD — deterministic technical analysis
"""ALUCARD V4 market-data and technical-analysis core.

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



def alligator(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bill Williams Alligator using SMMA-style smoothing and 13/8/5 periods."""
    median = (frame["high"] + frame["low"]) / 2.0

    def smma(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    jaw = smma(median, 13).shift(8)
    teeth = smma(median, 8).shift(5)
    lips = smma(median, 5).shift(3)
    return jaw, teeth, lips


def fractals(frame: pd.DataFrame, radius: int = 2) -> tuple[pd.Series, pd.Series]:
    """Bill Williams fractal confirmation with configurable radius=2."""
    window = radius * 2 + 1
    high_roll = frame["high"].rolling(window, center=True).max()
    low_roll = frame["low"].rolling(window, center=True).min()
    up = frame["high"].eq(high_roll).fillna(False)
    down = frame["low"].eq(low_roll).fillna(False)
    return up, down


def psar(frame: pd.DataFrame, step: float = 0.02, maximum: float = 0.20) -> pd.Series:
    """Parabolic SAR with an internal implementation independent of TA libs."""
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    out = np.full(len(frame), np.nan)
    if len(frame) == 0:
        return pd.Series(out, index=frame.index)

    rising = True
    sar = low[0]
    extreme = high[0]
    af = step
    out[0] = sar

    for i in range(1, len(frame)):
        sar = sar + af * (extreme - sar)

        if rising:
            sar = min(sar, low[i - 1], low[i - 2] if i > 1 else low[i - 1])
            if low[i] < sar:
                rising = False
                sar = extreme
                extreme = low[i]
                af = step
            elif high[i] > extreme:
                extreme = high[i]
                af = min(maximum, af + step)
        else:
            sar = max(sar, high[i - 1], high[i - 2] if i > 1 else high[i - 1])
            if high[i] > sar:
                rising = True
                sar = extreme
                extreme = high[i]
                af = step
            elif low[i] < extreme:
                extreme = low[i]
                af = min(maximum, af + step)

        out[i] = sar

    return pd.Series(out, index=frame.index)


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
    jaw, teeth, lips = alligator(frame)
    psar_line = psar(frame, 0.02, 0.20)
    fractal_up, fractal_down = fractals(frame, radius=2)

    latest = lambda series: None if series.empty or pd.isna(series.iloc[-1]) else float(series.iloc[-1])

    confirmed_up = bool(fractal_up.iloc[:-2].tail(5).any()) if len(frame) > 7 else False
    confirmed_down = bool(fractal_down.iloc[:-2].tail(5).any()) if len(frame) > 7 else False

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
        "alligator_jaw": latest(jaw),
        "alligator_teeth": latest(teeth),
        "alligator_lips": latest(lips),
        "psar": latest(psar_line),
        "fractal_up": 1.0 if confirmed_up else 0.0,
        "fractal_down": 1.0 if confirmed_down else 0.0,
    }


def generate_signal(frame: pd.DataFrame, minimum_candles: int = 60) -> Signal:
    """Weighted live confluence: Alligator + MA + PSAR + Fractal(2) + momentum."""
    if len(frame) < minimum_candles:
        return Signal("WAIT", 0.0, [f"Need at least {minimum_candles} candles"], {})

    values = compute_indicators(frame)
    required = (
        "price", "ema9", "ema20", "ema50", "rsi14", "macd_hist",
        "cci20", "adx14", "plus_di", "minus_di", "stoch_k", "stoch_d",
        "alligator_jaw", "alligator_teeth", "alligator_lips", "psar",
    )
    if any(values.get(k) is None for k in required):
        return Signal("WAIT", 0.0, ["Indicators are not ready"], values)

    price = values["price"]
    e9, e20, e50 = values["ema9"], values["ema20"], values["ema50"]
    rsi14 = values["rsi14"]
    macd_hist = values["macd_hist"]
    cci20 = values["cci20"]
    adx14 = values["adx14"]
    plus_di, minus_di = values["plus_di"], values["minus_di"]
    stoch_k, stoch_d = values["stoch_k"], values["stoch_d"]
    jaw, teeth, lips = values["alligator_jaw"], values["alligator_teeth"], values["alligator_lips"]
    sar = values["psar"]

    bullish = 0.0
    bearish = 0.0
    reasons: list[str] = []
    total = 0.0

    def add(weight: float, bull: bool, bear: bool, bull_text: str, bear_text: str) -> None:
        nonlocal bullish, bearish, total
        total += weight
        if bull and not bear:
            bullish += weight
            reasons.append(bull_text)
        elif bear and not bull:
            bearish += weight
            reasons.append(bear_text)

    add(1.50, e9 > e20 > e50, e9 < e20 < e50,
        "EMA 9/20/50 stack bullish", "EMA 9/20/50 stack bearish")
    add(1.60, lips > teeth > jaw, lips < teeth < jaw,
        "Alligator lines aligned bullish", "Alligator lines aligned bearish")
    add(1.30, price > sar, price < sar,
        "Price is above Parabolic SAR", "Price is below Parabolic SAR")
    add(1.10, macd_hist > 0, macd_hist < 0,
        "MACD histogram positive", "MACD histogram negative")
    add(0.90, cci20 > 0, cci20 < 0,
        "CCI momentum positive", "CCI momentum negative")
    add(0.80, 50 <= rsi14 <= 72, 28 <= rsi14 < 50,
        "RSI supports bullish momentum", "RSI supports bearish momentum")
    add(1.00, adx14 >= 20 and plus_di > minus_di, adx14 >= 20 and minus_di > plus_di,
        "ADX confirms bullish directional strength", "ADX confirms bearish directional strength")
    add(0.65, stoch_k > stoch_d and stoch_k < 85, stoch_k < stoch_d and stoch_k > 15,
        "Stochastic momentum rising", "Stochastic momentum falling")

    fractal_bull = values["fractal_up"] > 0 and price > float(frame["high"].iloc[-2])
    fractal_bear = values["fractal_down"] > 0 and price < float(frame["low"].iloc[-2])
    add(0.75, fractal_bull, fractal_bear,
        "Confirmed Fractal(2) supports upside break",
        "Confirmed Fractal(2) supports downside break")

    if total <= 0:
        return Signal("WAIT", 0.0, ["No usable indicator evidence"], values)

    bull_pct = bullish / total * 100.0
    bear_pct = bearish / total * 100.0
    edge = abs(bull_pct - bear_pct)
    confidence = min(99.0, max(bull_pct, bear_pct))

    if bullish > bearish and bull_pct >= 64.0 and edge >= 18.0:
        direction = "CALL"
    elif bearish > bullish and bear_pct >= 64.0 and edge >= 18.0:
        direction = "PUT"
    else:
        direction = "WAIT"
        confidence = min(confidence, 59.0)
        reasons.append("Confluence threshold not met; waiting for confirmation")

    return Signal(direction, round(confidence, 1), reasons, values)
