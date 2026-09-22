import os
from flask import Flask, jsonify, render_template_string, request
from signal_service import service

app = Flask(__name__)
APP_NAME = "ALUCARD V3"
APP_SUBTITLE = "GOTHIC MARKET INTELLIGENCE"
VERSION = "3.1.0"

# Pocket Option exposes very short chart intervals through longer intervals.
# The catalog is intentionally broad so the dashboard is not limited to the
# small starter list used by the first V3 build.
TIMEFRAMES = [
    "5s", "10s", "15s", "30s",
    "1m", "2m", "3m", "5m", "15m", "30m",
    "1h", "4h", "1d", "1w", "1mo"
]

ASSET_GROUPS = {
    "FOREX": [
        "EURUSD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDUSD",
        "CADCHF", "CADJPY", "CHFJPY", "EURAUD", "EURCAD",
        "EURCHF", "EURGBP", "EURJPY", "GBP/AUD", "GBPCAD",
        "GBPCHF", "GBPJPY", "GBPUSD", "USDCAD", "USDCHF", "USDJPY"
    ],
    "OTC FOREX": [
        "EURUSD_otc", "AUDCAD_otc", "AUDCHF_otc", "AUDJPY_otc", "AUDNZD_otc", "AUDUSD_otc",
        "CADCHF_otc", "CADJPY_otc", "CHFJPY_otc", "CHFNOK_otc",
        "EURCHF_otc", "EURGBP_otc", "EURJPY_otc", "EURNZD_otc", "EURRUB_otc", "EURTRY_otc", "EURHUF_otc",
        "GBPAUD_otc", "GBPJPY_otc", "GBPUSD_otc",
        "NZDJPY_otc", "NZDUSD_otc",
        "USDCAD_otc", "USDCHF_otc", "USDJPY_otc", "USDRUB_otc",
        "USDCNH_otc", "USDINR_otc", "USDSGD_otc", "USDCLP_otc", "USDTHB_otc", "USDMYR_otc",
        "USDVND_otc", "USDPKR_otc", "USDCOP_otc", "USDPHP_otc", "USDMXN_otc",
        "USDIDR_otc", "USDARS_otc", "USDBRL_otc", "USDBDT_otc", "USDDZD_otc", "USDEGP_otc",
        "ZARUSD_otc", "UAHUSD_otc", "YERUSD_otc", "NGNUSD_otc", "TNDUSD_otc", "MADUSD_otc", "LBPUSD_otc",
        "BHDCNY_otc", "AEDCNY_otc", "SARCNY_otc", "QARCNY_otc", "OMRCNY_otc", "JODCNY_otc", "KESUSD_otc"
    ],
    "COMMODITIES": [
        "XAUUSD", "XAGUSD", "USOIL", "UKOIL", "NATGAS"
    ],
    "OTC COMMODITIES": [
        "XAUUSD_otc", "UKOIL_otc", "USOIL_otc", "XAGUSD_otc",
        "NATGAS_otc", "PLATINUM_otc", "PALLADIUM_otc"
    ],
    "CRYPTO": [
        "BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "BCHUSD", "DOGEUSD",
        "ADAUSD", "SOLUSD", "DOTUSD", "LINKUSD", "AVAXUSD", "BNB",
        "TRXUSD", "MATICUSD", "DASHUSD", "BTCJPY", "BTCGBP",
        "BCHJPY", "BCHGBP", "BCHEUR", "LINKUSD"
    ],
    "OTC CRYPTO": [
        "BTCUSD_otc", "ETHUSD_otc", "LTCUSD_otc", "XRPUSD_otc", "BCHUSD_otc",
        "DOGEUSD_otc", "ADAUSD_otc", "SOLUSD_otc", "DOTUSD_otc", "LINKUSD_otc",
        "AVAXUSD_otc", "BNB_otc", "TRXUSD_otc", "MATICUSD_otc", "TONUSD_otc",
        "BTCETF_otc", "DASHUSD_otc"
    ],
    "STOCKS": [
        "AAPL", "BA", "JPM", "MCD", "META", "VISA", "PFE", "BABA", "CSCO",
        "TSLA", "INTC", "AXP", "XOM", "C", "GME", "AMD", "MSFT", "PLTR",
        "NFLX", "MARA", "JNJ", "AMZN", "COIN", "GOOGL", "NVDA"
    ],
    "OTC STOCKS": [
        "AAPL_otc", "BA_otc", "JPM_otc", "MCD_otc", "META_otc", "VISA_otc",
        "PFE_otc", "BABA_otc", "CSCO_otc", "TSLA_otc", "INTC_otc", "AXP_otc",
        "XOM_otc", "C_otc", "GME_otc", "AMD_otc", "MSFT_otc", "PLTR_otc",
        "NFLX_otc", "MARA_otc", "JNJ_otc", "AMZN_otc", "COIN_otc", "GOOGL_otc", "NVDA_otc"
    ],
    "INDICES": [
        "US100", "100GBP", "JPN225", "D30EUR", "E50EUR",
        "SP500", "DJI30", "CAC40", "HONGKONG33", "AUS200"
    ],
    "OTC INDICES": [
        "AUS200_otc", "E35EUR_otc", "100GBP_otc", "F40EUR_otc",
        "JPN225_otc", "D30EUR_otc", "E50EUR_otc", "SP500_otc",
        "DJI30_otc", "US100_otc"
    ],
}

