# ALUCARD V3 CLEAN BUILD — signal orchestration
"""Live signal orchestration for ALUCARD V3."""

from __future__ import annotations

import os
import threading
import time

from market_engine import generate_signal
from market_state import MarketState
from pocket_adapter import PocketOptionAdapter

PERIODS = {
    "5s": 5, "10s": 10, "15s": 15, "30s": 30,
    "1m": 60, "2m": 120, "3m": 180, "5m": 300,
    "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400,
    "1d": 86400, "1w": 604800, "1mo": 2592000,
}


class SignalService:
    PERIODS = PERIODS

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
        if self.started:
            return
        if not self.adapter.configured:
            self.error = "Pocket Option credentials are not configured"
            print("ALUCARD connector not started: Pocket Option credentials are not configured", flush=True)
            return

        self.adapter.subscribe(self.asset, self.period)
        self.started = True
        self.error = ""
        print(
            f"ALUCARD starting market connector asset={self.asset} timeframe={self.timeframe}",
            flush=True,
        )
        self.thread = threading.Thread(
            target=self._run,
            name="alucard-pocket-connector",
            daemon=True,
        )
        self.thread.start()

    def configure(self, asset: str, timeframe: str) -> None:
        self.asset = asset
        self.timeframe = timeframe
        self.period = PERIODS[timeframe]
        if self.adapter.connected:
            self.adapter.subscribe(asset, self.period)
        else:
            self.start()

    def _run(self) -> None:
        try:
            self.adapter.connect()
        except Exception as exc:
            self.error = str(exc)[:200]
            print(f"ALUCARD connector exception: {type(exc).__name__}", flush=True)
        finally:
            if self.adapter.last_error:
                self.error = self.adapter.last_error
            self.started = False
            print(
                f"ALUCARD connector stopped stage={self.adapter.connection_stage}",
                flush=True,
            )

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
        snap["candle_data"] = [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in self.state.get_candles(self.asset, self.period)[-120:]
        ]
        snap["configured"] = self.adapter.configured
        snap["connected"] = self.adapter.connected
        snap["connection_stage"] = self.adapter.connection_stage
        if self.adapter.last_error:
            self.error = self.adapter.last_error
        snap["error"] = self.error or (
            "Pocket Option credentials are not configured"
            if not self.adapter.configured else
            "Connecting to Pocket Option WebSocket"
        )
        snap["engine"] = "LIVE" if signal else ("STARTING" if self.started else "WAITING_FOR_DATA")
        return snap


service = SignalService()


def _autostart() -> None:
    # Start outside the import path so Gunicorn can finish booting immediately.
    time.sleep(0.25)
    service.start()


threading.Thread(
    target=_autostart,
    name="alucard-pocket-autostart",
    daemon=True,
).start()
