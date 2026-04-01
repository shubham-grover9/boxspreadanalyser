"""
NIFTY Box Spread Arbitrage Analyzer v2 — Multi-Expiry + Fyers API v3
- Fetches ALL available expiries from Fyers
- Visitors can switch between expiries
- Each expiry has its own live analysis
- Locked assumptions, owner's Fyers account feeds everyone
"""

import os, json, time, threading, hashlib, secrets
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, jsonify, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

# ── ENV VARS ─────────────────────────────────────────────────────────────────
FYERS_CLIENT_ID  = os.environ.get("FYERS_CLIENT_ID", "")
FYERS_SECRET_KEY = os.environ.get("FYERS_SECRET_KEY", "")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "changeme")
APP_URL          = os.environ.get("APP_URL", "http://localhost:5000")
REFRESH_SECONDS  = int(os.environ.get("REFRESH_SECONDS", "60"))

PARAMS = {
    "lot_size":       int(os.environ.get("LOT_SIZE", "75")),
    "num_lots":       int(os.environ.get("NUM_LOTS", "1")),
    "broker_per_leg": float(os.environ.get("BROKER_PER_LEG", "20")),
    "stt_entry_pct":  float(os.environ.get("STT_ENTRY_PCT", "0.05")),
    "stt_settl_pct":  float(os.environ.get("STT_SETTL_PCT", "0.125")),
    "txn_pct":        float(os.environ.get("TXN_PCT", "0.03503")),
    "sebi_pct":       float(os.environ.get("SEBI_PCT", "0.0001")),
    "gst_pct":        float(os.environ.get("GST_PCT", "18")),
    "stamp_pct":      float(os.environ.get("STAMP_PCT", "0.003")),
    "slip_per_leg":   float(os.environ.get("SLIP_PER_LEG", "0.5")),
    "rfr":            float(os.environ.get("RFR", "6.5")),
    "min_ann_ret":    float(os.environ.get("MIN_ANN_RET", "1.0")),
    "max_spread_pct": float(os.environ.get("MAX_SPREAD_PCT", "1.0")),
}

# ── STATE — one entry per expiry ─────────────────────────────────────────────
# state["expiries"] = ["27-Mar-2025", "24-Apr-2025", ...]  (sorted)
# state["data"][expiry] = { results, last_fetch, cmp, error, dte }
state = {
    "expiries":     [],
    "data":         {},
    "raw_map":      {},
    "access_token": None,
    "token_date":   None,
    "global_error": None,
}

TOKEN_FILE = "/tmp/fyers_token.json"

def save_token(token):
    state["access_token"] = token
    state["token_date"]   = str(date.today())
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token, "date": str(date.today())}, f)
    except Exception:
        pass

def load_token():
    if state["access_token"] and state["token_date"] == str(date.today()):
        return state["access_token"]
    try:
        with open(TOKEN_FILE) as f:
            d = json.load(f)
        if d.get("date") == str(date.today()):
            state["access_token"] = d["token"]
            state["token_date"]   = d["date"]
            return d["token"]
    except Exception:
        pass
    return None

def is_authenticated():
    return bool(load_token())

# ── FYERS AUTH ────────────────────────────────────────────────────────────────
def get_auth_url():
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=f"{APP_URL}/callback",
            response_type="code", grant_type="authorization_code",
        )
        return s.generate_authcode()
    except Exception as e:
        return None

def exchange_code(auth_code):
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=f"{APP_URL}/callback",
            response_type="code", grant_type="authorization_code",
        )
        s.set_token(auth_code)
        resp = s.generate_token()
        return resp.get("access_token")
    except Exception as e:
        state["global_error"] = str(e)
        return None

# ── OPTION CHAIN FETCH (per expiry) ──────────────────────────────────────────
def parse_expiry(expiry_raw):
    """Convert Fyers expiry (Unix timestamp int or date string) to (display_str, date_obj)."""
    try:
        # If it's a number (Unix timestamp)
        ts = int(expiry_raw)
        dt = datetime.fromtimestamp(ts).date()
        return dt.strftime("%d-%b-%Y"), dt
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.strptime(str(expiry_raw), "%d-%b-%Y").date()
        return str(expiry_raw), dt
    except Exception:
        return str(expiry_raw), None

