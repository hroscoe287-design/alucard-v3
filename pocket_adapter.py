# ALUCARD V3 — stable Pocket Option market connector
"""Read-only Pocket Option market-data adapter for ALUCARD V3.

The connector uses the maintained pocket-option SDK, selects the SDK's own
region constants (including DEMO regions), and keeps retrying after transient
WebSocket disconnects. It never places trades.
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

# Pocket Option's auth payload uses 1 for demo and 0 for real.
# ALUCARD's dashboard is configured as DEMO by default.
POCKET_DEMO = os.getenv("POCKET_DEMO", os.getenv("PO_IS_DEMO", "1")).strip() or "1"
POCKET_PLATFORM = os.getenv("POCKET_PLATFORM", os.getenv("PO_PLATFORM", "2")).strip() or "2"
POCKET_WS_URL = os.getenv("POCKET_WS_URL", "").strip()


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
        self._data_logged = False

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
        from pocket_option.constants import Regions
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

        # Use the SDK's own current region constants instead of maintaining a
        # second hard-coded list that can drift from the package.
        if demo:
            regions = [Regions.DEMO, Regions.DEMO_2]
        else:
            regions = [
                Regions.UNITED_STATES_NORTH,
                Regions.UNITED_STATES_SOUTH,
                Regions.EUROPA,
                Regions.ASIA,
                Regions.UNITED_STATES_2,
                Regions.UNITED_STATES_3,
                Regions.UNITED_STATES_4,
                Regions.FRANCE_1,
                Regions.FRANCE_2,
                Regions.INDIA,
                Regions.FINLAND,
                Regions.SEYCHELLES,
                Regions.HONGKONG,
                Regions.SERVER_1,
                Regions.SERVER_2,
                Regions.SERVER_3,
                Regions.RUSSIA,
            ]

        if POCKET_WS_URL:
            regions = [POCKET_WS_URL] + [
                x for x in regions if str(x) != POCKET_WS_URL
            ]

        retry_round = 0

        while not self._stop.is_set():
            retry_round += 1
            connected_this_round = False

            for base_url in regions:
                if self._stop.is_set():
                    return

                assets = [Asset(asset) for asset, _ in self._subscriptions]
                if not assets:
                    assets = [Asset("EURUSD_otc")]

                periods = [period for _, period in self._subscriptions]
                period = periods[0] if periods else 60

                client = PocketOptionClient(
                    logger=False,
                    socketio_logger=False,
                    engineio_logger=False,
                    request_timeout=12,
                    reconnection=True,
                    reconnection_attempts=0,
                )
                self._client = client
                self._loop = asyncio.get_running_loop()
                self.connected = False
                self.connection_stage = f"connecting:{str(base_url).split('//')[-1]}"
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

                @client.on.disconnect
                async def _on_disconnect(_data=None):
                    self.connected = False
                    self.connection_stage = "socket_disconnected"

                @client.on.load_history_period_fast
                async def _on_history(_data):
                    if not self.connected:
                        return
                    self.last_message_at = time.time()
                    self.connection_stage = "market_data_received"
                    if not self._data_logged:
                        self._data_logged = True
                        print("ALUCARD CONFIRMED MARKET DATA", flush=True)

                    for asset, sub_period in list(self._subscriptions):
                        try:
                            candles = await client.candles.get_candles(
                                Asset(asset),
                                timeframe=sub_period,
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

                    if not self._data_logged:
                        self._data_logged = True
                        print("ALUCARD CONFIRMED MARKET DATA", flush=True)

                    for item in items or []:
                        asset = str(getattr(item, "asset", "")).split(".")[-1]
                        timestamp = float(getattr(item, "timestamp", 0))
                        price = float(getattr(item, "value", 0))
                        if asset and price > 0:
                            self._consume_tick(asset, timestamp, price)

                try:
                    self.connection_stage = f"opening:{str(base_url).split('//')[-1]}"
                    print(
                        f"ALUCARD Pocket Option SDK trying {str(base_url).split('//')[-1]}",
                        flush=True,
                    )

                    await client.connect(
                        base_url,
                        auth=auth.model_dump(mode="json"),
                        wait=True,
                        wait_timeout=12,
                        retry=False,
                    )

                    try:
                        await asyncio.wait_for(
                            client.authorized_event.wait(),
                            timeout=15,
                        )
                    except TimeoutError:
                        self.connection_stage = "authorization_timeout"
                        self.last_error = "Pocket Option authorization timeout"
                        await client.disconnect()
                        continue

                    self.connected = True
                    self.connection_stage = "authenticated"
                    connected_this_round = True
                    retry_round = 0

                    # Make sure the selected subscription is active even when
                    # the server does not replay default_init callbacks.
                    for asset, sub_period in list(self._subscriptions):
                        try:
                            await self._subscribe_async(asset, sub_period)
                        except Exception as exc:
                            self.last_error = f"subscription:{type(exc).__name__}"

                    # Stay attached to this server. If it drops, the outer
                    # loop selects another current region and reconnects.
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
                    self.connected = False
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

                if self._stop.is_set():
                    return

                # A connection that actually authenticated/data-streamed has
                # already proven the credentials are valid; retry immediately
                # after a disconnect rather than waiting through a full sweep.
                if connected_this_round:
                    await asyncio.sleep(1)
                    break

                await asyncio.sleep(1)

            if self._stop.is_set():
                return

            # If every region failed, back off briefly and try the complete
            # current SDK region list again instead of stopping permanently.
            delay = min(15, 2 + retry_round)
            self.connection_stage = f"retrying_in:{delay}s"
            await asyncio.sleep(delay)

        self.connected = False
        self.connection_stage = "stopped"

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
