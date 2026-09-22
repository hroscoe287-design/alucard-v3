# ALUCARD V3 — direct Pocket Option WebSocket connector
"""Read-only Pocket Option market-data adapter for ALUCARD V3.

This connector follows the direct WebSocket architecture used by community
Pocket Option clients instead of the pocket-option 0.4.x Pydantic/socket.io
emitter. It builds the browser-style 42["auth", ...] frame, lets the client
handle Socket.IO framing/reconnects, subscribes to the selected asset, loads
history, and converts live ticks into candles.

It never places orders.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable

from market_engine import Candle

POCKET_SESSION = next(
    (
        os.getenv(name, "").strip()
        for name in (
            "POCKET_SESSION",
            "PO_SSID",
            "POCKET_OPTION_SSID",
            "POCKET_OPTION_SESSION",
            "PO_SESSION",
            "PO_SSID_TOKEN",
            "PO_TOKEN",
            "SSID",
        )
        if os.getenv(name, "").strip()
    ),
    "",
)

POCKET_UID = next(
    (
        os.getenv(name, "").strip()
        for name in (
            "POCKET_UID",
            "PO_UID",
            "POCKET_OPTION_UID",
            "UID",
            "USER_ID",
        )
        if os.getenv(name, "").strip()
    ),
    "",
)

POCKET_DEMO = os.getenv("POCKET_DEMO", os.getenv("PO_IS_DEMO", "1")).strip() or "1"
POCKET_PLATFORM = os.getenv("POCKET_PLATFORM", os.getenv("PO_PLATFORM", "2")).strip() or "2"


class PocketOptionAdapter:
    """Synchronous wrapper around the community direct-WebSocket client."""

    def __init__(self, on_candle: Callable[[str, Candle], None] | None = None):
        self.on_candle = on_candle
        self.connected = False
        self.last_message_at = 0.0
        self.last_error = ""
        self.connection_stage = "idle"
        self._stop = threading.Event()
        self._subscriptions: set[tuple[str, int]] = set()
        self._client = None
        self._bars: dict[tuple[str, int], dict] = {}
        self._data_logged = False

    @property
    def configured(self) -> bool:
        return bool(POCKET_SESSION and POCKET_UID)

    def subscribe(self, asset: str, period: int) -> None:
        self._subscriptions.add((asset, period))
        if self.connected and self._client:
            try:
                self._client.subscribe(asset, period)
                self.connection_stage = "market_subscription_sent"
            except Exception as exc:
                self.last_error = f"subscription:{type(exc).__name__}"

    def stop(self) -> None:
        self._stop.set()
        client = self._client
        if client is not None:
            try:
                client.disconnect_websocket()
            except Exception:
                pass

    def _ssid(self) -> str:
        try:
            uid = int(POCKET_UID)
            demo = int(POCKET_DEMO)
            platform = int(POCKET_PLATFORM)
        except ValueError as exc:
            raise RuntimeError("Invalid Pocket Option UID/demo/platform configuration") from exc

        # Community clients document this exact Socket.IO wire format.
        payload = {
            "session": POCKET_SESSION,
            "isDemo": demo,
            "uid": uid,
            "platform": platform,
            "isFastHistory": True,
            "isOptimized": True,
        }
        return "42" + json.dumps(["auth", payload], separators=(",", ":"))

    def connect(self) -> None:
        if not self.configured:
            raise RuntimeError("Pocket Option credentials are not configured")

        from pocketoptionapi import PocketOption

        retry = 0
        while not self._stop.is_set():
            retry += 1
            client = None
            try:
                self.connection_stage = "building_ssid"
                ssid = self._ssid()

                self.connection_stage = "connecting_direct_websocket"
                print(
                    "ALUCARD using direct Pocket Option WebSocket client",
                    flush=True,
                )

                client = PocketOption(ssid)
                self._client = client

                ok, error = client.connect()
                if not ok:
                    self.connected = False
                    self.connection_stage = "authorization_failed"
                    self.last_error = str(error or "Pocket Option connection failed")[:200]
                    print(
                        f"ALUCARD direct WebSocket connection failed: {type(error).__name__ if error else 'unknown'}",
                        flush=True,
                    )
                    try:
                        client.disconnect_websocket()
                    except Exception:
                        pass
                    time.sleep(min(15, 2 + retry))
                    continue

                self.connected = True
                self.last_message_at = time.time()
                self.connection_stage = "authenticated"
                retry = 0
                print("ALUCARD DIRECT WEBSOCKET AUTHENTICATED", flush=True)

                # Subscribe to the dashboard's selected market.
                for asset, period in list(self._subscriptions):
                    if client.subscribe(asset, period):
                        self.connection_stage = "market_subscription_sent"

                # Seed the engine with real server candles before relying on
                # tick aggregation. This is read-only.
                for asset, period in list(self._subscriptions):
                    self._load_history(client, asset, period)

                # Poll the client's ring buffer. The underlying client receives
                # updateStream ticks on its own websocket thread.
                self._poll_stream(client)

            except Exception as exc:
                self.connected = False
                self.connection_stage = "direct_websocket_error"
                self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
                print(
                    f"ALUCARD direct WebSocket error: {type(exc).__name__}",
                    flush=True,
                )
            finally:
                self.connected = False
                if client is not None:
                    try:
                        client.disconnect_websocket()
                    except Exception:
                        pass

            if not self._stop.is_set():
                delay = min(15, 2 + retry)
                self.connection_stage = f"retrying_in:{delay}s"
                time.sleep(delay)

        self.connected = False
        self.connection_stage = "stopped"

    def _load_history(self, client, asset: str, period: int) -> None:
        self.connection_stage = "loading_market_history"
        try:
            candles = client.get_historical_candles(
                asset,
                period,
                offset=9000,
                count_request=1,
            )
            if not candles:
                self.last_error = "No historical candles returned"
                return

            # The direct client returns normalized dictionaries. Keep the
            # latest 120 closed bars for the ALUCARD indicator engine.
            for row in candles[-120:]:
                try:
                    ts = float(row.get("time", row.get("timestamp", 0)))
                    if ts > 10_000_000_000:
                        ts /= 1000.0
                    self._emit(
                        asset,
                        Candle(
                            int(ts),
                            float(row["open"]),
                            float(row["high"]),
                            float(row["low"]),
                            float(row["close"]),
                            float(row.get("volume", 0) or 0),
                        ),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            self.last_message_at = time.time()
            self.connection_stage = "market_data_received"
            if not self._data_logged:
                self._data_logged = True
                print(
                    f"ALUCARD CONFIRMED MARKET DATA: {asset} candles={len(candles)}",
                    flush=True,
                )
        except Exception as exc:
            self.last_error = f"history:{type(exc).__name__}"
            print(
                f"ALUCARD history error: {type(exc).__name__}",
                flush=True,
            )

    def _poll_stream(self, client) -> None:
        seen: dict[str, int] = {}

        while not self._stop.is_set() and self.connected:
            subscriptions = list(self._subscriptions)
            if not subscriptions:
                time.sleep(1)
                continue

            for asset, period in subscriptions:
                try:
                    ticks = client.get_realtime_ticks(asset, limit=200)
                except Exception as exc:
                    self.last_error = f"ticks:{type(exc).__name__}"
                    continue

                start = seen.get(asset, 0)
                if start > len(ticks):
                    start = 0

                for timestamp, price in ticks[start:]:
                    self.last_message_at = time.time()
                    self.connection_stage = "market_data_received"
                    self._consume_tick(asset, period, float(timestamp), float(price))

                seen[asset] = len(ticks)

            time.sleep(0.25)

    def _consume_tick(self, asset: str, period: int, timestamp: float, price: float) -> None:
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        if price <= 0:
            return

        bucket = int(timestamp // period) * period
        key = (asset, period)
        bar = self._bars.get(key)

        if bar is None or bar["timestamp"] != bucket:
            if bar is not None:
                self._emit(
                    asset,
                    Candle(
                        bar["timestamp"],
                        bar["open"],
                        bar["high"],
                        bar["low"],
                        bar["close"],
                        bar["volume"],
                    ),
                )

            bar = {
                "timestamp": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 1.0,
            }
            self._bars[key] = bar
        else:
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += 1.0

        # Emit the current forming candle too, so the dashboard stays live.
        self._emit(
            asset,
            Candle(
                bar["timestamp"],
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
                bar["volume"],
            ),
        )

    def _emit(self, asset: str, candle: Candle) -> None:
        if self.on_candle:
            self.on_candle(asset, candle)