def days_to_expiry(expiry_raw):
    """Calculate DTE from expiry (Unix timestamp or date string)."""
    _, dt = parse_expiry(expiry_raw)
    if dt:
        return max(1, (dt - date.today()).days)
    return 30

def fetch_expiry(fyers, expiry_raw):
    """Fetch option chain for one specific expiry and compute box spreads."""
    try:
        display, _ = parse_expiry(expiry_raw)
        # Fyers expects the raw value (timestamp int or original string) back
        data = {
            "symbol":      "NSE:NIFTY50-INDEX",
            "strikecount": "25",
            "timestamp":   str(expiry_raw),
        }
        resp = fyers.optionchain(data=data)
        if resp.get("s") != "ok":
            return {"error": f"API: {resp.get('message', str(resp))}", "results": [], "cmp": None, "last_fetch": None}

        opt = resp.get("data", {})
        cmp = opt.get("ltp")

        # Build chain dict
        chain = {}
        for row in opt.get("optionChain", []):
            k = row.get("strikePrice")
            if k is None: continue
            if k not in chain:
                chain[k] = {"k":k,"cb":None,"ca":None,"pb":None,"pa":None}
            ot = row.get("option_type")
            if ot == "CE":
                chain[k]["cb"] = row.get("bid_price")
                chain[k]["ca"] = row.get("ask_price")
            elif ot == "PE":
                chain[k]["pb"] = row.get("bid_price")
                chain[k]["pa"] = row.get("ask_price")

        strikes  = sorted(chain.values(), key=lambda x: x["k"])
        dte      = days_to_expiry(expiry_raw)
        results  = []
        for i in range(len(strikes)):
            for j in range(i+1, len(strikes)):
                r = calc_pair(strikes[i], strikes[j], dte)
                if r: results.append(r)
        results.sort(key=lambda x: x["ann_ret"], reverse=True)

        return {
            "results":    results,
            "cmp":        cmp,
            "dte":        dte,
            "last_fetch": datetime.now().strftime("%H:%M:%S"),
            "error":      None,
        }
    except Exception as e:
        return {"error": str(e), "results": [], "cmp": None, "last_fetch": None}

def fetch_all_expiries():
    """Fetch list of all expiries, then fetch chain for each."""
    token = load_token()
    if not token:
        state["global_error"] = "No access token — admin login required."
        return
    try:
        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=token, log_path="")

        # First call to get all available expiries
        resp = fyers.optionchain(data={"symbol": "NSE:NIFTY50-INDEX", "strikecount": "1", "timestamp": ""})
        if resp.get("s") != "ok":
            state["global_error"] = f"Fyers API: {resp.get('message')}"
            return

        raw_expiries = [e["expiry"] for e in resp.get("data", {}).get("expiryData", [])]
        if not raw_expiries:
            state["global_error"] = "No expiries found in API response."
            return

        # Convert to display names, keep mapping raw→display
        expiry_display = []
        raw_map = {}  # display_str -> raw_value
        for raw in raw_expiries:
            display, _ = parse_expiry(raw)
            expiry_display.append(display)
            raw_map[display] = raw

        state["expiries"]     = expiry_display
        state["raw_map"]      = raw_map
        state["global_error"] = None

        # Fetch chain for each expiry
        for display in expiry_display:
            raw = raw_map[display]
            result = fetch_expiry(fyers, raw)
            result["display"] = display
            state["data"][display] = result
            time.sleep(0.3)  # be gentle with API rate limits

    except Exception as e:
        state["global_error"] = str(e)

def refresh_loop():
    while True:
        if is_authenticated():
            fetch_all_expiries()
        time.sleep(REFRESH_SECONDS)

