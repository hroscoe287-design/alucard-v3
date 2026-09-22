import os
from flask import Flask, jsonify, render_template_string
from signal_service import service

app = Flask(__name__)
APP_NAME = "ALUCARD V3"
APP_SUBTITLE = "GOTHIC MARKET INTELLIGENCE"
VERSION = "3.0.0"
TIMEFRAMES = ["5s","15s","30s","1m","2m","3m","5m","15m","30m","1h","4h","1d"]

ASSET_GROUPS = {
    "FOREX": ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD","EURGBP","EURJPY","GBPJPY"],
    "OTC FOREX": ["EURUSD_otc","GBPUSD_otc","USDJPY_otc","USDCHF_otc","AUDUSD_otc","USDCAD_otc","NZDUSD_otc","EURGBP_otc","EURJPY_otc","GBPJPY_otc"],
    "COMMODITIES": ["XAUUSD","XAGUSD","USOIL","UKOIL","NATGAS"],
    "OTC COMMODITIES": ["XAUUSD_otc","XAGUSD_otc","USOIL_otc","UKOIL_otc","NATGAS_otc"],
    "CRYPTO": ["BTCUSD","ETHUSD","LTCUSD","XRPUSD","BCHUSD","DOGEUSD","ADAUSD","SOLUSD","DOTUSD","LINKUSD","AVAXUSD","BNB"],
    "OTC CRYPTO": ["BTCUSD_otc","ETHUSD_otc","LTCUSD_otc","XRPUSD_otc","BCHUSD_otc","DOGEUSD_otc","ADAUSD_otc","SOLUSD_otc","DOTUSD_otc","LINKUSD_otc","AVAXUSD_otc","BNB_otc"],
    "STOCKS": ["AAPL","MSFT","AMZN","TSLA","META","GOOGL","NFLX","NVDA"],
    "OTC STOCKS": ["AAPL_otc","MSFT_otc","AMZN_otc","TSLA_otc","META_otc","GOOGL_otc","NFLX_otc","NVDA_otc"],
    "INDICES": ["SP500","NAS100","DJI30","DAX40","FTSE100","CAC40"],
    "OTC INDICES": ["SP500_otc","NAS100_otc","DJI30_otc","DAX40_otc","FTSE100_otc","CAC40_otc"],
}

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ALUCARD V3</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#08080b;color:#eee;font-family:Arial,sans-serif}
header{padding:18px;border-bottom:1px solid #292932;background:#101016}h1{margin:0;font-size:25px;letter-spacing:2px}
.sub{color:#8d8d98;font-size:11px;margin-top:5px;letter-spacing:2px}main{padding:16px;max-width:1150px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.card{background:#111118;border:1px solid #292932;border-radius:10px;padding:15px}
.label{font-size:10px;color:#8d8d98;letter-spacing:1.5px}.value{font-size:21px;margin-top:8px}
.tabs{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}button{background:#17171f;color:#ddd;border:1px solid #33333d;border-radius:7px;padding:10px 14px}
select{width:100%;padding:11px;background:#111118;color:#eee;border:1px solid #33333d;border-radius:7px;margin:7px 0}
.signal{font-size:46px;font-weight:bold;margin-top:14px}.muted{color:#999}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.reason{padding:7px 0;border-bottom:1px solid #22222b}.indicator{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mini{background:#0c0c11;padding:9px;border-radius:7px}
@media(max-width:700px){.grid{grid-template-columns:repeat(2,1fr)}.row{grid-template-columns:1fr}}
</style></head>
<body><header><h1>☠ ALUCARD V3</h1><div class="sub">GOTHIC MARKET INTELLIGENCE • LIVE MARKET ENGINE</div></header>
<main>
<div class="grid">
<div class="card"><div class="label">FEED</div><div id="feed" class="value">CONNECTING</div></div>
<div class="card"><div class="label">ENGINE</div><div id="engine" class="value">STARTING</div></div>
<div class="card"><div class="label">ASSET</div><div id="asset" class="value">EURUSD_otc</div></div>
<div class="card"><div class="label">TIMEFRAME</div><div id="tfv" class="value">1m</div></div>
</div>
<div class="tabs"><button>Signals</button><button>Trades</button><button>Performance</button><button>Settings</button></div>
<div class="row">
<div class="card"><div class="label">MARKET DATA</div>
<select id="assetSelect">{% for group,assets in ASSET_GROUPS.items() %}<optgroup label="{{group}}">{% for asset in assets %}<option value="{{asset}}" {% if asset==selected_asset %}selected{% endif %}>{{asset}}</option>{% endfor %}</optgroup>{% endfor %}</select>
<select id="tfSelect">{% for tf in TIMEFRAMES %}<option {% if tf==selected_tf %}selected{% endif %}>{{tf}}</option>{% endfor %}</select>
<button onclick="applySettings()">APPLY</button>
<div id="connection" class="muted">Waiting for live market data…</div></div>
<div class="card"><div class="label">SIGNAL</div><div id="signal" class="signal">WAIT</div><div id="confidence" class="muted">Confidence: —</div><div id="countdown" class="muted">Entry window: —</div></div>
</div>
<div class="card" style="margin-top:12px"><div class="label">ANALYSIS</div><div id="reasons" class="muted">No live analysis yet.</div><div class="label" style="margin-top:15px">INDICATORS</div><div id="indicators" class="indicator"></div></div>
</main>
<script>
let timer=null;
async function refresh(){
 try{
  const r=await fetch('/api/state',{cache:'no-store'}); const d=await r.json();
  document.getElementById('feed').textContent=d.connected?'LIVE':(d.configured?'DISCONNECTED':'NOT CONFIGURED');
  document.getElementById('engine').textContent=d.engine;
  document.getElementById('asset').textContent=d.asset;
  document.getElementById('tfv').textContent=d.timeframe;
  document.getElementById('connection').textContent=d.connected?'Pocket Option market-data stream connected':(d.error||'Waiting for Pocket Option WebSocket credentials');
  const s=d.signal;
  if(s){document.getElementById('signal').textContent=s.direction;document.getElementById('confidence').textContent='Model confidence: '+s.confidence+'%';
   document.getElementById('reasons').innerHTML=s.reasons.map(x=>'<div class="reason">'+x+'</div>').join('');
   document.getElementById('indicators').innerHTML=Object.entries(s.indicators||{}).map(([k,v])=>'<div class="mini"><b>'+k+'</b><br>'+(v==null?'—':Number(v).toFixed(4))+'</div>').join('');
  }
 }catch(e){document.getElementById('feed').textContent='ERROR'}
}
async function applySettings(){
 const asset=document.getElementById('assetSelect').value, tf=document.getElementById('tfSelect').value;
 await fetch('/api/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset,timeframe:tf})});
 refresh();
}
refresh();setInterval(refresh,2000);
</script></body></html>"""

@app.get("/")
def dashboard():
    return render_template_string(HTML,TIMEFRAMES=TIMEFRAMES,ASSET_GROUPS=ASSET_GROUPS,
                                  selected_asset=service.asset,selected_tf=service.timeframe)

@app.get("/api/health")
def health():
    service.start()
    s=service.snapshot()
    return jsonify({"service":APP_NAME,"version":VERSION,"status":"ok",
                    "feed":"live" if s["connected"] else "offline",
                    "engine":s["engine"],"configured":s["configured"]})

@app.get("/api/config")
def config():
    return jsonify({"name":APP_NAME,"version":VERSION,"timeframes":TIMEFRAMES,
                    "asset_groups":ASSET_GROUPS})

@app.get("/api/state")
def state():
    service.start()
    s=service.snapshot()
    s["timeframe"]=service.timeframe
    return jsonify(s)

@app.post("/api/configure")
def configure():
    from flask import request
    data=request.get_json(silent=True) or {}
    asset=data.get("asset",service.asset)
    timeframe=data.get("timeframe",service.timeframe)
    if asset not in {a for group in ASSET_GROUPS.values() for a in group} or timeframe not in TIMEFRAMES:
        return jsonify({"error":"Invalid asset or timeframe"}),400
    service.asset=asset
    service.timeframe=timeframe
    service.period={"5s":5,"15s":15,"30s":30,"1m":60,"2m":120,"3m":180,"5m":300,
                    "15m":900,"30m":1800,"1h":3600,"4h":14400,"1d":86400}[timeframe]
    if service.adapter.connected:
        service.adapter.subscribe(asset,service.period)
    return jsonify({"ok":True,"asset":asset,"timeframe":timeframe})

if __name__=="__main__":
    service.start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
