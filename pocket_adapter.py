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

def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


_RAW_SESSION = _first_env((
    "POCKET_SESSION",
    "PO_SSID",
    "POCKET_OPTION_SSID",
    "POCKET_OPTION_SESSION",
    "PO_SESSION",
    "PO_SSID_TOKEN",
    "PO_TOKEN",
    "SSID",
)).strip()

# Accept either a plain session string or the complete browser-style
# 42["auth",{...}] message.  This also lets ALUCARD derive UID from the
# captured auth message, so a separate UID variable is optional.
POCKET_SESSION = _RAW_SESSION
POCKET_UID = _first_env((
    "POCKET_UID",
    "PO_UID",
    "POCKET_OPTION_UID",
    "UID",
    "USER_ID",
))
POCKET_DEMO = os.getenv("POCKET_DEMO", os.getenv("PO_IS_DEMO", "1")).strip() or "1"
POCKET_PLATFORM = os.getenv("POCKET_PLATFORM", os.getenv("PO_PLATFORM", "2")).strip() or "2"

if _RAW_SESSION.lstrip().startswith("42") and '"auth"' in _RAW_SESSION:
    try:
        auth = json.loads(_RAW_SESSION[2:])
        payload = auth[1]
        if isinstance(payload, dict):
            # If the user supplied the complete browser auth frame, its
            # session/UID/demo/platform values are authoritative. This
            # prevents an older standalone UID variable from being paired
            # with a newer session token.
            raw_session = str(payload.get("session", "")).strip()
            raw_uid = str(payload.get("uid", "")).strip()
            raw_demo = str(payload.get("isDemo", "")).strip()
            raw_platform = str(payload.get("platform", "")).strip()

            if raw_session:
                POCKET_SESSION = raw_session
            if raw_uid:
                POCKET_UID = raw_uid
            if raw_demo:
                POCKET_DEMO = raw_demo
            if raw_platform:
                POCKET_PLATFORM = raw_platform
    except (ValueError, TypeError, IndexError, KeyError):
        pass




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
        # If Render received the complete browser auth frame, preserve it
        # byte-for-byte. The PocketOption client itself parses the frame and
        # rebuilds the connection payload. Reconstructing it here can silently
        # drop browser fields or pair a session with stale metadata.
        raw = _RAW_SESSION.strip()
        if raw.startswith("42") and '"auth"' in raw:
            try:
                parsed = json.loads(raw[2:])
                if (
                    isinstance(parsed, list)
                    and len(parsed) >= 2
                    and parsed[0] == "auth"
                    and isinstance(parsed[1], dict)
                    and parsed[1].get("session")
                    and parsed[1].get("uid") is not None
                    and parsed[1].get("isDemo") is not None
                ):
                    return raw
            except (ValueError, TypeError, IndexError):
                pass
            raise RuntimeError("Pocket Option auth frame is malformed")

        try:
            uid = int(POCKET_UID)
            demo = int(POCKET_DEMO)
            platform = int(POCKET_PLATFORM)
        except ValueError as exc:
            raise RuntimeError("Invalid Pocket Option UID/demo/platform configuration") from exc

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
                    safe_error = str(error or "Pocket Option connection failed").replace("\n", " ")[:180]
                    print(
                        f"ALUCARD Pocket Option connection rejected: {safe_error}",
                        flush=True,
                    )
                    if "41" in safe_error or "NotAuthorized" in safe_error or "Unauthorized" in safe_error:
                        self.connection_stage = "authorization_failed_fresh_ssid_required"
                        self.last_error = "Pocket Option rejected the SSID (41/NotAuthorized). A fresh browser auth frame is required."
                        print("ALUCARD AUTH FAILED: fresh Pocket Option browser 42[auth,...] SSID required", flush=True)
                        break
                    try:
                        client.disconnect_websocket()
                    except Exception:
                        pass
                    time.sleep(min(15, 2 + retry))
                    continue

                self.connection_stage = "waiting_for_socket_ready"
                deadline = time.time() + 30.0
                while not self._stop.is_set() and time.time() < deadline:
                    try:
                        if client.check_connect():
                            break
                    except Exception:
                        pass
                    time.sleep(0.25)

                if self._stop.is_set():
                    break

                try:
                    socket_ready = bool(client.check_connect())
                except Exception:
                    socket_ready = False

                if not socket_ready:
                    self.connected = False
                    self.connection_stage = "socket_ready_timeout"
                    self.last_error = "Pocket Option socket did not become ready"
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

                # The library requires server time synchronization before
                # historical candle requests. Do not request history early.
                for asset, period in list(self._subscriptions):
                    if client.subscribe(asset, period):
                        self.connection_stage = "market_subscription_sent"

                self.connection_stage = "waiting_for_time_sync"
                deadline = time.time() + 30.0
                while not self._stop.is_set() and time.time() < deadline:
                    try:
                        if client.is_time_synced():
                            break
                    except Exception:
                        pass
                    time.sleep(0.25)

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
