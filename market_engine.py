# ============================================================
# ALUCARD V3 — GOTHIC MARKET INTELLIGENCE
# Dashboard / API entrypoint
# ============================================================

import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

from signal_service import service


app = Flask(__name__)

APP_NAME = "ALUCARD V3"
APP_SUBTITLE = "GOTHIC MARKET INTELLIGENCE"
VERSION = "3.3.0"


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = [
    "5s",
    "10s",
    "15s",
    "30s",
    "1m",
    "2m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
    "1w",
    "1mo",
]

PERIODS = {
    "5s": 5,
    "10s": 10,
    "15s": 15,
    "30s": 30,
    "1m": 60,
    "2m": 120,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1mo": 2592000,
}


# ============================================================
# POCKET OPTION ASSET CATALOG
# ============================================================

ASSET_GROUPS = {
    "FOREX": [
        "EURUSD",
        "AUDCAD",
        "AUDCHF",
        "AUDJPY",
        "AUDUSD",
        "CADCHF",
        "CADJPY",
        "CHFJPY",
        "EURAUD",
        "EURCAD",
        "EURCHF",
        "EURGBP",
        "EURJPY",
        "GBPAUD",
        "GBPCAD",
        "GBPCHF",
        "GBPJPY",
        "GBPUSD",
        "NZDJPY",
        "NZDUSD",
        "USDCAD",
        "USDCHF",
        "USDJPY",
    ],

    "OTC FOREX": [
        "EURUSD_otc",
        "AUDCAD_otc",
        "AUDCHF_otc",
        "AUDJPY_otc",
        "AUDNZD_otc",
        "AUDUSD_otc",
        "CADCHF_otc",
        "CADJPY_otc",
        "CHFJPY_otc",
        "CHFNOK_otc",
        "EURAUD_otc",
        "EURCAD_otc",
        "EURCHF_otc",
        "EURGBP_otc",
        "EURJPY_otc",
        "EURNZD_otc",
        "EURRUB_otc",
        "EURTRY_otc",
        "EURHUF_otc",
        "GBPAUD_otc",
        "GBPCAD_otc",
        "GBPCHF_otc",
        "GBPJPY_otc",
        "GBPUSD_otc",
        "NZDJPY_otc",
        "NZDUSD_otc",
        "USDCAD_otc",
        "USDCHF_otc",
        "USDJPY_otc",
        "USDRUB_otc",
        "USDCNH_otc",
        "USDINR_otc",
        "USDSGD_otc",
        "USDCLP_otc",
        "USDTHB_otc",
        "USDMYR_otc",
        "USDVND_otc",
        "USDPKR_otc",
        "USDCOP_otc",
        "USDPHP_otc",
        "USDMXN_otc",
        "USDIDR_otc",
        "USDARS_otc",
        "USDBRL_otc",
        "USDBDT_otc",
        "USDDZD_otc",
        "USDEGP_otc",
        "ZARUSD_otc",
        "UAHUSD_otc",
        "YERUSD_otc",
        "NGNUSD_otc",
        "TNDUSD_otc",
        "MADUSD_otc",
        "LBPUSD_otc",
        "BHDCNY_otc",
        "AEDCNY_otc",
        "SARCNY_otc",
        "QARCNY_otc",
        "OMRCNY_otc",
        "JODCNY_otc",
        "KESUSD_otc",
    ],

    "COMMODITIES": [
        "XAUUSD",
        "XAGUSD",
        "USOIL",
        "UKOIL",
        "NATGAS",
    ],

    "OTC COMMODITIES": [
        "XAUUSD_otc",
        "XAGUSD_otc",
        "USOIL_otc",
        "UKOIL_otc",
        "NATGAS_otc",
        "PLATINUM_otc",
        "PALLADIUM_otc",
    ],

    "CRYPTO": [
        "BTCUSD",
        "ETHUSD",
        "LTCUSD",
        "XRPUSD",
        "BCHUSD",
        "DOGEUSD",
        "ADAUSD",
        "SOLUSD",
        "DOTUSD",
        "LINKUSD",
        "AVAXUSD",
        "BNB",
        "TRXUSD",
        "MATICUSD",
        "DASHUSD",
        "BTCJPY",
        "BTCGBP",
        "BCHJPY",
        "BCHGBP",
        "BCHEUR",
    ],

    "OTC CRYPTO": [
        "BTCUSD_otc",
        "ETHUSD_otc",
        "LTCUSD_otc",
        "XRPUSD_otc",
        "BCHUSD_otc",
        "DOGEUSD_otc",
        "ADAUSD_otc",
        "SOLUSD_otc",
        "DOTUSD_otc",
        "LINKUSD_otc",
        "AVAXUSD_otc",
        "BNB_otc",
        "TRXUSD_otc",
        "MATICUSD_otc",
        "TONUSD_otc",
        "BTCETF_otc",
        "DASHUSD_otc",
    ],

    "STOCKS": [
        "AAPL",
        "BA",
        "JPM",
        "MCD",
        "META",
        "VISA",
        "PFE",
        "BABA",
        "CSCO",
        "TSLA",
        "INTC",
        "AXP",
        "XOM",
        "C",
        "GME",
        "AMD",
        "MSFT",
        "PLTR",
        "NFLX",
        "MARA",
        "JNJ",
        "AMZN",
        "COIN",
        "GOOGL",
        "NVDA",
    ],

    "OTC STOCKS": [
        "AAPL_otc",
        "BA_otc",
        "JPM_otc",
        "MCD_otc",
        "META_otc",
        "VISA_otc",
        "PFE_otc",
        "BABA_otc",
        "CSCO_otc",
        "TSLA_otc",
        "INTC_otc",
        "AXP_otc",
        "XOM_otc",
        "C_otc",
        "GME_otc",
        "AMD_otc",
        "MSFT_otc",
        "PLTR_otc",
        "NFLX_otc",
        "MARA_otc",
        "JNJ_otc",
        "AMZN_otc",
        "COIN_otc",
        "GOOGL_otc",
        "NVDA_otc",
    ],

    "INDICES": [
        "US100",
        "100GBP",
        "JPN225",
        "D30EUR",
        "E50EUR",
        "SP500",
        "DJI30",
        "CAC40",
        "HONGKONG33",
        "AUS200",
    ],

    "OTC INDICES": [
        "AUS200_otc",
        "E35EUR_otc",
        "100GBP_otc",
        "F40EUR_otc",
        "JPN225_otc",
        "D30EUR_otc",
        "E50EUR_otc",
        "SP500_otc",
        "DJI30_otc",
        "US100_otc",
    ],
}


