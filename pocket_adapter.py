"""ALUCARD V3 Pocket Option WebSocket adapter.

Uses the browser-observed Socket.IO/Engine.IO v4 flow:
open -> Engine.IO connect -> Socket.IO connect -> auth -> history subscription.
Credentials are read only from environment variables and are never logged.
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
    "wss://api-us-south.po.market/socket.io/?EIO=4&transport=websocket",
)
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
        self.last_error = ""
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._subscriptions: set[tuple[str, int]] = set()
        self._candle_buffers = defaultdict(dict)
        self._socket_ready = False
        self._auth_sent = False

    @property
    def configured(self) -> bool:
        return bool(POCKET_SESSION.strip() and POCKET_UID.strip())

    def connect(self) -> None:
        if not self.configured:
            raise RuntimeError("Pocket Option credentials are not configured")

        while not self._stop.is_set():
            self._socket_ready = False
            self._auth_sent = False
            self.connected = False

            self.ws = websocket.WebSocketApp(
                POCKET_WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            try:
                self.ws.run_forever(
                    ping_interval=20,
                    ping_timeout=10,
                    origin="https://pocketoption.com",
                )
            except Exception as exc:
                self.last_error = f"WebSocket: {type(exc).__name__}"

            self.connected = False
            self._socket_ready = False
            if self._stop.wait(3):
                break

    def stop(self) -> None:
        self._stop.set()
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass

    def subscribe(self, asset: str, period: int) -> None:
        self._subscriptions.add((asset, period))
        if self._socket_ready and self._auth_sent:
            self._send_subscription(asset, period)

    def _on_open(self, ws) -> None:
        self.last_error = ""
        # Engine.IO/Socket.IO handshake: wait for the server's Socket.IO
        # connect acknowledgement before sending application auth.
        self._send("40")

    def _send_auth(self) -> None:
        if self._auth_sent:
            return
        try:
            uid = int(POCKET_UID)
            demo = int(POCKET_DEMO)
            platform = int(POCKET_PLATFORM)
        except ValueError as exc:
            self.last_error = "Invalid Pocket Option numeric configuration"
            raise RuntimeError("Invalid Pocket Option numeric configuration") from exc

        auth = {
            "session": POCKET_SESSION,
            "isDemo": demo,
            "uid": uid,
            "platform": platform,
            "isFastHistory": True,
            "isOptimized": True,
        }
        self._send("42" + json.dumps(["auth", auth], separators=(",", ":")))
        self._auth_sent = True

        # Give the server a short turn to process auth before requesting data.
        time.sleep(0.35)
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

        if not isinstance(message, str):
            return

        # Engine.IO ping/pong.
        if message == "2":
            self._send("3")
            return

        # Socket.IO namespace connection acknowledgement.
        if message == "40" or message.startswith("40"):
            self._socket_ready = True
            try:
                self._send_auth()
            except Exception:
                self.connected = False
            return

        # Some servers may send an auth acknowledgement as a Socket.IO event.
        if message.startswith("42"):
            try:
                packet = json.loads(message[2:])
            except (TypeError, ValueError, json.JSONDecodeError):
                return

            if not isinstance(packet, list) or len(packet) < 2:
                return

            event, payload = packet[0], packet[1]

            if event in {"auth", "authenticated", "success", "authorization"}:
                self.connected = True
                return

            if event in {"updateHistoryNewFast", "updateStream", "history"}:
                self.connected = True
                self._consume_payload(payload)

    def _consume_payload(self, payload) -> None:
        if isinstance(payload, dict):
            asset = payload.get("asset") or payload.get("symbol")
            candles = (
                payload.get("candles")
                or payload.get("history")
                or payload.get("data")
            )
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
            # History payloads sometimes arrive as [asset, candles].
            if len(payload) == 2 and isinstance(payload[0], str) and isinstance(payload[1], list):
                asset = payload[0]
                for item in payload[1]:
                    candle = self._normalize_candle(item)
                    if candle:
                        self._emit(asset, candle)
                return

            for item in payload:
                if not isinstance(item, dict):
                    continue
                candle = self._normalize_candle(item)
                if candle:
                    asset = item.get("asset") or item.get("symbol")
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
        # Never log the exception itself because a library error could contain
        # request headers or connection details. Keep only a safe type label.
        self.connected = False
        self.last_error = f"WebSocket error: {type(error).__name__}"

    def _on_close(self, ws, code, reason) -> None:
        self.connected = False
        self._socket_ready = False