ASSET_LABELS = {}
for _group, _assets in ASSET_GROUPS.items():
    for _asset in _assets:
        if _asset.endswith("_otc"):
            ASSET_LABELS[_asset] = _asset[:-4].replace("USD", "/USD").replace("EUR", "/EUR").replace("GBP", "/GBP").replace("JPY", "/JPY") + " OTC"
        else:
            ASSET_LABELS[_asset] = _asset

# Friendly names for the most common symbols.
ASSET_LABELS.update({
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
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "USDJPY": "USD/JPY",
})

QUANTUM_CLOUDS = [
    ("IBM QUANTUM", "Qiskit / Quantum Compute", "IBM_QUANTUM_API_TOKEN"),
    ("AWS BRAKET", "Managed QPUs + simulators", "AWS_ACCESS_KEY_ID"),
    ("AZURE QUANTUM", "Hybrid quantum cloud", "AZURE_QUANTUM_RESOURCE_ID"),
    ("GOOGLE QUANTUM AI", "Quantum Engine / Cirq", "GOOGLE_CLOUD_PROJECT"),
]

HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ALUCARD V3 • Gothic Market Intelligence</title>
<style>
:root{
 --bg:#040508;--panel:#080b0e;--panel2:#0b1114;--red:#ff1028;--red2:#8d0015;
 --green:#00ff91;--cyan:#27d9ff;--blue:#0e82ff;--text:#eaf2f5;--muted:#71818a;
 --line:#241018;--gold:#e7c77b;
}
*{box-sizing:border-box}
body{
 margin:0;background:
 radial-gradient(circle at 75% 4%,rgba(110,0,0,.42),transparent 30%),
 radial-gradient(circle at 15% 40%,rgba(0,90,90,.13),transparent 35%),
 linear-gradient(135deg,#030407,#09080c 50%,#030406);
 color:var(--text);font-family:Inter,Arial,sans-serif;min-height:100vh;
}
body:before{
 content:"";position:fixed;inset:0;pointer-events:none;opacity:.18;
 background-image:linear-gradient(rgba(255,0,0,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,0,0,.03) 1px,transparent 1px);
 background-size:40px 40px;mix-blend-mode:screen;
}
a{color:inherit}
.shell{display:grid;grid-template-columns:210px 1fr;min-height:100vh}
.sidebar{border-right:1px solid #3a0b13;background:linear-gradient(180deg,#07070a,#0b090d 65%,#060608);padding:18px 12px;position:sticky;top:0;height:100vh}
.brand{font-family:Georgia,serif;font-size:30px;color:#ff152b;text-shadow:0 0 16px rgba(255,0,30,.5);letter-spacing:1px;text-align:center}
.brand small{display:block;color:#d9e7eb;font:12px Arial;letter-spacing:4px;margin-top:4px}
.crest{height:120px;margin:18px 0;background:radial-gradient(circle at 50% 40%,rgba(255,0,30,.25),transparent 55%),linear-gradient(135deg,#210008,#050508);border:1px solid #5d101c;border-radius:8px;display:grid;place-items:center;color:#ff1028;font-size:58px}
.nav{display:grid;gap:7px}
.nav button{border:1px solid transparent;background:transparent;color:#a9bac0;text-align:left;padding:12px 13px;border-radius:8px;font-size:15px;cursor:pointer}
.nav button:hover,.nav button.active{color:#fff;background:linear-gradient(90deg,rgba(255,0,35,.22),transparent);border-color:#780f1c;box-shadow:inset 3px 0 0 var(--red)}
.asset-nav{margin-top:18px;padding-top:14px;border-top:1px solid #3b1018}
.asset-nav h4{margin:0 0 8px;color:#8fa1a8;font-size:11px;letter-spacing:2px}
.asset-nav button{width:100%;border:0;background:none;color:#9fb0b6;padding:7px 8px;text-align:left;cursor:pointer}
.main{min-width:0;padding:12px 14px 24px}
.topbar{min-height:154px;border:1px solid #410b14;border-radius:10px;overflow:hidden;position:relative;background:
 radial-gradient(circle at 35% 30%,rgba(120,0,20,.5),transparent 38%),
 linear-gradient(110deg,#0b0508,#16070b 45%,#050607);}
.topbar:after{content:"";position:absolute;inset:auto 0 0;height:1px;background:linear-gradient(90deg,transparent,var(--red),transparent)}
.hero{position:absolute;left:25px;top:20px;z-index:2}
.hero h1{margin:0;font:70px/1 Georgia,serif;color:#ff182b;letter-spacing:2px;text-shadow:0 0 25px rgba(255,0,0,.4)}
.hero p{margin:10px 0 0 118px;color:#c8d5da;letter-spacing:4px;font-size:14px}
.hero .sub{margin-left:118px;color:#85939a;font-size:11px;letter-spacing:5px;margin-top:8px}
.top-status{position:absolute;right:18px;top:22px;display:flex;gap:12px;align-items:center;z-index:3}
.live{border:1px solid #006e50;background:rgba(0,35,24,.7);padding:9px 14px;border-radius:7px;color:var(--green);font-weight:700}
.clock{border:1px solid #6d111d;padding:9px 12px;border-radius:7px;color:#d4e0e5;background:#05070a}
.cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:10px 0}
.card{background:linear-gradient(145deg,rgba(12,15,18,.97),rgba(6,8,10,.98));border:1px solid #3b1119;border-radius:9px;padding:11px;box-shadow:0 0 18px rgba(0,0,0,.35)}
.card .label{font-size:10px;letter-spacing:1.6px;color:#829098;text-transform:uppercase}
.card .big{font-size:20px;margin-top:7px;color:#f1f5f6}.green{color:var(--green)!important}.red{color:#ff3445!important}.cyan{color:var(--cyan)!important}
.workspace{display:grid;grid-template-columns:1fr 315px;gap:10px}
.chart-card{min-width:0}
.chart-head{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;margin-bottom:9px}
.asset-title{font-size:19px;font-weight:700;white-space:nowrap}
.asset-title small{color:#8b9aa0;font-size:11px}
.tfbar{display:flex;gap:4px;flex-wrap:wrap}
.tfbar button{border:1px solid #28343a;background:#071015;color:#b6c5ca;border-radius:5px;padding:7px 10px;font-size:12px;cursor:pointer}
.tfbar button.active{color:#fff;border-color:#c10c21;background:rgba(115,0,17,.45);box-shadow:0 0 10px rgba(255,0,30,.15)}
.selectbox{position:relative}
.selectbox select,.search{background:#05080b;color:#eaf1f4;border:1px solid #51202a;border-radius:6px;padding:9px;width:100%}
.market-row{display:grid;grid-template-columns:1fr 180px 90px;gap:7px;margin-bottom:8px}
.chart{
 height:420px;border:1px solid #4a111b;border-radius:6px;position:relative;overflow:hidden;
 background:
 linear-gradient(rgba(0,160,160,.09) 1px,transparent 1px),
 linear-gradient(90deg,rgba(0,160,160,.09) 1px,transparent 1px),
 radial-gradient(circle at 70% 20%,rgba(0,120,80,.18),transparent 28%),
 linear-gradient(135deg,#061113,#03090b 55%,#07110e);
 background-size:55px 55px,55px 55px,auto,auto;
}
.chart svg{width:100%;height:100%}
.chart-empty{position:absolute;inset:0;display:grid;place-items:center;color:#61747a;font-size:12px;letter-spacing:2px;text-transform:uppercase;background:rgba(0,0,0,.18)}
.chart-meta{position:absolute;left:10px;top:8px;right:10px;display:flex;gap:14px;flex-wrap:wrap;color:#7fdde2;font-size:11px;z-index:2}
.chart-meta span:nth-child(2){color:#b4eaa9}.chart-meta span:nth-child(3){color:#e6a7c0}.chart-meta span:nth-child(4){color:#f2d28a}
.bottom-grid{display:grid;grid-template-columns:1.2fr .9fr 1fr;gap:10px;margin-top:10px}
.table{width:100%;border-collapse:collapse;font-size:11px}.table th,.table td{padding:8px 5px;border-bottom:1px solid #172126;text-align:left}.table th{color:#75858c;font-weight:500}.pill{border-radius:5px;padding:3px 6px;border:1px solid #315;display:inline-block}.pill.live{padding:3px 6px;font-size:10px}.pill.call{color:var(--green);border-color:#08734e}.pill.put{color:#ff4052;border-color:#7c1522}.pill.wait{color:#a7c0cc;border-color:#28414d}
.signal-card{border-color:#4e101b}
.signal-title{font-size:11px;letter-spacing:1.5px;color:#8b9ba0}.signal-word{font-size:43px;font-weight:800;letter-spacing:1px;margin:8px 0;text-shadow:0 0 18px rgba(0,255,140,.16)}
.confbar{height:8px;border-radius:9px;background:#10181b;overflow:hidden;margin:8px 0 12px}.confbar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#008f64,#00ff91);box-shadow:0 0 12px #00ff91}
.metric{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #172126;font-size:12px}.metric b{color:#eef5f7}
.action-grid{display:grid;gap:7px;margin-top:12px}.action{padding:10px;border-radius:6px;border:1px solid #31414a;background:#091116;color:#cbd9de;font-weight:700}.action.call{background:linear-gradient(90deg,#087d4c,#10c96e);color:#fff;border-color:#00ff91}.action.put{background:linear-gradient(90deg,#a20d1f,#ff243d);color:#fff;border-color:#ff4a5a}
.quantum{margin-top:10px;border-color:#183e46;background:linear-gradient(145deg,#071116,#04090c)}
.quantum-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px}.quantum-head strong{letter-spacing:1.4px}.quantum-head span{color:var(--cyan);font-size:10px;border:1px solid #175e6c;padding:4px 7px;border-radius:10px}
.qgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.qnode{border:1px solid #1c4650;border-radius:7px;padding:9px;background:rgba(0,40,48,.18)}.qnode b{font-size:11px;color:#cbeff5}.qnode small{display:block;color:#718c93;margin-top:4px;font-size:9px}.qstatus{display:block;color:#a5c5cb;font-size:9px;margin-top:7px}.qstatus.ready{color:var(--green)}.qstatus.wait{color:#f0c36b}
.analysis{margin-top:10px}.analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.reason{padding:7px 0;border-bottom:1px solid #172126;color:#a9b8bd;font-size:12px}.indicators{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.mini{background:#060a0d;border:1px solid #16252a;border-radius:6px;padding:8px}.mini b{font-size:10px;color:#71868d}.mini div{font-size:13px;margin-top:4px}
.drawer{margin-top:10px}.drawer summary{cursor:pointer;color:#9eb0b6;letter-spacing:1px}.catalog{margin-top:8px;display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.catalog .group{border:1px solid #20141a;border-radius:7px;padding:8px;background:#06080a}.catalog h4{margin:0 0 5px;color:#ff5a69;font-size:10px;letter-spacing:1.4px}.catalog p{margin:0;color:#7f9197;font-size:10px;line-height:1.55}
.footer{padding:12px 4px;color:#62747b;font-size:10px;display:flex;justify-content:space-between;border-top:1px solid #1c1217;margin-top:12px}
@media(max-width:1200px){.cards{grid-template-columns:repeat(3,1fr)}.workspace{grid-template-columns:1fr}.bottom-grid{grid-template-columns:1fr 1fr}.hero h1{font-size:52px}.qgrid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.shell{display:block}.sidebar{height:auto;position:relative;border-right:0;border-bottom:1px solid #3a0b13}.crest{display:none}.nav{grid-template-columns:repeat(2,1fr)}.asset-nav{display:none}.main{padding:8px}.topbar{min-height:135px}.hero{left:14px;top:20px}.hero h1{font-size:39px}.hero p,.hero .sub{margin-left:0;letter-spacing:2px}.top-status{right:8px;top:auto;bottom:8px}.cards{grid-template-columns:repeat(2,1fr)}.chart-head{grid-template-columns:1fr}.market-row{grid-template-columns:1fr}.bottom-grid,.analysis-grid{grid-template-columns:1fr}.qgrid{grid-template-columns:1fr 1fr}.footer{display:block}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand">ALUCARD<small>SIGNAL BOT</small></div>
  <div class="crest">☠</div>
  <div class="nav">
    <button class="active">⌂ &nbsp; Dashboard</button>
    <button>◉ &nbsp; Signals</button>
    <button>▤ &nbsp; Trades</button>
    <button>▥ &nbsp; Performance</button>
    <button>⚙ &nbsp; Settings</button>
  </div>
  <div class="asset-nav">
    <h4>ASSETS</h4>
    <button onclick="jumpGroup('FOREX')">◉ &nbsp; Forex</button>
    <button onclick="jumpGroup('CRYPTO')">₿ &nbsp; Crypto</button>
    <button onclick="jumpGroup('STOCKS')">▥ &nbsp; Stocks</button>
    <button onclick="jumpGroup('COMMODITIES')">◌ &nbsp; Commodities</button>
    <button onclick="jumpGroup('INDICES')">◎ &nbsp; Indices</button>
  </div>
</aside>

<main class="main">
  <section class="topbar">
    <div class="hero">
      <h1>ALUCARD</h1>
      <p>SIGNAL BOT</p>
      <div class="sub">GOTHIC MARKET INTELLIGENCE</div>
    </div>
    <div class="top-status">
      <div id="liveBadge" class="live">● LIVE<br><span style="font-weight:400">Market Feed</span></div>
      <div class="clock" id="clock">--:--:--</div>
    </div>
  </section>

  <section class="cards">
    <div class="card"><div class="label">Account</div><div class="big cyan">DEMO</div></div>
    <div class="card"><div class="label">Balance</div><div class="big">—</div></div>
    <div class="card"><div class="label">Open Trades</div><div class="big">0 / 3</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="big green">—</div></div>
    <div class="card"><div class="label">Total P/L</div><div class="big green">—</div></div>
    <div class="card"><div class="label">AI Engine</div><div id="engineTop" class="big green">STARTING</div></div>
  </section>

  <div class="workspace">
    <section>
      <div class="card chart-card">
        <div class="market-row">
          <div class="selectbox">
            <select id="assetSelect">
              {% for group,assets in ASSET_GROUPS.items() %}
              <optgroup label="{{group}}">
                {% for asset in assets %}
                <option value="{{asset}}" {% if asset==selected_asset %}selected{% endif %}>{{ASSET_LABELS.get(asset, asset)}}</option>
                {% endfor %}
              </optgroup>
              {% endfor %}
            </select>
          </div>
          <input id="assetSearch" class="search" placeholder="Search every asset…" oninput="filterAssets()">
          <button class="action" onclick="applySettings()">APPLY</button>
        </div>

        <div class="chart-head">
          <div class="asset-title"><span id="assetTitle">EUR/USD OTC</span><br><small id="feedText">Pocket Option market-data stream</small></div>
          <div class="tfbar">
            {% for tf in TIMEFRAMES %}
            <button class="tfbtn {% if tf==selected_tf %}active{% endif %}" data-tf="{{tf}}" onclick="pickTf('{{tf}}')">{{tf}}</button>
            {% endfor %}
          </div>
          <div style="text-align:right"><div class="label">NEXT SIGNAL</div><div id="countdown" class="big red">--:--</div></div>
        </div>

        <div class="chart">
          <div class="chart-meta">
            <span>EMA 9 20 50</span><span>◆ ALLIGATOR</span><span>◆ PSAR</span><span>◆ MACD 12 26 9</span><span>◆ CCI (14)</span>
          </div>
          <svg id="chartSvg" viewBox="0 0 1000 400" preserveAspectRatio="none"></svg>
          <div id="chartEmpty" class="chart-empty">Waiting for live candle data…</div>
        </div>
      </div>

      <div class="bottom-grid">
        <div class="card">
          <div class="label">Live Signals</div>
          <table class="table"><thead><tr><th>Time</th><th>Asset</th><th>Direction</th><th>Confidence</th><th>Status</th></tr></thead>
          <tbody id="signalRows"><tr><td>—</td><td id="rowAsset">EUR/USD OTC</td><td><span class="pill wait">WAIT</span></td><td>—</td><td><span class="pill">LIVE</span></td></tr></tbody></table>
        </div>
        <div class="card">
          <div class="label">Performance</div>
          <div class="metric"><span>Data candles</span><b id="candleCount">0</b></div>
          <div class="metric"><span>Stale seconds</span><b id="stale">—</b></div>
          <div class="metric"><span>Connection stage</span><b id="stage">—</b></div>
          <div class="metric"><span>Timeframe</span><b id="tfMetric">1m</b></div>
        </div>
        <div class="card">
          <div class="label">Recent Engine Events</div>
          <div id="events" class="reason">Booting ALUCARD V3…</div>
        </div>
      </div>
    </section>

    <aside>
      <div class="card signal-card">
        <div class="signal-title">☠ AI SIGNAL</div>
        <div id="signal" class="signal-word green">WAIT</div>
        <div class="metric"><span>Confidence</span><b id="confidence">0%</b></div>
        <div class="confbar"><i id="confFill"></i></div>
        <div class="metric"><span>Market feed</span><b id="feedState">CONNECTING</b></div>
        <div class="metric"><span>Entry window</span><b id="entryWindow">—</b></div>
        <div class="metric"><span>Chart timeframe</span><b id="sideTf">1m</b></div>
        <div class="action-grid">
          <div class="action call">↗ CALL</div>
          <div class="action put">↘ PUT</div>
          <div class="action">◷ WAIT</div>
        </div>
        <div class="muted" style="font-size:9px;margin-top:9px">Signal controls are display-only. ALUCARD V3 does not place trades.</div>
      </div>

      <div class="card quantum">
        <div class="quantum-head"><strong>⚛ QUANTUM CLOUD LAYER</strong><span>EXPERIMENTAL</span></div>
        <div class="qgrid">
          {% for name,desc,envkey in QUANTUM_CLOUDS %}
          <div class="qnode">
            <b>{{name}}</b><small>{{desc}}</small>
            <span class="qstatus wait" data-qenv="{{envkey}}">CHECKING</span>
          </div>
          {% endfor %}
        </div>
        <div class="muted" style="font-size:9px;margin-top:8px">
          Quantum providers are optional research/ensemble inputs. A quantum score is not a guaranteed win probability.
        </div>
      </div>

      <div class="card analysis">
        <div class="label">Analysis</div>
        <div id="reasons"><div class="reason">No live analysis yet.</div></div>
        <div class="label" style="margin-top:12px">Indicators</div>
        <div id="indicators" class="indicators"></div>
      </div>
    </aside>
  </div>

  <details class="card drawer">
    <summary>FULL POCKET OPTION ASSET CATALOG • {% set total=namespace(n=0) %}{% for g,a in ASSET_GROUPS.items() %}{% set total.n=total.n+a|length %}{% endfor %}{{total.n}} dashboard symbols</summary>
    <div class="catalog">
      {% for group,assets in ASSET_GROUPS.items() %}
      <div class="group" id="group-{{group|replace(' ','-')}}">
        <h4>{{group}}</h4>
        <p>{% for asset in assets %}{{ASSET_LABELS.get(asset,asset)}}{% if not loop.last %} • {% endif %}{% endfor %}</p>
      </div>
      {% endfor %}
    </div>
  </details>

  <div class="footer">
    <span>ALUCARD SIGNAL BOT v{{VERSION}} &nbsp;|&nbsp; Powered by AI &nbsp;|&nbsp; Pocket Option market data</span>
    <span>LIVE MARKET DATA &nbsp;•&nbsp; QUANTUM CLOUD LAYER &nbsp;•&nbsp; SIGNAL ENGINE</span>
  </div>
</main>
</div>

<script>
const periodSeconds = {{ PERIODS|tojson }};
let currentTf = {{ selected_tf|tojson }};
let lastDirection = "WAIT";

function pad(n){return String(n).padStart(2,"0")}
function clock(){
  const d=new Date();
  document.getElementById("clock").textContent =
    d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())+"  "+pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds());
}
setInterval(clock,1000); clock();

function pickTf(tf){
  currentTf=tf;
  document.querySelectorAll(".tfbtn").forEach(b=>b.classList.toggle("active",b.dataset.tf===tf));
  document.getElementById("tfMetric").textContent=tf;
  document.getElementById("sideTf").textContent=tf;
}

function filterAssets(){
  const q=document.getElementById("assetSearch").value.toLowerCase();
  const select=document.getElementById("assetSelect");
  [...select.options].forEach(o=>{
    const show=!q || o.text.toLowerCase().includes(q) || o.value.toLowerCase().includes(q);
    o.hidden=!show;
  });
}

async function applySettings(){
  const asset=document.getElementById("assetSelect").value;
  const tf=currentTf;
  const r=await fetch("/api/configure",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({asset,timeframe:tf})});
  const d=await r.json();
  if(!r.ok){document.getElementById("events").textContent=d.error||"Configuration rejected";return}
  document.getElementById("events").textContent="Configuration applied: "+asset+" / "+tf;
  refresh();
}

function drawChart(candles){
  const svg=document.getElementById("chartSvg");
  const empty=document.getElementById("chartEmpty");
  if(!candles || candles.length<2){svg.innerHTML="";empty.style.display="grid";return}
  empty.style.display="none";
  const data=candles.slice(-90);
  const lo=Math.min(...data.map(c=>Number(c.low)));
  const hi=Math.max(...data.map(c=>Number(c.high)));
  const span=(hi-lo)||1;
  const w=1000,h=400, left=22,right=12,top=24,bottom=20;
  const x=i=>left+i*((w-left-right)/(data.length-1));
  const y=v=>top+(hi-v)*(h-top-bottom)/span;
  let out="";
  for(let i=0;i<data.length;i++){
    const c=data[i],xx=x(i),yo=y(c.open),yc=y(c.close),yh=y(c.high),yl=y(c.low);
    const up=Number(c.close)>=Number(c.open);
    const bodyH=Math.max(2,Math.abs(yc-yo));
    out += '<line x1="'+xx+'" y1="'+yh+'" x2="'+xx+'" y2="'+yl+'" stroke="'+(up?'#00ff91':'#ff3045')+'" stroke-width="1"/>';
    out += '<rect x="'+(xx-3)+'" y="'+Math.min(yo,yc)+'" width="6" height="'+bodyH+'" fill="'+(up?'#00ff91':'#ff3045')+'" opacity=".9"/>';
  }
  svg.innerHTML=out;
}

function setSignal(s){
  const direction=s?.direction||"WAIT";
  const conf=Number(s?.confidence||0);
  lastDirection=direction;
  const el=document.getElementById("signal");
  el.textContent=direction;
  el.className="signal-word "+(direction==="CALL"?"green":direction==="PUT"?"red":"cyan");
  document.getElementById("confidence").textContent=conf.toFixed(1)+"%";
  document.getElementById("confFill").style.width=Math.max(0,Math.min(100,conf))+"%";
  const reasons=(s?.reasons||["No live analysis yet."]);
  document.getElementById("reasons").innerHTML=reasons.map(x=>'<div class="reason">'+x+"</div>").join("");
  const ind=s?.indicators||{};
  document.getElementById("indicators").innerHTML=Object.entries(ind).slice(0,9).map(([k,v])=>{
    const n=(v==null||Number.isNaN(Number(v)))?"—":Number(v).toFixed(4);
    return '<div class="mini"><b>'+k.toUpperCase()+'</b><div>'+n+'</div></div>';
  }).join("");
  const row=document.getElementById("signalRows");
  row.innerHTML='<tr><td>'+new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"})+'</td><td>'+document.getElementById("assetTitle").textContent+'</td><td><span class="pill '+direction.toLowerCase()+'">'+direction+'</span></td><td>'+conf.toFixed(1)+'%</td><td><span class="pill live">LIVE</span></td></tr>';
}

async function refresh(){
  try{
    const r=await fetch("/api/state",{cache:"no-store"});
    const d=await r.json();
    const live=!!d.connected;
    document.getElementById("liveBadge").innerHTML=live?"● LIVE<br><span style='font-weight:400'>Market Feed</span>":"○ OFFLINE<br><span style='font-weight:400'>Market Feed</span>";
    document.getElementById("liveBadge").className=live?"live":"live";
    document.getElementById("engineTop").textContent=d.engine||"WAITING";
    document.getElementById("feedState").textContent=live?"CONNECTED":"WAITING";
    document.getElementById("feedText").textContent=live?"Pocket Option market-data stream connected":(d.error||"Waiting for market data");
    document.getElementById("assetTitle").textContent={{ASSET_LABELS|tojson}}[d.asset]||d.asset;
    document.getElementById("rowAsset").textContent=document.getElementById("assetTitle").textContent;
    currentTf=d.timeframe||currentTf;
    document.getElementById("tfMetric").textContent=currentTf;
    document.getElementById("sideTf").textContent=currentTf;
    pickTf(currentTf);
    document.getElementById("candleCount").textContent=d.candles||0;
    document.getElementById("stale").textContent=d.stale_seconds==null?"—":Number(d.stale_seconds).toFixed(1)+"s";
    document.getElementById("stage").textContent=d.connection_stage||"—";
    document.getElementById("entryWindow").textContent=live?Math.max(0,Math.ceil(periodSeconds[currentTf]-(Date.now()/1000)%periodSeconds[currentTf]))+"s":"—";
    document.getElementById("countdown").textContent=live?Math.max(0,Math.ceil(periodSeconds[currentTf]-(Date.now()/1000)%periodSeconds[currentTf])).toString().padStart(2,"0")+"s":"--:--";
    setSignal(d.signal);
    drawChart(d.candle_data||[]);
  }catch(e){
    document.getElementById("feedState").textContent="ERROR";
    document.getElementById("engineTop").textContent="OFFLINE";
    document.getElementById("events").textContent="Dashboard state request failed.";
  }
}
async function quantumStatus(){
  const r=await fetch("/api/quantum-status",{cache:"no-store"});
  const d=await r.json();
  document.querySelectorAll("[data-qenv]").forEach(x=>{
    const state=d[x.dataset.qenv];
    x.textContent=state?"CONFIGURED":"OPTIONAL / NOT CONFIGURED";
    x.className="qstatus "+(state?"ready":"wait");
  });
}
function jumpGroup(name){
  const el=document.getElementById("group-"+name.replaceAll(" ","-"));
  if(el){el.scrollIntoView({behavior:"smooth",block:"center"});}
}
refresh(); quantumStatus(); setInterval(refresh,2000); setInterval(quantumStatus,10000);
</script>
</body>
</html>"""

@app.get("/")
def dashboard():
    return render_template_string(
        HTML,
        TIMEFRAMES=TIMEFRAMES,
        PERIODS=service.PERIODS if hasattr(service, "PERIODS") else {
            "5s":5,"10s":10,"15s":15,"30s":30,"1m":60,"2m":120,"3m":180,
            "5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,
            "1d":86400,"1w":604800,"1mo":2592000
        },
        ASSET_GROUPS=ASSET_GROUPS,
        ASSET_LABELS=ASSET_LABELS,
        QUANTUM_CLOUDS=QUANTUM_CLOUDS,
        selected_asset=service.asset,
        selected_tf=service.timeframe,
        VERSION=VERSION,
    )

@app.get("/api/health")
def health():
    service.start()
    s=service.snapshot()
    return jsonify({
        "service":APP_NAME,"version":VERSION,"status":"ok",
        "feed":"live" if s["connected"] else "offline",
        "engine":s["engine"],"configured":s["configured"]
    })

@app.get("/api/config")
def config():
    return jsonify({
        "name":APP_NAME,"version":VERSION,
        "timeframes":TIMEFRAMES,
        "asset_groups":ASSET_GROUPS,
        "asset_labels":ASSET_LABELS,
        "quantum_clouds":[x[0] for x in QUANTUM_CLOUDS],
    })

@app.get("/api/quantum-status")
def quantum_status():
    return jsonify({
        key: bool(os.getenv(key))
        for _,_,key in QUANTUM_CLOUDS
    })

@app.get("/api/state")
def state():
    service.start()
    s=service.snapshot()
    s["timeframe"]=service.timeframe
    return jsonify(s)

@app.post("/api/configure")
def configure():
    data=request.get_json(silent=True) or {}
    asset=data.get("asset",service.asset)
    timeframe=data.get("timeframe",service.timeframe)
    valid_assets={a for group in ASSET_GROUPS.values() for a in group}
    if asset not in valid_assets or timeframe not in TIMEFRAMES:
        return jsonify({"error":"Invalid asset or timeframe"}),400
    service.configure(asset,timeframe)
    return jsonify({"ok":True,"asset":asset,"timeframe":timeframe})

if __name__=="__main__":
    service.start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
