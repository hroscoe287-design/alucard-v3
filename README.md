# ALUCARD V4 — Gothic Market Intelligence

A new ALUCARD build from scratch. This repository is intentionally separate from the legacy ALUCARD V2 project.

## Architecture

Pocket Option WebSocket → Market Data Adapter → Candle State → Technical Analysis → Signal Engine → Dashboard

## Included

- Flask web dashboard
- Pocket Option Socket.IO/Engine.IO WebSocket adapter
- OHLC candle normalization and thread-safe storage
- EMA 9/20/50
- RSI
- MACD
- CCI
- ATR
- ADX / directional movement
- Bollinger Bands
- Stochastic
- Transparent CALL / PUT / WAIT signal logic
- Live feed/staleness state
- Asset groups and timeframe selector
- Render Blueprint for a free web service

## Timeframes

5s, 15s, 30s, 1m, 2m, 3m, 5m, 15m, 30m, 1h, 4h, 1d.

## Runtime configuration

Set these environment variables in Render:

- POCKET_SESSION — your current Pocket Option browser session value
- POCKET_UID — your Pocket Option user ID
- POCKET_DEMO — configured account mode
- POCKET_PLATFORM — Pocket Option platform identifier
- POCKET_ASSET — default asset, currently EURUSD_otc
- POCKET_TIMEFRAME — default timeframe, currently 1m

Never commit a Pocket Option session or other credential to GitHub.

## Render

The repository contains render.yaml. Connect the repository to Render and create the Blueprint. The two secret variables are intentionally marked sync: false.

## Important

The signal confidence shown by ALUCARD is a model score, not a guaranteed probability of winning. The application analyzes market data and does not place trades.

The Pocket Option WebSocket protocol can change. Native binary stream packets are kept isolated from the normalized candle layer so protocol changes can be handled without rewriting the analysis engine.
