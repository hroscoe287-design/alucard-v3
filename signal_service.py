"""Live signal orchestration for ALUCARD V3."""

from __future__ import annotations

import os
import threading
import time

from market_engine import generate_signal
from market_state import MarketState
from pocket_adapter import PocketOptionAdapter

PERIODS = {
    "5s": 5, "15s": 15, "30s": 30, "1m": 60, "2m": 120,
    "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


class SignalService:
    def __init__(self):
        self.state = MarketState()
        self.asset = os.getenv("POCKET_ASSET", "EURUSD_otc")
        self.timeframe = os.getenv("POCKET_TIMEFRAME", "1m")
        self.period = PERIODS.get(self.timeframe, 60)
        self.adapter = PocketOptionAdapter(self._on_candle)
        self.thread: threading.Thread | None = None
        self.started = False
        self.error = ""

    def start(self) -> None:
        if self.started or not self.adapter.configured:
            return
        self.adapter.subscribe(self.asset, self.period)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.started = True

    def _run(self) -> None:
        try:
            self.adapter.connect()
        except Exception as exc:
            self.error = str(exc)[:200]
            self.started = False
        finally:
            # Surface only the adapter's safe diagnostic label.
            if self.adapter.last_error:
                self.error = self.adapter.last_error
            self.started = False

    def _on_candle(self, asset, candle) -> None:
        period = self.period
        self.state.add_candle(asset, period, candle)
        candles = self.state.get_candles(asset, period)
        signal = generate_signal(candles)
        self.state.set_signal(asset, period, signal)

    def snapshot(self) -> dict:
        snap = self.state.snapshot(self.asset, self.period)
        signal = snap.get("signal")
        if signal:
            snap["signal"] = {
                "direction": signal.direction,
                "confidence": signal.confidence,
                "reasons": signal.reasons,
                "indicators": signal.indicators,
            }
        snap["configured"] = self.adapter.configured
        snap["connected"] = self.adapter.connected
        if self.adapter.last_error:
            self.error = self.adapter.last_error
        snap["error"] = self.error or (
            "Pocket Option credentials are not configured"
            if not self.adapter.configured else
            "Connecting to Pocket Option WebSocket"
        )
        snap["engine"] = "LIVE" if signal else "WAITING_FOR_DATA"
        return snap


service = SignalService()