def make_label(symbol):
    if symbol.endswith("_otc"):
        base = symbol[:-4]
        return f"{base} OTC"

    replacements = {
        "EURUSD": "EUR/USD",
        "AUDCAD": "AUD/CAD",
        "AUDCHF": "AUD/CHF",
        "AUDJPY": "AUD/JPY",
        "AUDUSD": "AUD/USD",
        "CADCHF": "CAD/CHF",
        "CADJPY": "CAD/JPY",
        "CHFJPY": "CHF/JPY",
        "EURAUD": "EUR/AUD",
        "EURCAD": "EUR/CAD",
        "EURCHF": "EUR/CHF",
        "EURGBP": "EUR/GBP",
        "EURJPY": "EUR/JPY",
        "GBPAUD": "GBP/AUD",
        "GBPCAD": "GBP/CAD",
        "GBPCHF": "GBP/CHF",
        "GBPJPY": "GBP/JPY",
        "GBPUSD": "GBP/USD",
        "NZDJPY": "NZD/JPY",
        "NZDUSD": "NZD/USD",
        "USDCAD": "USD/CAD",
        "USDCHF": "USD/CHF",
        "USDJPY": "USD/JPY",
        "XAUUSD": "GOLD / USD",
        "XAGUSD": "SILVER / USD",
    }

    return replacements.get(symbol, symbol)


ASSET_LABELS = {}

for group_assets in ASSET_GROUPS.values():
    for asset in group_assets:
        ASSET_LABELS[asset] = make_label(asset)


VALID_ASSETS = {
    asset
    for group_assets in ASSET_GROUPS.values()
    for asset in group_assets
}


# ============================================================
# QUANTUM CLOUD STATUS
# ============================================================

QUANTUM_CLOUDS = [
    (
        "IBM QUANTUM",
        "Qiskit / Quantum Compute",
        "IBM_QUANTUM_API_TOKEN",
    ),
    (
        "AWS BRAKET",
        "Managed QPU / Simulator",
        "AWS_ACCESS_KEY_ID",
    ),
    (
        "AZURE QUANTUM",
        "Hybrid Quantum Cloud",
        "AZURE_QUANTUM_RESOURCE_ID",
    ),
    (
        "GOOGLE QUANTUM AI",
        "Quantum Engine / Cirq",
        "GOOGLE_CLOUD_PROJECT",
    ),
]


# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_ASSET = os.getenv(
    "POCKET_ASSET",
    "EURUSD_otc",
)

DEFAULT_TIMEFRAME = os.getenv(
    "POCKET_TIMEFRAME",
    "1m",
)


if DEFAULT_ASSET not in VALID_ASSETS:
    DEFAULT_ASSET = "EURUSD_otc"

if DEFAULT_TIMEFRAME not in TIMEFRAMES:
    DEFAULT_TIMEFRAME = "1m"


# ============================================================
# HTML DASHBOARD
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width,initial-scale=1,maximum-scale=1">

<title>ALUCARD V3 • Gothic Market Intelligence</title>

<style>

:root {
    --bg:#030507;
    --panel:#070b0e;
    --panel2:#0b1115;
    --line:#281017;
    --red:#ff1230;
    --red2:#8c0618;
    --green:#00ff91;
    --cyan:#25d9ff;
    --yellow:#f1cc75;
    --text:#edf5f7;
    --muted:#718188;
}

* {
    box-sizing:border-box;
}

html,body {
    margin:0;
    min-height:100%;
    background:#030507;
    color:var(--text);
    font-family:Arial,Helvetica,sans-serif;
}

body {
    background:
      radial-gradient(circle at 75% 0%,
        rgba(120,0,25,.32),transparent 28%),
      radial-gradient(circle at 10% 40%,
        rgba(0,120,140,.10),transparent 35%),
      linear-gradient(135deg,#020304,#09070b,#020304);
}

body:before {
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    opacity:.13;
    background:
      linear-gradient(rgba(255,0,0,.05) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,0,0,.04) 1px,transparent 1px);
    background-size:40px 40px;
}

button,
select,
input {
    font:inherit;
}

button {
    cursor:pointer;
}

.shell {
    display:grid;
    grid-template-columns:215px 1fr;
    min-height:100vh;
}

