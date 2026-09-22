import os
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
APP_NAME = "ALUCARD V3"
APP_SUBTITLE = "GOTHIC MARKET INTELLIGENCE"
VERSION = "3.0.0"
TIMEFRAMES = ["5s", "15s", "30s", "1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]
ASSET_GROUPS = {"FOREX": [], "OTC FOREX": [], "COMMODITIES": [], "OTC COMMODITIES": [], "CRYPTO": [], "OTC CRYPTO": [], "STOCKS": [], "OTC STOCKS": [], "INDICES": [], "OTC INDICES": []}
HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ALUCARD V3</title><style>*{box-sizing:border-box}body{margin:0;background:#09090c;color:#eee;font-family:Arial,sans-serif}header{padding:18px;border-bottom:1px solid #292932;background:#101016}h1{margin:0;font-size:24px;letter-spacing:2px}.sub{color:#888;font-size:11px;margin-top:5px;letter-spacing:2px}main{padding:16px;max-width:1100px;margin:auto}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.card{background:#111118;border:1px solid #292932;border-radius:10px;padding:15px}.label{font-size:10px;color:#888;letter-spacing:1.5px}.value{font-size:21px;margin-top:8px}.tabs{display:flex;gap:8px;margin:15px 0;flex-wrap:wrap}button{background:#17171f;color:#ddd;border:1px solid #33333d;border-radius:7px;padding:10px 14px}select{width:100%;padding:11px;background:#111118;color:#eee;border:1px solid #33333d;border-radius:7px}.signal{font-size:42px;font-weight:bold;margin-top:10px}.wait{color:#aaa}@media(max-width:700px){.grid{grid-template-columns:repeat(2,1fr)}}</style></head><body><header><h1>☠ ALUCARD V3</h1><div class="sub">GOTHIC MARKET INTELLIGENCE</div></header><main><div class="grid"><div class="card"><div class="label">FEED</div><div class="value">OFFLINE</div></div><div class="card"><div class="label">ENGINE</div><div class="value">READY</div></div><div class="card"><div class="label">ASSET</div><div class="value">—</div></div><div class="card"><div class="label">TIMEFRAME</div><div class="value">1m</div></div></div><div class="tabs"><button>Signals</button><button>Trades</button><button>Performance</button><button>Settings</button></div><div class="card"><div class="label">MARKET DATA CONNECTION</div><p>ALUCARD V3 is waiting for a live market-data adapter.</p><div class="label">TIMEFRAME</div><select>{% for tf in TIMEFRAMES %}<option>{{ tf }}</option>{% endfor %}</select><div class="signal wait">WAIT</div></div></main></body></html>"""

@app.get("/")
def dashboard():
    return render_template_string(HTML, TIMEFRAMES=TIMEFRAMES)

@app.get("/api/health")
def health():
    return jsonify({"service": APP_NAME, "version": VERSION, "status": "ok", "feed": "offline", "engine": "ready"})

@app.get("/api/config")
def config():
    return jsonify({"name": APP_NAME, "version": VERSION, "timeframes": TIMEFRAMES, "asset_groups": list(ASSET_GROUPS.keys())})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
