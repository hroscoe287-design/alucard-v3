"""Native Pocket Option Socket.IO market-data adapter for ALUCARD V3.

This implementation uses the maintained unofficial Pocket Option SDK instead of
hand-rolling the Engine.IO websocket handshake. It is read-only: it subscribes
to market data and never opens trades.
"""

from __future__ import annotations

import asyncio
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
        for name in ("POCKET_UID", "PO_UID", "POCKET_OPTION_UID", "UID", "USER_ID")
        if os.getenv(name, "").strip()
    ),
    "",
)

POCKET_DEMO = os.getenv("POCKET_DEMO", os.getenv("PO_IS_DEMO", "0")).strip() or "0"
POCKET_PLATFORM = os.getenv("POCKET_PLATFORM", os.getenv("PO_PLATFORM", "2")).strip() or "2"

POCKET_WS_URL = os.getenv("POCKET_WS_URL", "").strip()

REAL_REGIONS = [
    "wss://api-us-north.po.market",
    "wss://api-us-south.po.market",
    "wss://api-eu.po.market",
    "wss://api-asia.po.market",
    "wss://api-us2.po.market",
    "wss://api-us3.po.market",
    "wss://api-us4.po.market",
    "wss://api-fr.po.market",
    "wss://api-fr2.po.market",
    "wss://api-in.po.market",
    "wss://api-fin.po.market",
    "wss://api-sc.po.market",
    "wss://api-hk.po.market",
    "wss://api-spb.po.market",
    "wss://api-l.po.market",
    "wss://api-c.po.market",
    "wss://api-msk.po.market",
]