.sidebar {
    background:
      linear-gradient(180deg,#060609,#0a080c 60%,#040507);
    border-right:1px solid #430c17;
    padding:16px 12px;
    position:sticky;
    top:0;
    height:100vh;
}

.brand {
    text-align:center;
    color:var(--red);
    font-family:Georgia,serif;
    font-size:29px;
    letter-spacing:2px;
    text-shadow:0 0 18px rgba(255,0,35,.55);
}

.brand small {
    display:block;
    color:#c8d4d8;
    font-family:Arial,sans-serif;
    font-size:10px;
    letter-spacing:4px;
    margin-top:4px;
}

.crest {
    height:125px;
    margin:18px 0;
    border:1px solid #57111d;
    border-radius:8px;
    display:grid;
    place-items:center;
    font-size:62px;
    color:var(--red);
    background:
      radial-gradient(circle,
        rgba(255,0,30,.25),transparent 58%),
      linear-gradient(135deg,#230007,#050507);
}

.nav {
    display:grid;
    gap:6px;
}

.nav button {
    width:100%;
    text-align:left;
    color:#a8b7bc;
    background:transparent;
    border:1px solid transparent;
    padding:11px 12px;
    border-radius:7px;
}

.nav button:hover,
.nav button.active {
    color:white;
    border-color:#68101d;
    background:rgba(130,0,20,.20);
    box-shadow:inset 3px 0 var(--red);
}

.side-assets {
    margin-top:18px;
    border-top:1px solid #331019;
    padding-top:13px;
}

.side-assets h4 {
    margin:0 0 8px;
    color:#77888e;
    font-size:10px;
    letter-spacing:2px;
}

.side-assets button {
    width:100%;
    border:0;
    background:none;
    color:#91a2a8;
    padding:7px;
    text-align:left;
}

.main {
    min-width:0;
    padding:12px;
}

.hero {
    min-height:145px;
    position:relative;
    overflow:hidden;
    border:1px solid #4b0d18;
    border-radius:10px;
    background:
      radial-gradient(circle at 35% 30%,
        rgba(125,0,25,.48),transparent 42%),
      linear-gradient(110deg,#0c0508,#18070c,#050709);
}

.hero:after {
    content:"";
    position:absolute;
    bottom:0;
    left:0;
    right:0;
    height:1px;
    background:linear-gradient(
      90deg,transparent,var(--red),transparent
    );
}

.hero-text {
    position:absolute;
    left:25px;
    top:22px;
}

.hero-text h1 {
    margin:0;
    color:var(--red);
    font-family:Georgia,serif;
    font-size:66px;
    line-height:.9;
    letter-spacing:3px;
    text-shadow:0 0 28px rgba(255,0,25,.45);
}

.hero-text p {
    margin:9px 0 0 4px;
    letter-spacing:5px;
    font-size:14px;
}

.hero-text small {
    display:block;
    margin-top:7px;
    color:#87969b;
    letter-spacing:4px;
    font-size:10px;
}

.status-area {
    position:absolute;
    top:18px;
    right:16px;
    display:flex;
    gap:8px;
    align-items:flex-start;
}

.status-box {
    border:1px solid #3b161d;
    border-radius:7px;
    background:#05080a;
    padding:8px 11px;
    min-width:105px;
}

.status-label {
    color:#718087;
    font-size:8px;
    letter-spacing:1.5px;
}

.status-value {
    margin-top:4px;
    font-size:16px;
    font-weight:bold;
}

.live-status {
    color:var(--green);
    border-color:#075b45;
}

.offline-status {
    color:#ff4052;
    border-color:#641321;
}

.cards {
    display:grid;
    grid-template-columns:
      repeat(6,minmax(0,1fr));
    gap:8px;
    margin:10px 0;
}

.card {
    background:
      linear-gradient(145deg,
        rgba(11,15,18,.98),
        rgba(5,7,9,.98));
    border:1px solid #351019;
    border-radius:8px;
    padding:11px;
}

.label {
    color:#738289;
    font-size:9px;
    letter-spacing:1.5px;
    text-transform:uppercase;
}

.big {
    margin-top:6px;
    font-size:20px;
}

.green {
    color:var(--green);
}

.red {
    color:#ff3348;
}

.cyan {
    color:var(--cyan);
}

.yellow {
    color:var(--yellow);
}

.workspace {
    display:grid;
    grid-template-columns:minmax(0,1fr) 320px;
    gap:10px;
}

.market-card {
    min-width:0;
}

.market-controls {
    display:grid;
    grid-template-columns:minmax(0,1fr) 200px 85px;
    gap:7px;
    margin-bottom:10px;
}

.market-controls select,
.market-controls input {
    width:100%;
    color:#e8f0f2;
    background:#04080b;
    border:1px solid #4a1923;
    border-radius:6px;
    padding:10px;
    outline:none;
}

.market-controls select:focus,
.market-controls input:focus {
    border-color:var(--red);
}

.apply {
    color:white;
    background:#850719;
    border:1px solid #ff1938;
    border-radius:6px;
    font-weight:bold;
}

.tf-row {
    display:flex;
    flex-wrap:wrap;
    gap:4px;
    margin-bottom:10px;
}

.tf {
    border:1px solid #26353a;
    background:#061015;
    color:#aebdc1;
    border-radius:5px;
    padding:7px 9px;
    font-size:11px;
}

.tf.active {
    color:white;
    background:#780819;
    border-color:#e31934;
    box-shadow:0 0 10px rgba(255,0,30,.16);
}

.chart-title {
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:12px;
    margin-bottom:8px;
}

.asset-name {
    font-size:19px;
    font-weight:bold;
}

.asset-sub {
    margin-top:4px;
    color:#73858b;
    font-size:10px;
}

.chart {
    position:relative;
    height:425px;
    overflow:hidden;
    border:1px solid #42121c;
    border-radius:6px;
    background:
      linear-gradient(rgba(0,160,180,.07) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,160,180,.07) 1px,transparent 1px),
      linear-gradient(135deg,#061012,#03090b,#07100e);
    background-size:55px 55px;
}

.chart svg {
    width:100%;
    height:100%;
}

.chart-overlay {
    position:absolute;
    left:10px;
    top:8px;
    display:flex;
    flex-wrap:wrap;
    gap:12px;
    color:#7bdce4;
    font-size:9px;
    z-index:3;
}

.chart-wait {
    position:absolute;
    inset:0;
    display:grid;
    place-items:center;
    color:#5d7076;
    font-size:11px;
    letter-spacing:2px;
    pointer-events:none;
}

.next-box {
    text-align:right;
}

.next-time {
    color:var(--red);
    font-size:22px;
    font-weight:bold;
    margin-top:5px;
}

.signal-panel {
    border-color:#4e101a;
}

.signal-direction {
    font-size:47px;
    font-weight:900;
    letter-spacing:2px;
    margin:9px 0;
}

.confidence {
    font-size:12px;
    color:#aab9bd;
}

.conf-bar {
    height:8px;
    margin-top:7px;
    background:#10181b;
    border-radius:9px;
    overflow:hidden;
}

.conf-bar i {
    display:block;
    height:100%;
    width:0;
    background:var(--green);
    box-shadow:0 0 12px var(--green);
}

.metric {
    display:flex;
    justify-content:space-between;
    border-bottom:1px solid #172125;
    padding:8px 0;
    font-size:11px;
}

.metric span {
    color:#788990;
}

.metric b {
    color:#edf4f5;
}

.signal-reasons {
    margin-top:10px;
}

.reason {
    color:#a9b7bb;
    font-size:11px;
    padding:7px 0;
    border-bottom:1px solid #162126;
}

.indicators {
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:6px;
    margin-top:10px;
}

.indicator {
    padding:8px;
    border:1px solid #16262b;
    border-radius:6px;
    background:#05090b;
}

.indicator b {
    display:block;
    color:#6e8086;
    font-size:8px;
}

.indicator span {
    display:block;
    margin-top:4px;
    font-size:11px;
}

.action-grid {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:7px;
    margin-top:11px;
}

.trade-button {
    padding:10px;
    border-radius:6px;
    border:1px solid #26383e;
    background:#081116;
    color:#c8d5d9;
    font-weight:bold;
}

.trade-button.call {
    border-color:#00c979;
    background:#087b4d;
    color:white;
}

.trade-button.put {
    border-color:#ff4253;
    background:#9e1121;
    color:white;
}

.bottom-grid {
    display:grid;
    grid-template-columns:
      1.2fr .8fr 1fr;
    gap:10px;
    margin-top:10px;
}

.table {
    width:100%;
    border-collapse:collapse;
    font-size:10px;
}

.table th,
.table td {
    text-align:left;
    padding:8px 5px;
    border-bottom:1px solid #172126;
}

.table th {
    color:#718087;
    font-weight:normal;
}

.pill {
    display:inline-block;
    padding:3px 6px;
    border-radius:4px;
    border:1px solid #29414a;
    color:#a7bdc4;
}

.pill.call {
    color:var(--green);
    border-color:#08764f;
}

.pill.put {
    color:#ff4354;
    border-color:#791725;
}

.pill.wait {
    color:#b0c2c8;
}

.quantum {
    margin-top:10px;
    border-color:#16434c;
    background:
      radial-gradient(circle at 50% 0%,
        rgba(0,180,220,.10),transparent 45%),
      #050b0e;
}

.quantum-head {
    display:flex;
    justify-content:space-between;
    align-items:center;
}

.quantum-head strong {
    letter-spacing:1px;
}

.quantum-head span {
    color:var(--cyan);
    border:1px solid #17606d;
    border-radius:10px;
    padding:4px 7px;
    font-size:8px;
}

.qgrid {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:6px;
    margin-top:9px;
}

.qnode {
    border:1px solid #1a4650;
    border-radius:6px;
    padding:8px;
    background:rgba(0,35,45,.18);
}

.qnode b {
    color:#c8edf2;
    font-size:9px;
}

.qnode small {
    display:block;
    color:#718b92;
    font-size:8px;
    margin-top:4px;
}

.qstatus {
    display:block;
    margin-top:7px;
    color:#f0c66d;
    font-size:8px;
}

.qstatus.ready {
    color:var(--green);
}

.events {
    color:#71838a;
    font-size:10px;
    line-height:1.5;
    min-height:32px;
    margin-top:9px;
}

.footer {
    color:#5f7178;
    border-top:1px solid #211219;
    margin-top:12px;
    padding:11px 3px;
    display:flex;
    justify-content:space-between;
    font-size:9px;
}

@media(max-width:1200px) {
    .cards {
        grid-template-columns:repeat(3,1fr);
    }

    .workspace {
        grid-template-columns:1fr;
    }

    .bottom-grid {
        grid-template-columns:1fr 1fr;
    }
}

@media(max-width:760px) {

    .shell {
        display:block;
    }

    .sidebar {
        height:auto;
        position:relative;
        border-right:0;
        border-bottom:1px solid #430c17;
    }

    .crest {
        display:none;
    }

    .nav {
        grid-template-columns:repeat(2,1fr);
    }

    .side-assets {
        display:none;
    }

    .main {
        padding:7px;
    }

    .hero {
        min-height:155px;
    }

    .hero-text {
        left:13px;
        top:18px;
    }

    .hero-text h1 {
        font-size:43px;
    }

    .hero-text p {
        letter-spacing:3px;
    }

    .status-area {
        left:10px;
        right:10px;
        top:auto;
        bottom:8px;
        justify-content:flex-start;
        overflow:auto;
    }

    .status-box {
        min-width:100px;
    }

    .cards {
        grid-template-columns:repeat(2,1fr);
    }

    .market-controls {
        grid-template-columns:1fr;
    }

    .chart {
        height:340px;
    }

    .chart-title {
        align-items:flex-start;
    }

    .bottom-grid {
        grid-template-columns:1fr;
    }

    .qgrid {
        grid-template-columns:1fr 1fr;
    }

    .footer {
        display:block;
        line-height:1.7;
    }
}

</style>
</head>

<body>

<div class="shell">

<aside class="sidebar">

    <div class="brand">
        ALUCARD
        <small>SIGNAL BOT</small>
    </div>

    <div class="crest">☠</div>

    <div class="nav">
        <button class="active">⌂ &nbsp; Dashboard</button>
        <button>◉ &nbsp; Signals</button>
        <button>▤ &nbsp; Trades</button>
        <button>▥ &nbsp; Performance</button>
        <button>⚙ &nbsp; Settings</button>
    </div>

    <div class="side-assets">
        <h4>MARKET CATALOG</h4>
        <button onclick="focusGroup('FOREX')">◉ Forex</button>
        <button onclick="focusGroup('OTC FOREX')">◉ OTC Forex</button>
        <button onclick="focusGroup('CRYPTO')">₿ Crypto</button>
        <button onclick="focusGroup('STOCKS')">▥ Stocks</button>
        <button onclick="focusGroup('COMMODITIES')">◌ Commodities</button>
        <button onclick="focusGroup('INDICES')">◎ Indices</button>
    </div>

</aside>


<main class="main">

<section class="hero">

    <div class="hero-text">
        <h1>ALUCARD</h1>
        <p>SIGNAL BOT</p>
        <small>GOTHIC MARKET INTELLIGENCE • V3</small>
    </div>

    <div class="status-area">

        <div id="feedStatus"
             class="status-box live-status">

            <div class="status-label">
                MARKET FEED
            </div>

            <div id="feedValue"
                 class="status-value">
                WAITING
            </div>

        </div>


        <div class="status-box">

            <div class="status-label">
                REAL WORLD TIME
            </div>

            <div id="worldClock"
                 class="status-value">
                --:--:--
            </div>

        </div>


        <div class="status-box">

            <div class="status-label">
                ENTRY COUNTDOWN
            </div>

            <div id="entryClock"
                 class="status-value red">
                WAIT
            </div>

        </div>

    </div>

</section>


<section class="cards">

    <div class="card">
        <div class="label">Account</div>
        <div class="big cyan">DEMO</div>
    </div>

    <div class="card">
        <div class="label">Balance</div>
        <div id="balance" class="big">—</div>
    </div>

    <div class="card">
        <div class="label">Open Trades</div>
        <div class="big">0 / 3</div>
    </div>

    <div class="card">
        <div class="label">Engine</div>
        <div id="engine" class="big green">
            STARTING
        </div>
    </div>

    <div class="card">
        <div class="label">Candles</div>
        <div id="candleCount" class="big">0</div>
    </div>

    <div class="card">
        <div class="label">Data Age</div>
        <div id="stale" class="big">—</div>
    </div>

</section>


<div class="workspace">


<section class="card market-card">

    <div class="market-controls">

        <select id="assetSelect">

            {% for group, assets in ASSET_GROUPS.items() %}

            <optgroup label="{{ group }}">

                {% for asset in assets %}

                <option value="{{ asset }}"
                    {% if asset == selected_asset %}
                    selected
                    {% endif %}>

                    {{ ASSET_LABELS.get(asset, asset) }}

                </option>

                {% endfor %}

            </optgroup>

            {% endfor %}

        </select>


        <input id="assetSearch"
               placeholder="Search every asset..."
               oninput="filterAssets()">


        <button class="apply"
                onclick="applyConfig()">
            APPLY
        </button>

    </div>


    <div class="tf-row">

        {% for tf in TIMEFRAMES %}

        <button
            class="tf {% if tf == selected_tf %}active{% endif %}"
            data-tf="{{ tf }}"
            onclick="chooseTimeframe('{{ tf }}')">

            {{ tf }}

        </button>

        {% endfor %}

    </div>


    <div class="chart-title">

        <div>

            <div id="assetTitle"
                 class="asset-name">

                {{ ASSET_LABELS.get(
                    selected_asset,
                    selected_asset
                ) }}

            </div>

            <div id="feedText"
                 class="asset-sub">

                Waiting for Pocket Option market data...

            </div>

        </div>


        <div class="next-box">

            <div class="label">
                NEXT CANDLE
            </div>

            <div id="nextCandle"
                 class="next-time">
                --:--
            </div>

        </div>

    </div>


    <div class="chart">

        <div class="chart-overlay">
            <span>EMA 9</span>
            <span>EMA 20</span>
            <span>EMA 50</span>
            <span>RSI</span>
            <span>MACD</span>
            <span>CCI</span>
            <span>ADX</span>
        </div>

        <svg id="chartSvg"
             viewBox="0 0 1000 400"
             preserveAspectRatio="none">
        </svg>

        <div id="chartWait"
             class="chart-wait">

            WAITING FOR LIVE CANDLE DATA

        </div>

    </div>


    <div class="bottom-grid">

        <div class="card">

            <div class="label">
                Live Signal
            </div>

            <table class="table">

                <thead>
                    <tr>
                        <th>TIME</th>
                        <th>ASSET</th>
                        <th>DIRECTION</th>
                        <th>CONF.</th>
                    </tr>
                </thead>

                <tbody id="signalRows">

                    <tr>
                        <td>—</td>
                        <td>{{ ASSET_LABELS.get(
                            selected_asset,
                            selected_asset
                        ) }}</td>
                        <td>
                            <span class="pill wait">
                                WAIT
                            </span>
                        </td>
                        <td>—</td>
                    </tr>

                </tbody>

            </table>

        </div>


        <div class="card">

            <div class="label">
                Connection
            </div>

            <div class="metric">
                <span>Stage</span>
                <b id="stage">—</b>
            </div>

            <div class="metric">
                <span>Timeframe</span>
                <b id="tfMetric">{{ selected_tf }}</b>
            </div>

            <div class="metric">
                <span>Feed</span>
                <b id="feedMetric">WAITING</b>
            </div>

            <div class="metric">
                <span>Data</span>
                <b id="dataMetric">—</b>
            </div>

        </div>


        <div class="card">

            <div class="label">
                System Events
            </div>

            <div id="events"
                 class="events">

                ALUCARD V3 initializing...

            </div>

        </div>

    </div>

</section>


<aside>

    <div class="card signal-panel">

        <div class="label">
            ALUCARD DECISION ENGINE
        </div>

        <div id="signal"
             class="signal-direction cyan">

            WAIT

        </div>

        <div class="confidence">

            CONFIDENCE:
            <b id="confidence">0.0%</b>

        </div>

        <div class="conf-bar">
            <i id="confidenceBar"></i>
        </div>


        <div class="metric">
            <span>Asset</span>
            <b id="sideAsset">—</b>
        </div>

        <div class="metric">
            <span>Timeframe</span>
            <b id="sideTf">{{ selected_tf }}</b>
        </div>

        <div class="metric">
            <span>Signal State</span>
            <b id="signalState">WAITING</b>
        </div>

        <div class="metric">
            <span>Entry Window</span>
            <b id="entryWindow">—</b>
        </div>


        <div class="action-grid">

            <button class="trade-button call"
                    onclick="manualDisplay('CALL')">
                CALL
            </button>

            <button class="trade-button put"
                    onclick="manualDisplay('PUT')">
                PUT
            </button>

        </div>


        <div class="signal-reasons"
             id="reasons">

            <div class="reason">
                Waiting for market analysis.
            </div>

        </div>


        <div id="indicators"
             class="indicators">
        </div>

    </div>


    <div class="card quantum">

        <div class="quantum-head">

            <strong>
                QUANTUM COMPUTING CLOUDS
            </strong>

            <span>
                OPTIONAL
            </span>

        </div>


        <div class="qgrid">

            {% for name, description, envkey
               in QUANTUM_CLOUDS %}

            <div class="qnode">

                <b>{{ name }}</b>

                <small>
                    {{ description }}
                </small>

                <span
                    class="qstatus"
                    data-qenv="{{ envkey }}">

                    CHECKING...

                </span>

            </div>

            {% endfor %}

        </div>

    </div>

</aside>

</div>


<div class="card quantum"
     style="margin-top:10px">

    <div class="label">
        FULL POCKET OPTION ASSET CATALOG
    </div>

    <input
        id="catalogSearch"
        class="market-controls"
        style="display:block;margin-top:8px;width:100%;color:white;background:#04080b;border:1px solid #3b1a22;border-radius:6px;padding:9px"
        placeholder="Search asset catalog..."
        oninput="filterCatalog()">


    <div id="catalog"
         style="
         display:grid;
         grid-template-columns:
         repeat(auto-fit,minmax(210px,1fr));
         gap:8px;
         margin-top:9px;
         ">

        {% for group, assets in ASSET_GROUPS.items() %}

        <div
            class="catalog-group"
            data-group="{{ group }}"
            style="
            border:1px solid #21161b;
            border-radius:6px;
            padding:9px;
            background:#05080a;
            ">

            <div style="
                color:#ff5365;
                font-size:10px;
                letter-spacing:1.4px;
                margin-bottom:7px;
                ">

                {{ group }}

            </div>

            <div style="
                color:#82949a;
                font-size:9px;
                line-height:1.7;
                ">

                {% for asset in assets %}

                <span
                    class="catalog-asset"
                    data-symbol="{{ asset }}"
                    style="
                    display:inline-block;
                    margin-right:7px;
                    cursor:pointer;
                    "
                    onclick="selectAsset('{{ asset }}')">

                    {{ ASSET_LABELS.get(asset, asset) }}

                </span>

                {% endfor %}

            </div>

        </div>

        {% endfor %}

    </div>

</div>


<footer class="footer">

    <span>
        ALUCARD V3 • GOTHIC MARKET INTELLIGENCE
    </span>

    <span>
        READ-ONLY MARKET ANALYSIS • VERSION {{ VERSION }}
    </span>

</footer>

</main>

</div>


<script>

let currentTimeframe =
    "{{ selected_tf }}";

let signalCountdownEnd = null;
let lastSignalKey = "";
let lastSignalDirection = "WAIT";


const periodSeconds = {{ PERIODS | tojson }};


function chooseTimeframe(tf) {

    currentTimeframe = tf;

    document
        .querySelectorAll(".tf")
        .forEach(button => {

            button.classList.toggle(
                "active",
                button.dataset.tf === tf
            );

        });

    document.getElementById(
        "tfMetric"
    ).textContent = tf;

    document.getElementById(
        "sideTf"
    ).textContent = tf;

}


function selectAsset(asset) {

    document.getElementById(
        "assetSelect"
    ).value = asset;

    applyConfig();

}


async function applyConfig() {

    const asset =
        document.getElementById(
            "assetSelect"
        ).value;

    const response =
        await fetch(
            "/api/configure",
            {
                method:"POST",
                headers:{
                    "Content-Type":
                        "application/json"
                },
                body:JSON.stringify({
                    asset:asset,
                    timeframe:currentTimeframe
                })
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        document.getElementById(
            "events"
        ).textContent =
            data.error ||
            "Configuration rejected.";

        return;

    }

    document.getElementById(
        "events"
    ).textContent =
        "Configuration applied: " +
        asset +
        " / " +
        currentTimeframe;

    refresh();

}


function filterAssets() {

    const query =
        document.getElementById(
            "assetSearch"
        ).value
        .toLowerCase()
        .trim();

    document
        .querySelectorAll(
            "#assetSelect option"
        )
        .forEach(option => {

            option.hidden =
                query.length > 0 &&
                !option.textContent
                    .toLowerCase()
                    .includes(query);

        });

}


function filterCatalog() {

    const query =
        document.getElementById(
            "catalogSearch"
        ).value
        .toLowerCase()
        .trim();

    document
        .querySelectorAll(
            ".catalog-group"
        )
        .forEach(group => {

            let visible = false;

            group
                .querySelectorAll(
                    ".catalog-asset"
                )
                .forEach(item => {

                    const match =
                        !query ||
                        item.textContent
                            .toLowerCase()
                            .includes(query);

                    item.style.display =
                        match
                        ? "inline-block"
                        : "none";

                    if (match)
                        visible = true;

                });

            group.style.display =
                visible
                ? "block"
                : "none";

        });

}


function focusGroup(name) {

    const groups =
        document.querySelectorAll(
            ".catalog-group"
        );

    groups.forEach(group => {

        if (group.dataset.group === name) {

            group.scrollIntoView({
                behavior:"smooth",
                block:"center"
            });

        }

    });

}


function drawChart(candles) {

    const svg =
        document.getElementById(
            "chartSvg"
        );

    const wait =
        document.getElementById(
            "chartWait"
        );

    if (!candles ||
        candles.length < 2) {

        svg.innerHTML = "";
        wait.style.display = "grid";
        return;

    }

    wait.style.display = "none";

    const data =
        candles.slice(-90);

    const lows =
        data.map(c => Number(c.low));

    const highs =
        data.map(c => Number(c.high));

    const lo =
        Math.min(...lows);

    const hi =
        Math.max(...highs);

    const span =
        (hi - lo) || 1;

    const width = 1000;
    const height = 400;

    const left = 20;
    const right = 15;
    const top = 25;
    const bottom = 20;

    const x = i =>
        left +
        i *
        ((width-left-right) /
        Math.max(1,data.length-1));

    const y = value =>
        top +
        (hi-value) *
        ((height-top-bottom)/span);

    let html = "";

    data.forEach((candle,i) => {

        const xx = x(i);

        const open =
            y(Number(candle.open));

        const close =
            y(Number(candle.close));

        const high =
            y(Number(candle.high));

        const low =
            y(Number(candle.low));

        const bullish =
            Number(candle.close) >=
            Number(candle.open);

        const color =
            bullish
            ? "#00ff91"
            : "#ff3045";

        const body =
            Math.max(
                2,
                Math.abs(close-open)
            );

        html +=
            '<line ' +
            'x1="'+xx+'" ' +
            'y1="'+high+'" ' +
            'x2="'+xx+'" ' +
            'y2="'+low+'" ' +
            'stroke="'+color+'" ' +
            'stroke-width="1"/>' +

            '<rect ' +
            'x="'+(xx-3)+'" ' +
            'y="'+Math.min(open,close)+'" ' +
            'width="6" ' +
            'height="'+body+'" ' +
            'fill="'+color+'"/>';
    });

    svg.innerHTML = html;

}


function setSignal(signal) {

    if (!signal) {

        signal = {
            direction:"WAIT",
            confidence:0,
            reasons:[
                "Waiting for market data."
            ],
            indicators:{}
        };

    }

    const direction =
        signal.direction || "WAIT";

    const confidence =
        Number(signal.confidence || 0);

    const reasons =
        signal.reasons || [];

    const key =
        direction +
        "|" +
        confidence +
        "|" +
        reasons.join("|");


    if (
        (direction === "CALL" ||
         direction === "PUT") &&
        key !== lastSignalKey
    ) {

        signalCountdownEnd =
            Date.now() + 12000;

        lastSignalKey = key;

    }

    if (direction === "WAIT") {

        signalCountdownEnd = null;
        lastSignalKey = key;

    }


    const signalElement =
        document.getElementById(
            "signal"
        );

    signalElement.textContent =
        direction;

    signalElement.className =
        "signal-direction " +
        (
            direction === "CALL"
            ? "green"
            : direction === "PUT"
            ? "red"
            : "cyan"
        );


    document.getElementById(
        "confidence"
    ).textContent =
        confidence.toFixed(1) + "%";


    document.getElementById(
        "confidenceBar"
    ).style.width =
        Math.max(
            0,
            Math.min(
                100,
                confidence
            )
        ) + "%";


    document.getElementById(
        "signalState"
    ).textContent =
        direction;


    document.getElementById(
        "reasons"
    ).innerHTML =
        (
            reasons.length
            ? reasons
            : ["Waiting for market analysis."]
        )
        .map(reason =>
            '<div class="reason">' +
            escapeHtml(reason) +
            '</div>'
        )
        .join("");


    const indicators =
        signal.indicators || {};

    document.getElementById(
        "indicators"
    ).innerHTML =
        Object.entries(indicators)
        .slice(0,12)
        .map(([key,value]) => {

            let shown = "—";

            if (
                value !== null &&
                value !== undefined &&
                !Number.isNaN(Number(value))
            ) {

                shown =
                    Number(value)
                    .toFixed(4);

            }

            return `
                <div class="indicator">
                    <b>${escapeHtml(
                        key.toUpperCase()
                    )}</b>
                    <span>${shown}</span>
                </div>
            `;

        })
        .join("");


    const assetTitle =
        document.getElementById(
            "assetTitle"
        ).textContent;


    document.getElementById(
        "sideAsset"
    ).textContent =
        assetTitle;


    document.getElementById(
        "signalRows"
    ).innerHTML = `

        <tr>

            <td>
                ${new Date()
                    .toLocaleTimeString()}
            </td>

            <td>
                ${escapeHtml(assetTitle)}
            </td>

            <td>
                <span class="pill ${
                    direction.toLowerCase()
                }">
                    ${direction}
                </span>
            </td>

            <td>
                ${confidence.toFixed(1)}%
            </td>

        </tr>

    `;

}


function escapeHtml(value) {

    return String(value)
        .replaceAll("&","&amp;")
        .replaceAll("<","&lt;")
        .replaceAll(">","&gt;")
        .replaceAll('"',"&quot;")
        .replaceAll("'","&#039;");

}


function updateCountdown() {

    const entry =
        document.getElementById(
            "entryClock"
        );

    const next =
        document.getElementById(
            "nextCandle"
        );

    if (!signalCountdownEnd) {

        entry.textContent =
            lastSignalDirection === "WAIT"
            ? "WAIT"
            : "WAIT";

    } else {

        const remaining =
            Math.max(
                0,
                Math.ceil(
                    (signalCountdownEnd -
                    Date.now()) / 1000
                )
            );

        if (remaining > 0) {

            entry.textContent =
                remaining + "s";

        } else {

            entry.textContent =
                "TOO LATE";

            entry.className =
                "status-value red";

        }

    }


    const seconds =
        periodSeconds[currentTimeframe]
        || 60;

    const remainingCandle =
        Math.max(
            0,
            Math.ceil(
                seconds -
                (
                    Date.now()/1000
                ) % seconds
            )
        );

    const mins =
        Math.floor(
            remainingCandle / 60
        );

    const secs =
        remainingCandle % 60;

    next.textContent =
        String(mins).padStart(2,"0") +
        ":" +
        String(secs).padStart(2,"0");

}


function manualDisplay(direction) {

    document.getElementById(
        "events"
    ).textContent =
        direction +
        " display control only — " +
        "ALUCARD does not place orders.";

}


function updateWorldClock() {

    document.getElementById(
        "worldClock"
    ).textContent =
        new Date().toLocaleTimeString();

}


async function quantumStatus() {

    try {

        const response =
            await fetch(
                "/api/quantum-status",
                {cache:"no-store"}
            );

        const data =
            await response.json();

        document
            .querySelectorAll(
                "[data-qenv]"
            )
            .forEach(element => {

                const ready =
                    Boolean(
                        data[
                            element.dataset.qenv
                        ]
                    );

                element.textContent =
                    ready
                    ? "CONFIGURED"
                    : "OPTIONAL / NOT CONFIGURED";

                element.className =
                    "qstatus " +
                    (
                        ready
                        ? "ready"
                        : ""
                    );

            });

    } catch(error) {

        console.log(
            "Quantum status unavailable"
        );

    }

}


async function refresh() {

    try {

        const response =
            await fetch(
                "/api/state",
                {cache:"no-store"}
            );

        const data =
            await response.json();


        const connected =
            Boolean(data.connected);


        const feedStatus =
            document.getElementById(
                "feedStatus"
            );

        const feedValue =
            document.getElementById(
                "feedValue"
            );


        feedValue.textContent =
            connected
            ? "LIVE"
            : "WAITING";


        feedStatus.className =
            "status-box " +
            (
                connected
                ? "live-status"
                : "offline-status"
            );


        document.getElementById(
            "engine"
        ).textContent =
            data.engine || "WAITING";


        document.getElementById(
            "feedMetric"
        ).textContent =
            connected
            ? "CONNECTED"
            : "WAITING";


        document.getElementById(
            "dataMetric"
        ).textContent =
            data.candles || 0;


        document.getElementById(
            "candleCount"
        ).textContent =
            data.candles || 0;


        document.getElementById(
            "stale"
        ).textContent =
            data.stale_seconds == null
            ? "—"
            : Number(
                data.stale_seconds
            ).toFixed(1) + "s";


        document.getElementById(
            "stage"
        ).textContent =
            data.connection_stage ||
            "—";


        document.getElementById(
            "feedText"
        ).textContent =
            connected
            ? "Pocket Option market-data stream connected"
            : (
                data.error ||
                "Waiting for Pocket Option market data..."
            );


        const label =
            data.asset || "{{ selected_asset }}";

        document.getElementById(
            "assetTitle"
        ).textContent =
            {{ ASSET_LABELS | tojson }}[label]
            || label;


        currentTimeframe =
            data.timeframe ||
            currentTimeframe;


        chooseTimeframe(
            currentTimeframe
        );


        drawChart(
            data.candle_data || []
        );


        lastSignalDirection =
            data.signal?.direction ||
            "WAIT";


        setSignal(
            data.signal
        );


        if (data.error) {

            document.getElementById(
                "events"
            ).textContent =
                data.error;

        }


    } catch(error) {

        document.getElementById(
            "feedValue"
        ).textContent =
            "ERROR";

        document.getElementById(
            "engine"
        ).textContent =
            "OFFLINE";

        document.getElementById(
            "events"
        ).textContent =
            "Dashboard connection error: " +
            error.message;

    }

}


setInterval(
    updateWorldClock,
    250
);

setInterval(
    updateCountdown,
    250
);

setInterval(
    refresh,
    2000
);

setInterval(
    quantumStatus,
    10000
);


updateWorldClock();
updateCountdown();
refresh();
quantumStatus();

</script>

</body>
</html>
"""


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/")
def dashboard():

    return render_template_string(
        HTML,
        TIMEFRAMES=TIMEFRAMES,
        PERIODS=PERIODS,
        ASSET_GROUPS=ASSET_GROUPS,
        ASSET_LABELS=ASSET_LABELS,
        QUANTUM_CLOUDS=QUANTUM_CLOUDS,
        selected_asset=service.asset
        if getattr(service, "asset", None)
        else DEFAULT_ASSET,
        selected_tf=service.timeframe
        if getattr(service, "timeframe", None)
        else DEFAULT_TIMEFRAME,
        VERSION=VERSION,
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    service.start()

    snapshot = service.snapshot()

    return jsonify({
        "service": APP_NAME,
        "version": VERSION,
        "status": "ok",
        "feed": (
            "live"
            if snapshot.get("connected")
            else "offline"
        ),
        "engine": snapshot.get(
            "engine",
            "WAITING"
        ),
        "configured": snapshot.get(
            "configured",
            False
        ),
    })


# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
def config():

    return jsonify({
        "name": APP_NAME,
        "subtitle": APP_SUBTITLE,
        "version": VERSION,
        "timeframes": TIMEFRAMES,
        "periods": PERIODS,
        "asset_groups": ASSET_GROUPS,
        "asset_labels": ASSET_LABELS,
        "asset_count": len(VALID_ASSETS),
        "quantum_clouds": [
            name
            for name, _, _ in QUANTUM_CLOUDS
        ],
    })


# ============================================================
# QUANTUM STATUS
# ============================================================

@app.get("/api/quantum-status")
def quantum_status():

    return jsonify({
        key: bool(os.getenv(key))
        for _, _, key in QUANTUM_CLOUDS
    })


# ============================================================
# LIVE STATE
# ============================================================

@app.get("/api/state")
def state():

    service.start()

    snapshot = service.snapshot()

    snapshot["timeframe"] = (
        service.timeframe
    )

    snapshot["asset_label"] = (
        ASSET_LABELS.get(
            service.asset,
            service.asset
        )
    )

    return jsonify(snapshot)


# ============================================================
# CONFIGURE ASSET / TIMEFRAME
# ============================================================

@app.post("/api/configure")
def configure():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    asset = str(
        data.get(
            "asset",
            service.asset
        )
    ).strip()

    timeframe = str(
        data.get(
            "timeframe",
            service.timeframe
        )
    ).strip()


    if asset not in VALID_ASSETS:

        return jsonify({
            "ok": False,
            "error":
                "Invalid Pocket Option asset."
        }), 400


    if timeframe not in TIMEFRAMES:

        return jsonify({
            "ok": False,
            "error":
                "Invalid timeframe."
        }), 400


    try:

        service.configure(
            asset,
            timeframe
        )

    except Exception as exc:

        return jsonify({
            "ok": False,
            "error": str(exc)[:300]
        }), 500


    return jsonify({
        "ok": True,
        "asset": asset,
        "asset_label":
            ASSET_LABELS.get(
                asset,
                asset
            ),
        "timeframe": timeframe,
        "period":
            PERIODS[timeframe],
    })


# ============================================================
# SIMPLE SERVER-INFO ENDPOINT
# ============================================================

@app.get("/api/info")
def info():

    return jsonify({
        "name": APP_NAME,
        "version": VERSION,
        "utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "asset": service.asset,
        "timeframe": service.timeframe,
        "assets": len(VALID_ASSETS),
        "timeframes": len(TIMEFRAMES),
        "read_only": True,
    })


# ============================================================
# LOCAL START
# ============================================================

if __name__ == "__main__":

    service.start()

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
