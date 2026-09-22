"""ALUCARD V3 Pocket Option WebSocket adapter.

Uses the browser-observed Socket.IO/Engine.IO v4 flow:
open -> Engine.IO connect -> Socket.IO connect -> auth -> history subscription.
Credentials are read only from environment variables and are never logged.
"""

from __future__ import annotations

import json
import os
import struct
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
# Real-account clusters vary by region. If the configured cluster cannot be
# reached from the Render region, try other known real clusters.
POCKET_WS_FALLBACKS = [
    "wss://api-us-north.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-eu.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-spb.po.market/socket.io/?EIO=4&transport=websocket",
    "wss://api-msk.po.market/socket.io/?EIO=4&transport=websocket",
]
def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default

POCKET_SESSION = _first_env(
    "POCKET_SESSION", "PO_SSID", "POCKET_OPTION_SSID",
    "POCKET_OPTION_SESSION", "PO_SESSION", "PO_SSID_TOKEN",
    "PO_TOKEN", "SSID",
)
POCKET_UID = _first_env(
    "POCKET_UID", "PO_UID", "POCKET_OPTION_UID", "UID", "USER_ID",
)
POCKET_DEMO = _first_env("POCKET_DEMO", "PO_IS_DEMO", default="0")
POCKET_PLATFORM = _first_env("POCKET_PLATFORM", "PO_PLATFORM", default="2")


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
        self.connection_stage = "idle"
        self._pending_binary_event = None
        self._auth_event = threading.Event()
        self._tick_bars = {}

    @property
    def configured(self) -> bool:
        return bool(POCKET_SESSION.strip() and POCKET_UID.strip())

    def connect(self) -> None:
        if not self.configured:
            raise RuntimeError("Pocket Option credentials are not configured")

        print(
            f"ALUCARD Pocket Option connector starting "
            f"(session_configured={bool(POCKET_SESSION)}, uid_configured={bool(POCKET_UID)})",
            flush=True,
        )

        urls = [POCKET_WS_URL] + [u for u in POCKET_WS_FALLBACKS if u != POCKET_WS_URL]

        while not self._stop.is_set():
            connected_this_round = False

            for url in urls:
                if self._stop.is_set():
                    break

                self._socket_ready = False
                self._auth_sent = False
                self._auth_event.clear()
                self.connected = False
                host = url.split("/", 3)[2] if "://" in url else "unknown"
                self.connection_stage = f"opening:{host}"
                print(f"ALUCARD Pocket Option trying {host}", flush=True)

                self.ws = websocket.WebSocketApp(
                    url,
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
                        http_no_proxy=["*"],
                        http_proxy_timeout=15,
                    )
                except Exception as exc:
                    self.last_error = f"WebSocket: {type(exc).__name__}"
                    self.connection_stage = "run_forever_error"

                if self.connected or self._socket_ready:
                    connected_this_round = True
                    break

                self.connected = False
                self._socket_ready = False

            if connected_this_round:
                if self._stop.wait(3):
                    break
            elif self._stop.wait(2):
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
        self.connection_stage = "transport_open"
        # Engine.IO sends the initial 0{...} OPEN packet first. The client
        # must answer with Socket.IO 40; sending 40 from on_open races the
        # Engine.IO handshake and can cause the server to close the socket.
        self.connection_stage = "waiting_engineio_open"

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
        self.connection_stage = "auth_sent"
        self._send("42" + json.dumps(["auth", auth], separators=(",", ":")))
        self._auth_sent = True
        self.connection_stage = "waiting_for_auth"

    def _send_subscription(self, asset: str, period: int) -> None:
        now = int(time.time())
        # Pocket Option history requests use a unique index in centiseconds,
        # while the range end time is normal Unix seconds.
        request_index = int(time.time() * 100)
        # Pocket Option clients use changeSymbol/subfor for the live stream
        # and loadHistoryPeriod for the initial candle history.
        self._send("42" + json.dumps(
            ["changeSymbol", {"asset": asset, "period": period}],
            separators=(",", ":"),
        ))
        self._send("42" + json.dumps(
            ["subscribeSymbol", {"asset": asset}],
            separators=(",", ":"),
        ))
        self._send("42" + json.dumps(
            ["subfor", asset],
            separators=(",", ":"),
        ))
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

        # Socket.IO binary attachment: the preceding 451- packet names the
        # event and this frame contains the JSON payload.
        if isinstance(message, (bytes, bytearray)):
            event = self._pending_binary_event
            self._pending_binary_event = None
            raw = bytes(message)
            if event:
                try:
                    try:
                        decoded = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                        decoded = None
                    self.connected = True
                    self.connection_stage = "market_data_received"
                    if event == "successauth":
                        self.connection_stage = "authenticated"
                        for asset, period in list(self._subscriptions):
                            self._send_subscription(asset, period)
                    elif decoded is not None:
                        self._consume_payload(decoded, default_asset=self._current_asset())
                    elif event == "updateStream":
                        self._consume_binary_tick(raw)
                except Exception:
                    pass
            elif len(raw) == 39:
                self._consume_binary_tick(raw)
            return

        if not isinstance(message, str):
            return

        # Engine.IO OPEN packet. A Socket.IO namespace connection packet must
        # not be sent until the Engine.IO transport has opened.
        if message.startswith("0"):
            self.connection_stage = "engineio_open"
            self._send("40")
            self.connection_stage = "socketio_connect_sent"
            return

        # Engine.IO ping/pong.
        if message == "2":
            self._send("3")
            return

        # Socket.IO namespace connection acknowledgement.
        if message == "40" or message.startswith("40"):
            self._socket_ready = True
            self.connection_stage = "socketio_ready"
            try:
                self._send_auth()
            except Exception:
                self.connected = False
            return

        # Pocket Option commonly uses 41 / NotAuthorized for rejected auth.
        if message == "41" or "NotAuthorized" in message:
            self.connected = False
            self.connection_stage = "auth_error"
            self.last_error = "Pocket Option authorization rejected"
            return

        # Pocket Option can return binary-event envelopes such as
        # 451-["updateStream",...] and 451-["loadHistoryPeriodFast",...].
        if message.startswith("451-"):
            try:
                raw = json.loads(message[4:])
                if isinstance(raw, list) and raw:
                    event = raw[0]
                    if event == "successauth":
                        self.connected = True
                        self.connection_stage = "authenticated"
                        self._auth_event.set()
                        for asset, period in list(self._subscriptions):
                            self._send_subscription(asset, period)
                        return
                    if event in {"loadHistoryPeriodFast", "updateHistoryNewFast", "updateStream", "history"}:
                        self._pending_binary_event = event
                        self.connected = True
                        self.connection_stage = "market_data_received"
                        # The actual payload arrives as the next WebSocket
                        # binary frame; do not discard it.
                        return
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
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

            if event in {"successauth", "auth", "authenticated", "success", "authorization"}:
                self.connected = True
                self.connection_stage = "authenticated"
                self._auth_event.set()
                for asset, period in list(self._subscriptions):
                    self._send_subscription(asset, period)
                return

            if event in {"loadHistoryPeriodFast", "updateHistoryNewFast", "updateStream", "history"}:
                self.connected = True
                self.connection_stage = "market_data_received"
                self._consume_payload(payload)
                return

            # Socket.IO CONNECT_ERROR packets are encoded as 44...
            if event == "connect_error":
                self.connected = False
                self.connection_stage = "auth_error"
                self.last_error = "Pocket Option authorization rejected"

    def _current_asset(self) -> str | None:
        return next(iter(self._subscriptions), (None, 0))[0]

    def _consume_tick(self, asset: str, timestamp, price) -> None:
        try:
            timestamp = int(float(timestamp))
            price = float(price)
        except (TypeError, ValueError):
            return
        if timestamp > 10000000000:
            timestamp //= 1000
        if price <= 0:
            return
        period = next(iter(self._subscriptions), (asset, 60))[1]
        bucket = (timestamp // period) * period
        key = (asset, period)
        bar = self._tick_bars.get(key)
        if bar is None or bar["timestamp"] != bucket:
            if bar is not None:
                self._emit(asset, Candle(bar["timestamp"], bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"]))
            self._tick_bars[key] = {"timestamp": bucket, "open": price, "high": price, "low": price, "close": price, "volume": 1.0}
        else:
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += 1.0
        bar = self._tick_bars[key]
        self._emit(asset, Candle(bar["timestamp"], bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"]))
    def _consume_binary_tick(self, raw: bytes) -> None:
        if len(raw) != 39:
            return
        try:
            values = struct.unpack("<IdIfffff", raw)
            timestamp = values[1]
            price = next((v for v in values[3:] if v > 0), None)
            if price is not None:
                self._consume_tick(self._current_asset() or "", timestamp, price)
        except (struct.error, TypeError, ValueError):
            return

    def _consume_payload(self, payload, default_asset=None) -> None:
        # Pocket Option history/stream payloads are not consistent across
        # server clusters. Normalize dicts, [asset, candles], and raw OHLC
        # arrays without requiring one exact envelope shape.
        if isinstance(payload, dict):
            asset = payload.get("asset") or payload.get("symbol") or payload.get("active") or default_asset
            for key in ("candles", "history", "data", "quotes", "values"):
                value = payload.get(key)
                if isinstance(value, list):
                    for row in value:
                        if isinstance(row, (list, tuple)) and 2 <= len(row) < 5 and asset:
                            self._consume_tick(str(asset), row[0], row[1])
                    self._consume_items(asset, value)
                    return
            candle = self._normalize_candle(payload)
            if candle and asset:
                self._emit(str(asset), candle)
            return

        if isinstance(payload, list):
            if len(payload) >= 2 and isinstance(payload[0], str) and isinstance(payload[1], list):
                self._consume_items(payload[0], payload[1])
                return
            # Common history form: [[timestamp, open, close, high, low], ...]
            self._consume_items(default_asset, payload)

    def _consume_items(self, asset, items) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict):
                candle = self._normalize_candle(item)
                item_asset = item.get("asset") or item.get("symbol") or asset
                if candle and item_asset:
                    self._emit(str(item_asset), candle)
                continue

            if isinstance(item, (list, tuple)) and len(item) >= 5 and asset:
                try:
                    # Pocket Option historical arrays are commonly
                    # [timestamp, open, close, high, low].
                    ts = int(float(item[0]))
                    o = float(item[1])
                    c = float(item[2])
                    h = float(item[3])
                    l = float(item[4])
                    v = float(item[5]) if len(item) > 5 else 0.0
                    candle = self._validate_candle(Candle(ts, o, h, l, c, v))
                    if candle:
                        self._emit(str(asset), candle)
                except (TypeError, ValueError):
                    continue

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

        return PocketOptionAdapter._validate_candle(Candle(ts, o, h, l, c, v))

    @staticmethod
    def _validate_candle(candle: Candle) -> Candle | None:
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            return None
        if candle.high < max(candle.open, candle.close):
            return None
        if candle.low > min(candle.open, candle.close) or candle.high < candle.low:
            return None
        return candle

    def _emit(self, asset: str, candle: Candle) -> None:
        if self.on_candle:
            self.on_candle(asset, candle)

    def _on_error(self, ws, error) -> None:
        # Never log the exception itself because a library error could contain
        # request headers or connection details. Keep only a safe type label.
        self.connected = False
        self.connection_stage = "websocket_error"
        self.last_error = f"WebSocket error: {type(error).__name__}"

    def _on_close(self, ws, code, reason) -> None:
        self.connected = False
        self._socket_ready = False
        self.connection_stage = f"closed:{code}" if code is not None else "closed"
