"""ALUCARD V3 Pocket Option WebSocket adapter.

This adapter expects a valid Pocket Option browser session supplied through
environment variables. Credentials are never logged or returned by this code.
The wire format is Socket.IO Engine.IO v4; market messages are normalized into
Candle objects for the analysis engine.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from typing import Callable

import websocket

from market_engine import Candle


POCKET_WS_URL = os.getenv(
    "POCKET_WS_URL",
    "wss://api-spb.po.market/socket.io/?EIO=4&transport=websocket",
)

# Session/auth data must be supplied at runtime. Never commit it to GitHub.
POCKET_SESSION = os.getenv("POCKET_SESSION", "")
POCKET_UID = os.getenv("POCKET_UID", "")
POCKET_DEMO = os.getenv("POCKET_DEMO", "0")
POCKET_PLATFORM = os.getenv("POCKET_PLATFORM", "9")


class PocketOptionAdapter:
    def __init__(self, on_candle: Callable[[str, Candle], None] | None = None):
        self.on_candle = on_candle
        self.ws = None
        self.connected = False
        self.last_message_at = 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._subscriptions: set[tuple[str, int]] = set()
        self._candle_buffers = defaultdict(dict)

    @property
    def configured(self) -> bool:
        return bool(POCKET_SESSION and POCKET_UID)

    def connect(self) -> None:
        if not self.configured:
            raise RuntimeError("Pocket Option credentials are not configured")

        self.ws = websocket.WebSocketApp(
            POCKET_WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.ws.run_forever(
            ping_interval=20,
            ping_timeout=10,
            origin="https://pocketoption.com",
        )

    def stop(self) -> None:
        self._stop.set()
        if self.ws:
            self.ws.close()

    def subscribe(self, asset: str, period: int) -> None:
        self._subscriptions.add((asset, period))
        if self.connected:
            self._send_subscription(asset, period)

    def _on_open(self, ws) -> None:
        self.connected = True
        self._send("40")
        # Socket.IO auth is sent after the Engine.IO/Socket.IO handshake.
        auth = {
            "session": POCKET_SESSION,
            "isDemo": int(POCKET_DEMO),
            "uid": int(POCKET_UID),
            "platform": int(POCKET_PLATFORM),
            "isFastHistory": True,
            "isOptimized": True,
        }
        self._send("42" + json.dumps(["auth", auth], separators=(",", ":")))
        time.sleep(0.25)
        for asset, period in list(self._subscriptions):
            self._send_subscription(asset, period)

    def _send_subscription(self, asset: str, period: int) -> None:
        now = int(time.time())
        payload = [
            "loadHistoryPeriod",
            {
                "asset": asset,
                "index": now,
                "time": now - 9000,
                "offset": 9000,
                "period": period,
            },
        ]
        self._send("42" + json.dumps(payload, separators=(",", ":")))

    def _send(self, message: str) -> None:
        if self.ws:
            with self._lock:
                self.ws.send(message)

    def _on_message(self, ws, message) -> None:
        self.last_message_at = time.time()
        # Initial V3 adapter accepts JSON Socket.IO messages first.
        # Binary/native price payloads are intentionally isolated so that
        # protocol changes cannot corrupt the candle engine.
        if not isinstance(message, str):
            return

        if not message.startswith("42"):
            return

        try:
            packet = json.loads(message[2:])
        except (TypeError, ValueError, json.JSONDecodeError):
            return

        if not isinstance(packet, list) or len(packet) < 2:
            return

        event, payload = packet[0], packet[1]
        if event not in {"updateHistoryNewFast", "updateStream", "history"}:
            return

        self._consume_payload(payload)

    def _consume_payload(self, payload) -> None:
        if isinstance(payload, dict):
            asset = payload.get("asset") or payload.get("symbol")
            candles = payload.get("candles") or payload.get("history") or payload.get("data")
            if asset and isinstance(candles, list):
                for item in candles:
                    candle = self._normalize_candle(item)
                    if candle:
                        self._emit(asset, candle)
            else:
                candle = self._normalize_candle(payload)
                if candle and asset:
                    self._emit(asset, candle)

        elif isinstance(payload, list):
            for item in payload:
                candle = self._normalize_candle(item)
                if candle:
                    asset = getattr(item, "asset", None) if not isinstance(item, dict) else item.get("asset")
                    if asset:
                        self._emit(asset, candle)

    @staticmethod
    def _normalize_candle(item) -> Candle | None:
        if not isinstance(item, dict):
            return None

        try:
            ts = int(item.get("timestamp", item.get("time", item.get("t"))))
            o = float(item.get("open", item.get("o")))
            h = float(item.get("high", item.get("h")))
            l = float(item.get("low", item.get("l")))
            c = float(item.get("close", item.get("c", item.get("price"))))
            v = float(item.get("volume", item.get("v", 0.0)))
        except (TypeError, ValueError):
            return None

        if ts > 10_000_000_000:
            ts //= 1000
        if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c) or h < l:
            return None

        return Candle(ts, o, h, l, c, v)

    def _emit(self, asset: str, candle: Candle) -> None:
        if self.on_candle:
            self.on_candle(asset, candle)

    def _on_error(self, ws, error) -> None:
        self.connected = False

    def _on_close(self, ws, code, reason) -> None:
        self.connected = False