# ── BOX SPREAD ENGINE ─────────────────────────────────────────────────────────
def calc_pair(r1, r2, dte):
    p    = PARAMS
    ca1, pb1 = r1.get("ca"), r1.get("pb")
    cb2, pa2 = r2.get("cb"), r2.get("pa")
    if any(v is None for v in [ca1, pb1, cb2, pa2]): return None

    k1, k2 = r1["k"], r2["k"]
    lots   = p["lot_size"] * p["num_lots"]
    box_w  = k2 - k1
    nd     = (ca1 + pa2 - cb2 - pb1) * lots
    bv     = box_w * lots
    estt   = p["stt_entry_pct"] / 100 * (cb2 + pb1) * lots
    sstt   = p["stt_settl_pct"] / 100 * bv
    tp     = (ca1 + pa2 + cb2 + pb1) * lots
    other  = (p["txn_pct"]/100*tp + p["sebi_pct"]/100*tp +
              4*p["broker_per_leg"]*(1+p["gst_pct"]/100) +
              p["stamp_pct"]/100*(ca1+pa2)*lots +
              4*p["slip_per_leg"]*lots)
    net    = bv - nd - estt - sstt - other
    ret    = net / nd * 100 if nd else 0
    ann    = ret * 365 / dte if dte else 0

    cb1, ca2, pa1, pb2 = r1.get("cb"), r2.get("ca"), r1.get("pa"), r2.get("pb")
    sp = None
    if all(v is not None for v in [ca1,cb1,ca2,cb2,pa1,pb1,pa2,pb2]):
        sp = ((ca1-cb1)+(ca2-cb2)+(pa1-pb1)+(pa2-pb2)) / box_w * 100

    if net <= 0:                  sig = "loss"
    elif ann < p["min_ann_ret"]:  sig = "borderline"
    elif sp is not None and sp < p["max_spread_pct"]: sig = "execute"
    else:                         sig = "borderline"

    return {
        "k1":k1,"k2":k2,"box_w":box_w,
        "net_debit":round(nd,0),"box_value":round(bv,0),
        "entry_stt":round(estt,0),"settl_stt":round(sstt,0),
        "other_costs":round(other,0),"net_pnl":round(net,0),
        "ret_pct":round(ret,2),"ann_ret":round(ann,2),
        "spread_pct":round(sp,2) if sp is not None else None,
        "signal":sig,
    }

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML, refresh_sec=REFRESH_SECONDS)

@app.route("/api/expiries")
def api_expiries():
    return jsonify({
        "expiries":      state["expiries"],
        "authenticated": is_authenticated(),
        "global_error":  state["global_error"],
        "refresh_sec":   REFRESH_SECONDS,
    })