class PocketOptionAdapter:
    def __init__(self, on_candle: Callable[[str, Candle], None] | None = None):
        self.on_candle = on_candle
        self.connected = False
        self.last_message_at = 0.0
        self.last_error = ""
        self.connection_stage = "idle"
        self._stop = threading.Event()
        self._subscriptions: set[tuple[str, int]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = None
        self._bars: dict[tuple[str, int], dict] = {}

    @property
    def configured(self) -> bool:
        return bool(POCKET_SESSION and POCKET_UID)

    def subscribe(self, asset: str, period: int) -> None:
        self._subscriptions.add((asset, period))
        if self._loop and self._client and self.connected:
            asyncio.run_coroutine_threadsafe(
                self._subscribe_async(asset, period),
                self._loop,
            )

    async def _subscribe_async(self, asset: str, period: int) -> None:
        from pocket_option.models import Asset, ChangeAssetRequest

        po_asset = Asset(asset)
        await self._client.emit.subscribe_to_asset(po_asset)
        await self._client.emit.change_asset(
            ChangeAssetRequest(asset=po_asset, period=period)
        )
        await self._client.emit.subscribe_for_market_sentiment(po_asset)
        self.connection_stage = "market_subscription_sent"

    def stop(self) -> None:
        self._stop.set()
        if self._loop and self._client:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._client.disconnect(),
                    self._loop,
                )
            except Exception:
                pass

    def connect(self) -> None:
        if not self.configured:
            raise RuntimeError("Pocket Option credentials are not configured")

        try:
            asyncio.run(self._connect_loop())
        except Exception as exc:
            self.connected = False
            self.last_error = f"SDK: {type(exc).__name__}"
            self.connection_stage = "sdk_error"
            raise

    async def _connect_loop(self) -> None:
        from pocket_option import PocketOptionClient
        from pocket_option.contrib.default_init import default_init
        from pocket_option.models import Asset, AuthorizationData

        try:
            demo = int(POCKET_DEMO)
            platform = int(POCKET_PLATFORM)
            uid = int(POCKET_UID)
        except ValueError as exc:
            raise RuntimeError("Invalid Pocket Option numeric configuration") from exc

        auth = AuthorizationData.model_validate(
            {
                "session": POCKET_SESSION,
                "isDemo": demo,
                "uid": uid,
                "platform": platform,
                "isFastHistory": True,
                "isOptimized": True,
            }
        )

        assets = [Asset(asset) for asset, _ in self._subscriptions]
        if not assets:
            assets = [Asset("EURUSD_otc")]

        periods = [period for _, period in self._subscriptions]
        period = periods[0] if periods else 60

        regions = list(REAL_REGIONS)
        if POCKET_WS_URL:
            regions = [POCKET_WS_URL] + [x for x in regions if x != POCKET_WS_URL]

        for base_url in regions:
            if self._stop.is_set():
                return

            client = PocketOptionClient(
                logger=False,
                socketio_logger=False,
                engineio_logger=False,
                request_timeout=8,
                reconnection=True,
                reconnection_attempts=0,
            )
            self._client = client
            self._loop = asyncio.get_running_loop()
            self.connected = False
            self.connection_stage = f"connecting:{base_url.split('//')[-1]}"
            self.last_error = ""

            default_init(
                client,
                authorization=auth,
                sub_assets=assets,
                sub_period=period,
            )

            @client.on.connect
            async def _on_connect():
                self.connection_stage = "socketio_connected"

            @client.on.success_auth
            async def _on_auth(_data):
                self.connected = True
                self.last_message_at = time.time()
                self.connection_stage = "authenticated"
                print("ALUCARD Pocket Option SDK authenticated", flush=True)

            @client.on.load_history_period_fast
            async def _on_history(_data):
                if not self.connected:
                    return
                self.last_message_at = time.time()
                self.connection_stage = "market_data_received"
                for asset, period in list(self._subscriptions):
                    try:
                        candles = await client.candles.get_candles(
                            Asset(asset),
                            timeframe=period,
                            count=120,
                        )
                    except Exception:
                        continue
                    for candle in candles:
                        self._emit_sdk_candle(asset, candle)

            @client.on.update_history_new_fast
            async def _on_history_update(_data):
                self.last_message_at = time.time()
                if self.connected:
                    self.connection_stage = "market_data_received"

            @client.on.update_close_value
            async def _on_stream(items):
                self.last_message_at = time.time()
                self.connected = True
                self.connection_stage = "market_data_received"
                for item in items or []:
                    asset = str(getattr(item, "asset", "")).split(".")[-1]
                    timestamp = float(getattr(item, "timestamp", 0))
                    price = float(getattr(item, "value", 0))
                    if asset and price > 0:
                        self._consume_tick(asset, timestamp, price)

            try:
                self.connection_stage = f"opening:{base_url.split('//')[-1]}"
                print(
                    f"ALUCARD Pocket Option SDK trying {base_url.split('//')[-1]}",
                    flush=True,
                )
                await client.connect(base_url, auth=auth, wait=True, wait_timeout=10, retry=False)

                # Socket.IO connect succeeded. default_init sends auth and the
                # successauth event flips self.connected.
                try:
                    await asyncio.wait_for(client.authorized_event.wait(), timeout=12)
                except TimeoutError:
                    self.connection_stage = "authorization_timeout"
                    self.last_error = "Pocket Option authorization timeout"
                    await client.disconnect()
                    continue

                self.connected = True
                self.connection_stage = "authenticated"

                # Ensure the selected subscription is active even if the
                # server did not replay the default_init callbacks.
                for asset, sub_period in list(self._subscriptions):
                    await self._subscribe_async(asset, sub_period)

                await client.wait()
            except Exception as exc:
                self.connected = False
                self.last_error = f"SDK {type(exc).__name__}"
                self.connection_stage = "sdk_connection_error"
                print(
                    f"ALUCARD Pocket Option SDK connection error: {type(exc).__name__}",
                    flush=True,
                )
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            if not self._stop.is_set():
                await asyncio.sleep(1)

        self.connected = False
        if not self.last_error:
            self.last_error = "Pocket Option regions exhausted"
        self.connection_stage = "regions_exhausted"

    def _consume_tick(self, asset: str, timestamp: float, price: float) -> None:
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0

        period = next(
            (p for a, p in self._subscriptions if a == asset),
            next(iter(self._subscriptions), ("", 60))[1],
        )
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

    def _emit_sdk_candle(self, asset: str, candle) -> None:
        try:
            ts = float(candle.timestamp.timestamp())
            if ts > 10_000_000_000:
                ts /= 1000.0
            self._emit(
                asset,
                Candle(
                    int(ts),
                    float(candle.open),
                    float(candle.high),
                    float(candle.low),
                    float(candle.close),
                    0.0,
                ),
            )
        except (AttributeError, TypeError, ValueError):
            return

    def _emit(self, asset: str, candle: Candle) -> None:
        if self.on_candle:
            self.on_candle(asset, candle)
