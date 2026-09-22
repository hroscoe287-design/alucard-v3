# ALUCARD V3 CLEAN BUILD — thread-safe market state
"""Thread-safe live market state for ALUCARD V3."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import RLock
from time import time

from market_engine import Candle, Signal


class MarketState:
    def __init__(self, max_candles: int = 500):
        self._lock = RLock()
        self._max_candles = max_candles
        self._candles = defaultdict(lambda: deque(maxlen=max_candles))
        self._signals: dict[tuple[str, int], Signal] = {}
        self._last_update: dict[tuple[str, int], float] = {}

    def add_candle(self, asset: str, period: int, candle: Candle) -> None:
        key = (asset, period)
        with self._lock:
            candles = self._candles[key]
            if candles and candle.timestamp < candles[-1].timestamp:
                return
            if candles and candle.timestamp == candles[-1].timestamp:
                candles[-1] = candle
            else:
                candles.append(candle)
            self._last_update[key] = time()

    def get_candles(self, asset: str, period: int) -> list[Candle]:
        with self._lock:
            return list(self._candles[(asset, period)])

    def set_signal(self, asset: str, period: int, signal: Signal) -> None:
        with self._lock:
            self._signals[(asset, period)] = signal

    def get_signal(self, asset: str, period: int) -> Signal | None:
        with self._lock:
            return self._signals.get((asset, period))

    def snapshot(self, asset: str, period: int) -> dict:
        key = (asset, period)
        with self._lock:
            candles = list(self._candles[key])
            signal = self._signals.get(key)
            updated = self._last_update.get(key, 0.0)

        return {
            "asset": asset,
            "period": period,
            "candles": len(candles),
            "last_update": updated,
            "stale_seconds": max(0.0, time() - updated) if updated else None,
            "signal": signal,
        }