@app.route("/api/data/<expiry>")
def api_data(expiry):
    d = state["data"].get(expiry, {})
    res = d.get("results", [])
    arb   = sum(1 for r in res if r["signal"]=="execute")
    bord  = sum(1 for r in res if r["signal"]=="borderline")
    best  = max((r["net_pnl"] for r in res), default=None)
    maxan = max((r["ann_ret"] for r in res), default=None)
    return jsonify({
        "expiry":      expiry,
        "results":     res,
        "last_fetch":  d.get("last_fetch"),
        "error":       d.get("error"),
        "cmp":         d.get("cmp"),
        "dte":         d.get("dte"),
        "params":      PARAMS,
        "scorecard":   {"total":len(res),"arb":arb,"borderline":bord,
                        "loss":len(res)-arb-bord,"best_pnl":best,"max_ann":maxan},
    })

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        pw = request.form.get("password","")
        if hashlib.sha256(pw.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest():
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template_string(ADMIN_HTML, error="Wrong password", logged_in=False, state=state, auth_url=None)
    if not session.get("admin"):
        return render_template_string(ADMIN_HTML, error=None, logged_in=False, state=state, auth_url=None)
    return render_template_string(ADMIN_HTML, error=None, logged_in=True, state=state, auth_url=get_auth_url())

@app.route("/callback")
def callback():
    auth_code = request.args.get("auth_code")
    if not auth_code:
        return "<h2>No auth code received.</h2><a href='/admin'>Back</a>"
    token = exchange_code(auth_code)
    if token:
        save_token(token)
        threading.Thread(target=fetch_all_expiries, daemon=True).start()
        return redirect("/admin?success=1")
    return f"<h2>Token exchange failed.</h2><p>{state['global_error']}</p><a href='/admin'>Back</a>"

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")

# ── DASHBOARD HTML ────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIFTY Box Spread — Live</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#f4f6f9;color:#1a1a1a}
.topbar{background:#0f172a;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.title{font-size:16px;font-weight:700;color:#f8fafc;letter-spacing:-.3px}
.subtitle{font-size:11px;color:#94a3b8;margin-top:2px}
.status{display:flex;align-items:center;gap:8px;font-size:12px;color:#94a3b8}
.dot{width:8px;height:8px;border-radius:50%;background:#475569}
.dot.live{background:#22c55e;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.main{padding:20px 24px;max-width:1400px;margin:0 auto}
.expiry-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;align-items:center}
.expiry-label{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-right:4px}
.eb{padding:5px 14px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:12px;color:#475569;font-weight:500;font-family:inherit;transition:all .15s}
.eb:hover{border-color:#94a3b8;color:#0f172a}
.eb.active{background:#0f172a;color:#fff;border-color:#0f172a}
.eb .arb-badge{display:inline-block;margin-left:5px;background:#dcfce7;color:#15803d;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700}
.eb.active .arb-badge{background:#22c55e;color:#fff}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px}
@media(max-width:800px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.cl{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.cv{font-size:22px;font-weight:700;font-family:'Courier New',monospace}
.cv.g{color:#16a34a}.cv.a{color:#d97706}.cv.r{color:#dc2626}.cv.b{color:#2563eb}
.section{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:16px;overflow:hidden}
.sechdr{padding:12px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px;display:flex;align-items:center;justify-content:space-between}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.fb{padding:4px 12px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:12px;color:#64748b;font-family:inherit}
.fb.active{background:#0f172a;color:#fff;border-color:#0f172a}
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#f8fafc;padding:8px 12px;text-align:right;font-size:11px;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0;white-space:nowrap;text-transform:uppercase;letter-spacing:.4px}
th:first-child,th:nth-child(2){text-align:left}
td{padding:7px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Courier New',monospace;white-space:nowrap}
td:first-child,td:nth-child(2){text-align:left;font-family:inherit;font-weight:600;color:#0f172a}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;font-family:inherit}
.pill-g{background:#dcfce7;color:#15803d}
.pill-a{background:#fef3c7;color:#92400e}
.pill-r{background:#fee2e2;color:#b91c1c}
.empty{text-align:center;padding:48px;color:#94a3b8;font-size:13px}
.ref{font-size:11px;color:#94a3b8}
.loading{text-align:center;padding:32px;color:#94a3b8}
</style>
</head>
<body>
<div class="topbar">
  <div>
    <div class="title">NIFTY Box Spread Arbitrage Scanner</div>
    <div class="subtitle" id="subtitle">Loading expiries...</div>
  </div>
  <div class="status"><div class="dot" id="dot"></div><span id="statusTxt">Connecting</span></div>
</div>
<div class="main">
  <div class="expiry-bar" id="expiryBar">
    <span class="expiry-label">Expiry</span>
    <span class="loading">Fetching expiries...</span>
  </div>
  <div id="scoreCards" class="cards"></div>
  <div class="section">
    <div class="sechdr">
      <span id="tableTitle">Results</span>
      <div style="display:flex;gap:12px;align-items:center">
        <div class="filters" id="filterBtns"></div>
        <span class="ref" id="refreshInfo"></span>
      </div>
    </div>
    <div style="padding:0"><div class="tbl-wrap">
      <table>
        <thead><tr>
          <th style="text-align:left">K1</th><th style="text-align:left">K2</th>
          <th>Width</th><th>DTE</th><th>Net Debit</th><th>Box Value</th>
          <th>Entry STT</th><th>Settl. STT</th><th>Other Costs</th>
          <th>Net P&amp;L</th><th>Return%</th><th>Ann.%</th>
          <th>Spread%</th><th>Signal</th>
        </tr></thead>
        <tbody id="tBody"><tr><td colspan="14"><div class="empty">Select an expiry above to load results</div></td></tr></tbody>
      </table>
    </div></div>
  </div>
  <div style="text-align:center;font-size:11px;color:#94a3b8;padding-bottom:24px">
    Live data via Fyers API v3 · NSE European-style cash-settled index options · Not financial advice
  </div>
</div>
<script>
let filter='all', allExpiries=[], activeExpiry=null, expiryCache={}, dte=91;
const fi=(v,d=0)=>v==null?'—':(v<0?'−':'')+'₹'+Math.abs(v).toFixed(d).replace(/\B(?=(\d{3})+(?!\d))/g,',');
const fp=v=>v==null?'—':(v>=0?'+':'')+v.toFixed(2)+'%';
const pills={execute:'pill-g',borderline:'pill-a',loss:'pill-r'};
const plabs={execute:'EXECUTE',borderline:'BORDERLINE',loss:'AVOID'};

async function loadExpiries(){
  try{
    const r=await fetch('/api/expiries');
    const d=await r.json();
    allExpiries=d.expiries||[];
    document.getElementById('dot').className=d.global_error?'dot':'dot live';
    document.getElementById('statusTxt').textContent=d.global_error?'Error':('Live · refreshes every '+d.refresh_sec+'s');
    document.getElementById('refreshInfo').textContent='Auto-refreshes every '+d.refresh_sec+'s';
    renderExpiryBar();
    if(allExpiries.length && !activeExpiry){
      activeExpiry=allExpiries[0];
      loadExpiry(activeExpiry);
    }
  }catch(e){document.getElementById('statusTxt').textContent='Connection error';}
}

async function loadExpiry(expiry){
  activeExpiry=expiry;
  renderExpiryBar();
  document.getElementById('tBody').innerHTML='<tr><td colspan="14"><div class="empty">Loading '+expiry+'...</div></td></tr>';
  const r=await fetch('/api/data/'+encodeURIComponent(expiry));
  const d=await r.json();
  expiryCache[expiry]=d;
  dte=d.dte||91;
  document.getElementById('subtitle').textContent=expiry+' · '+dte+' days · CMP ₹'+(d.cmp||0).toLocaleString('en-IN')+'  · Lot '+(d.params?.lot_size||75);
  renderResults(d);
  renderExpiryBar();
}

function renderExpiryBar(){
  const bar=document.getElementById('expiryBar');
  if(!allExpiries.length){bar.innerHTML='<span class="expiry-label">Expiry</span><span style="font-size:12px;color:#94a3b8">Waiting for data...</span>';return;}
  bar.innerHTML='<span class="expiry-label">Expiry</span>'+allExpiries.map(e=>{
    const cached=expiryCache[e];
    const arbCount=cached?cached.scorecard?.arb:null;
    const badge=arbCount>0?`<span class="arb-badge">${arbCount}</span>`:'';
    return `<button class="eb${e===activeExpiry?' active':''}" onclick="loadExpiry('${e}')">${e}${badge}</button>`;
  }).join('');
}

function renderResults(d){
  const s=d.scorecard||{};
  document.getElementById('scoreCards').innerHTML=[
    ['Complete pairs',s.total,'b'],
    ['Arbitrage',s.arb,'g'],
    ['Borderline',s.borderline,'a'],
    ['Best P&L/lot',fi(s.best_pnl),'g'],
    ['Max ann. return',fp(s.max_ann),'g'],
  ].map(([l,v,c])=>`<div class="card"><div class="cl">${l}</div><div class="cv ${c}" style="font-size:${typeof v==='string'&&v.length>6?'14px':'22px'}">${v??'—'}</div></div>`).join('');

  const res=d.results||[];
  const fc={all:res.length,execute:res.filter(r=>r.signal==='execute').length,borderline:res.filter(r=>r.signal==='borderline').length,loss:res.filter(r=>r.signal==='loss').length};
  document.getElementById('filterBtns').innerHTML=Object.keys(fc).map(k=>`<button class="fb${filter===k?' active':''}" onclick="setFilter('${k}')">${k.charAt(0).toUpperCase()+k.slice(1)} (${fc[k]})</button>`).join('');
  document.getElementById('tableTitle').textContent=`${activeExpiry} — ${res.length} complete pairs · DTE: ${d.dte||'?'}`;

  const f=(filter==='all'?res:res.filter(r=>r.signal===filter)).sort((a,b)=>b.ann_ret-a.ann_ret);
  if(!f.length){document.getElementById('tBody').innerHTML=`<tr><td colspan="14"><div class="empty">${d.error?'Error: '+d.error:'No complete pairs with all 4 legs priced'}</div></td></tr>`;return;}
  document.getElementById('tBody').innerHTML=f.map(r=>`<tr>
    <td>${r.k1.toLocaleString('en-IN')}</td><td>${r.k2.toLocaleString('en-IN')}</td>
    <td>${r.box_w.toLocaleString('en-IN')}</td><td>${d.dte||'?'}</td>
    <td>${fi(r.net_debit)}</td><td>${fi(r.box_value)}</td>
    <td>${fi(r.entry_stt)}</td><td>${fi(r.settl_stt)}</td><td>${fi(r.other_costs)}</td>
    <td style="color:${r.net_pnl>=0?'#16a34a':'#dc2626'};font-weight:700">${fi(r.net_pnl)}</td>
    <td style="color:${r.ret_pct>=0?'#16a34a':'#dc2626'}">${fp(r.ret_pct)}</td>
    <td style="color:${r.ann_ret>=1?'#16a34a':r.ann_ret>=0?'#d97706':'#dc2626'};font-weight:700">${fp(r.ann_ret)}</td>
    <td>${r.spread_pct!=null?r.spread_pct.toFixed(2)+'%':'—'}</td>
    <td><span class="pill ${pills[r.signal]}">${plabs[r.signal]}</span></td>
  </tr>`).join('');
}

function setFilter(f){
  filter=f;
  if(activeExpiry&&expiryCache[activeExpiry]) renderResults(expiryCache[activeExpiry]);
}

loadExpiries();
setInterval(()=>{
  loadExpiries();
  if(activeExpiry) loadExpiry(activeExpiry);
}, {{refresh_sec}}000);
</script>
</body></html>"""

# ── ADMIN HTML ────────────────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#f1f5f9;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.box{background:#fff;border-radius:12px;padding:36px;width:100%;max-width:480px;box-shadow:0 4px 20px rgba(0,0,0,.1)}
h1{font-size:20px;margin-bottom:6px}p{font-size:13px;color:#64748b;margin-bottom:20px;line-height:1.5}
label{display:block;font-size:12px;color:#64748b;margin-bottom:4px;font-weight:600}
input[type=password]{width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;margin-bottom:14px}
.btn{display:block;width:100%;padding:11px;background:#0f172a;color:#fff;border:none;border-radius:7px;font-size:14px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none;margin-bottom:8px}
.btn-fyers{background:#ff6600}.btn-fyers:hover{background:#e55a00}
.err{background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:10px;color:#b91c1c;font-size:13px;margin-bottom:14px}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px;color:#15803d;font-size:13px;margin-bottom:14px}
.stat{background:#f8fafc;border-radius:8px;padding:14px;font-size:12px;color:#475569;margin-bottom:16px;line-height:2}
.stat b{color:#0f172a} hr{border:none;border-top:1px solid #e2e8f0;margin:20px 0} a{color:#2563eb;font-size:13px}
</style></head>
<body><div class="box">
  <h1>Scanner Admin</h1>
  <p>This page is only for you. Share the main URL (<a href="/">/</a>) with everyone else.</p>
  {% if not logged_in %}
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST">
      <label>Admin password</label>
      <input type="password" name="password" autofocus>
      <button type="submit" class="btn">Login</button>
    </form>
  {% else %}
    {% if request.args.get('success') %}<div class="ok">✓ Fyers login successful! Live data is fetching all expiries now.</div>{% endif %}
    <div class="stat">
      <b>Auth status:</b> {{ '✓ Token active today' if state.access_token else '✗ No token — login required' }}<br>
      <b>Expiries loaded:</b> {{ state.expiries|length }} ({{ ', '.join(state.expiries[:3]) }}{% if state.expiries|length > 3 %}...{% endif %})<br>
      <b>Total pairs computed:</b> {{ state.data.values()|sum(attribute='results')|list|length if state.data else 0 }}<br>
      {% if state.global_error %}<b>Error:</b> <span style="color:#dc2626">{{ state.global_error }}</span>{% endif %}
    </div>
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">Fyers tokens expire daily at midnight. Click the button each morning before market open.</p>
    {% if auth_url %}<a href="{{ auth_url }}" class="btn btn-fyers">Login with Fyers (refresh token) →</a>{% endif %}
    <hr>
    <a href="/">← Dashboard</a> &nbsp;·&nbsp; <a href="/admin/logout">Logout</a>
  {% endif %}
</div></body></html>"""

# ── STARTUP ───────────────────────────────────────────────────────────────────
def startup():
    if is_authenticated():
        print("✓ Token found — fetching all expiries on startup")
        threading.Thread(target=fetch_all_expiries, daemon=True).start()
    else:
        print("⚠ No token — visit /admin to login with Fyers")
    threading.Thread(target=refresh_loop, daemon=True).start()

startup()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
