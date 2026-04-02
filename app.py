import os, json, time, threading, hashlib, secrets
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, jsonify, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

FYERS_CLIENT_ID  = os.environ.get("FYERS_CLIENT_ID", "")
FYERS_SECRET_KEY = os.environ.get("FYERS_SECRET_KEY", "")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "changeme")
APP_URL          = os.environ.get("APP_URL", "http://localhost:5000")
REFRESH_SEC      = int(os.environ.get("REFRESH_SECONDS", "60"))

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

state = {
    "expiries": [], "raw_map": {}, "data": {},
    "access_token": None, "token_date": None, "global_error": None,
    "last_fetch": None,
}

TOKEN_FILE = "/tmp/fyers_token.json"

# ── AUTH ──────────────────────────────────────────────────────────────────────
def save_token(token):
    state["access_token"] = token
    state["token_date"] = str(date.today())
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
            state["token_date"] = d["date"]
            return d["token"]
    except Exception:
        pass
    return None

def is_authenticated():
    return bool(load_token())

def expiry_display(raw):
    try:
        return datetime.fromtimestamp(int(raw)).strftime("%d-%b-%Y")
    except Exception:
        return str(raw)

def expiry_dte(raw):
    try:
        return max(1, (datetime.fromtimestamp(int(raw)).date() - date.today()).days)
    except Exception:
        pass
    try:
        return max(1, (datetime.strptime(str(raw), "%d-%b-%Y").date() - date.today()).days)
    except Exception:
        return 30

def get_auth_url():
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=APP_URL + "/callback",
            response_type="code", grant_type="authorization_code",
        )
        return s.generate_authcode()
    except Exception:
        return None

def exchange_code(auth_code):
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=APP_URL + "/callback",
            response_type="code", grant_type="authorization_code",
        )
        s.set_token(auth_code)
        resp = s.generate_token()
        return resp.get("access_token")
    except Exception as e:
        state["global_error"] = str(e)
        return None

# ── CALC ──────────────────────────────────────────────────────────────────────
def calc_pair(r1, r2, dte):
    p = PARAMS
    ca1 = r1.get("ca"); pb1 = r1.get("pb")
    cb2 = r2.get("cb"); pa2 = r2.get("pa")
    if any(v is None for v in [ca1, pb1, cb2, pa2]):
        return None
    k1, k2 = r1["k"], r2["k"]
    lots = p["lot_size"] * p["num_lots"]
    box_w = k2 - k1
    nd = (ca1 + pa2 - cb2 - pb1) * lots
    bv = box_w * lots
    estt = (p["stt_entry_pct"] / 100) * (cb2 + pb1) * lots
    sstt = (p["stt_settl_pct"] / 100) * bv
    tp = (ca1 + pa2 + cb2 + pb1) * lots
    other = ((p["txn_pct"] / 100) * tp + (p["sebi_pct"] / 100) * tp +
             4 * p["broker_per_leg"] * (1 + p["gst_pct"] / 100) +
             (p["stamp_pct"] / 100) * (ca1 + pa2) * lots +
             4 * p["slip_per_leg"] * lots)
    net = bv - nd - estt - sstt - other
    ret = (net / nd * 100) if nd else 0
    ann = (ret * 365 / dte) if dte else 0
    cb1 = r1.get("cb"); ca2 = r2.get("ca")
    pa1 = r1.get("pa"); pb2 = r2.get("pb")
    sp = None
    if all(v is not None for v in [ca1, cb1, ca2, cb2, pa1, pb1, pa2, pb2]):
        sp = ((ca1-cb1) + (ca2-cb2) + (pa1-pb1) + (pa2-pb2)) / box_w * 100
    if net <= 0: sig = "loss"
    elif ann < p["min_ann_ret"]: sig = "borderline"
    elif sp is not None and sp < p["max_spread_pct"]: sig = "execute"
    else: sig = "borderline"
    return {
        "k1": k1, "k2": k2, "box_w": box_w,
        "ca1": ca1, "cb2": cb2, "pa2": pa2, "pb1": pb1,
        "net_debit": round(nd, 0), "box_value": round(bv, 0),
        "entry_stt": round(estt, 0), "settl_stt": round(sstt, 0),
        "other_costs": round(other, 0), "net_pnl": round(net, 0),
        "ret_pct": round(ret, 2), "ann_ret": round(ann, 2),
        "spread_pct": round(sp, 2) if sp is not None else None,
        "signal": sig,
    }

def fetch_one(fyers, raw_expiry):
    try:
        resp = fyers.optionchain(data={
            "symbol": "NSE:NIFTY50-INDEX",
            "strikecount": "25",
            "timestamp": str(raw_expiry),
        })
        if resp.get("s") != "ok":
            return {"error": resp.get("message", "API error"), "chain": [], "pairs": [], "cmp": None}
        opt = resp.get("data", {})
        cmp = opt.get("ltp")
        chain_dict = {}
        for row in opt.get("optionChain", []):
            k = row.get("strikePrice")
            if k is None: continue
            if k not in chain_dict:
                chain_dict[k] = {"k": k, "cb": None, "ca": None, "pb": None, "pa": None,
                                  "civ": None, "piv": None, "coi": None, "poi": None}
            ot = row.get("option_type")
            if ot == "CE":
                chain_dict[k]["cb"] = row.get("bid_price")
                chain_dict[k]["ca"] = row.get("ask_price")
                chain_dict[k]["civ"] = row.get("iv")
                chain_dict[k]["coi"] = row.get("oi")
            elif ot == "PE":
                chain_dict[k]["pb"] = row.get("bid_price")
                chain_dict[k]["pa"] = row.get("ask_price")
                chain_dict[k]["piv"] = row.get("iv")
                chain_dict[k]["poi"] = row.get("oi")
        chain = sorted(chain_dict.values(), key=lambda x: x["k"])
        dte = expiry_dte(raw_expiry)
        pairs = []
        for i in range(len(chain)):
            for j in range(i + 1, len(chain)):
                r = calc_pair(chain[i], chain[j], dte)
                if r: pairs.append(r)
        pairs.sort(key=lambda x: x["ann_ret"], reverse=True)
        return {"error": None, "chain": chain, "pairs": pairs, "cmp": cmp, "dte": dte}
    except Exception as e:
        return {"error": str(e), "chain": [], "pairs": [], "cmp": None, "dte": None}

def fetch_all():
    token = load_token()
    if not token:
        state["global_error"] = "No token — visit /admin to login."
        return
    try:
        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=token, log_path="")
        resp = fyers.optionchain(data={"symbol": "NSE:NIFTY50-INDEX", "strikecount": "1", "timestamp": ""})
        if resp.get("s") != "ok":
            state["global_error"] = resp.get("message", "API error")
            return
        raw_expiries = [e["expiry"] for e in resp.get("data", {}).get("expiryData", [])]
        displays = [expiry_display(r) for r in raw_expiries]
        state["expiries"] = displays
        state["raw_map"] = {expiry_display(r): r for r in raw_expiries}
        state["global_error"] = None
        for disp in displays:
            raw = state["raw_map"][disp]
            state["data"][disp] = fetch_one(fyers, raw)
            time.sleep(0.4)
        state["last_fetch"] = datetime.now().strftime("%H:%M:%S")
    except Exception as e:
        state["global_error"] = str(e)

def refresh_loop():
    while True:
        if is_authenticated():
            fetch_all()
        time.sleep(REFRESH_SEC)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def inr(v, dec=0):
    if v is None: return "—"
    neg = v < 0
    s = "₹{:,.{}f}".format(abs(v), dec)
    return ("−" if neg else "") + s

def pct(v, dec=2):
    if v is None: return "—"
    return "{:+.{}f}%".format(v, dec)

def num(v, dec=2):
    if v is None: return "—"
    return "{:.{}f}".format(v, dec)

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    active = request.args.get("expiry") or (state["expiries"][0] if state["expiries"] else None)
    d = state["data"].get(active, {}) if active else {}
    chain = d.get("chain", [])
    pairs = d.get("pairs", [])
    sig_filter = request.args.get("sig", "all")
    if sig_filter != "all":
        pairs = [p for p in pairs if p["signal"] == sig_filter]
    arb = sum(1 for p in d.get("pairs", []) if p["signal"] == "execute")
    bord = sum(1 for p in d.get("pairs", []) if p["signal"] == "borderline")
    loss = sum(1 for p in d.get("pairs", []) if p["signal"] == "loss")
    best = max((p["net_pnl"] for p in d.get("pairs", [])), default=None)
    maxann = max((p["ann_ret"] for p in d.get("pairs", [])), default=None)
    return render_template_string(PAGE,
        expiries=state["expiries"], active=active,
        d=d, chain=chain, pairs=pairs,
        arb=arb, bord=bord, loss=loss,
        total=len(d.get("pairs", [])),
        best=best, maxann=maxann,
        params=PARAMS, inr=inr, pct=pct, num=num,
        last_fetch=state["last_fetch"],
        global_error=state["global_error"],
        authenticated=is_authenticated(),
        sig_filter=sig_filter,
        refresh_sec=REFRESH_SEC,
    )

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hashlib.sha256(pw.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest():
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template_string(ADMIN_PAGE, error="Wrong password", logged_in=False, state=state, auth_url=None)
    if not session.get("admin"):
        return render_template_string(ADMIN_PAGE, error=None, logged_in=False, state=state, auth_url=None)
    return render_template_string(ADMIN_PAGE, error=None, logged_in=True, state=state, auth_url=get_auth_url())

@app.route("/callback")
def callback():
    auth_code = request.args.get("auth_code")
    if not auth_code:
        return "<h2>No auth code.</h2><a href='/admin'>Back</a>"
    token = exchange_code(auth_code)
    if token:
        save_token(token)
        threading.Thread(target=fetch_all, daemon=True).start()
        return redirect("/admin?success=1")
    return "<h2>Token exchange failed.</h2><a href='/admin'>Back</a>"

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")

# ── MAIN PAGE ─────────────────────────────────────────────────────────────────
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{{ refresh_sec }}">
<title>NIFTY Box Spread — Live</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#f0f2f5;color:#1a1a1a}
.topbar{background:#0f172a;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.t1{font-size:15px;font-weight:700;color:#f8fafc}
.t2{font-size:11px;color:#94a3b8;margin-top:2px}
.live{display:flex;align-items:center;gap:6px;font-size:12px;color:#94a3b8}
.dot{width:7px;height:7px;border-radius:50%;background:{% if authenticated and not global_error %}#22c55e{% else %}#ef4444{% endif %}}
.main{padding:16px 20px;max-width:1500px;margin:0 auto}
.err{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:10px 14px;color:#b91c1c;font-size:12px;margin-bottom:12px}
/* Expiry bar */
.ebar{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.elabel{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.eb{padding:4px 12px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;text-decoration:none;font-size:12px;color:#475569;font-weight:500}
.eb:hover{border-color:#94a3b8;color:#0f172a}
.eb.on{background:#0f172a;color:#fff;border-color:#0f172a}
.arbn{display:inline-block;margin-left:4px;background:#dcfce7;color:#15803d;border-radius:3px;padding:1px 4px;font-size:10px;font-weight:700}
.eb.on .arbn{background:#22c55e;color:#fff}
/* Scorecard */
.cards{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:14px}
@media(max-width:900px){.cards{grid-template-columns:repeat(3,1fr)}}
.card{background:#fff;border-radius:9px;padding:12px 14px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.cl{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px}
.cv{font-size:20px;font-weight:700;font-family:'Courier New',monospace}
.g{color:#16a34a}.a{color:#d97706}.r{color:#dc2626}.b{color:#2563eb}
/* Section */
.sec{background:#fff;border-radius:9px;box-shadow:0 1px 2px rgba(0,0,0,.06);margin-bottom:14px;overflow:hidden}
.sh{padding:10px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.sb{padding:14px 16px}
/* Assumptions grid */
.agrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media(max-width:800px){.agrid{grid-template-columns:repeat(2,1fr)}}
.arow{background:#f8fafc;border-radius:6px;padding:8px 10px;display:flex;justify-content:space-between;align-items:center}
.ak{font-size:11px;color:#64748b}
.av{font-size:13px;font-weight:600;font-family:'Courier New',monospace;color:#0f172a}
/* Tables */
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:11.5px}
th{background:#f1f5f9;padding:7px 10px;text-align:right;font-size:10px;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0;white-space:nowrap;text-transform:uppercase;letter-spacing:.3px}
th.l{text-align:left}
td{padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Courier New',monospace;white-space:nowrap}
td.l{text-align:left;font-family:inherit;font-weight:600}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;font-family:inherit}
.pg{background:#dcfce7;color:#15803d}
.pa{background:#fef3c7;color:#92400e}
.pr{background:#fee2e2;color:#b91c1c}
.ps{background:#f1f5f9;color:#64748b}
/* filters */
.fbar{display:flex;gap:5px;flex-wrap:wrap}
.fb{padding:3px 10px;border-radius:4px;border:1px solid #e2e8f0;background:#fff;text-decoration:none;font-size:11px;color:#64748b}
.fb:hover{border-color:#94a3b8}
.fb.on{background:#0f172a;color:#fff;border-color:#0f172a}
.empty{text-align:center;padding:40px;color:#94a3b8;font-size:13px}
.ref{font-size:11px;color:#94a3b8}
.na{color:#94a3b8}
</style>
</head>
<body>
<div class="topbar">
  <div>
    <div class="t1">NIFTY Box Spread Arbitrage Scanner</div>
    <div class="t2">
      {% if active %}{{ active }} &nbsp;·&nbsp; DTE: {{ d.get('dte','?') }} &nbsp;·&nbsp; CMP: ₹{{ "{:,.0f}".format(d.get('cmp',0) or 0) }} &nbsp;·&nbsp; Lot: {{ params.lot_size }}{% else %}Waiting for data...{% endif %}
    </div>
  </div>
  <div class="live">
    <div class="dot"></div>
    {% if not authenticated %}Not authenticated — <a href="/admin" style="color:#60a5fa">login</a>
    {% elif global_error %}<span style="color:#f87171">{{ global_error }}</span>
    {% else %}Live &nbsp;·&nbsp; Updated {{ last_fetch or '...' }} &nbsp;·&nbsp; Auto-refreshes every {{ refresh_sec }}s{% endif %}
  </div>
</div>

<div class="main">
{% if global_error %}<div class="err">{{ global_error }}</div>{% endif %}

<!-- EXPIRY TABS -->
<div class="ebar">
  <span class="elabel">Expiry</span>
  {% if expiries %}
    {% for e in expiries %}
      {% set ed = state_data.get(e, {}) %}
      {% set en = ed.get('arb_count', 0) %}
      <a href="/?expiry={{ e }}&sig={{ sig_filter }}" class="eb {% if e == active %}on{% endif %}">
        {{ e }}{% if en > 0 %}<span class="arbn">{{ en }}</span>{% endif %}
      </a>
    {% endfor %}
  {% else %}
    <span style="font-size:12px;color:#94a3b8">{% if authenticated %}Loading expiries...{% else %}Login at <a href="/admin">/admin</a> to load data{% endif %}</span>
  {% endif %}
</div>

<!-- SCORECARD -->
<div class="cards">
  <div class="card"><div class="cl">Complete Pairs</div><div class="cv b">{{ total }}</div></div>
  <div class="card"><div class="cl">Arbitrage ✔</div><div class="cv g">{{ arb }}</div></div>
  <div class="card"><div class="cl">Borderline ⚠</div><div class="cv a">{{ bord }}</div></div>
  <div class="card"><div class="cl">Loss ✘</div><div class="cv r">{{ loss }}</div></div>
  <div class="card"><div class="cl">Best P&L/lot</div><div class="cv g" style="font-size:14px">{{ inr(best) }}</div></div>
  <div class="card"><div class="cl">Max Ann. Return</div><div class="cv g" style="font-size:14px">{{ pct(maxann) }}</div></div>
</div>

<!-- ASSUMPTIONS -->
<div class="sec">
  <div class="sh">Assumptions (read-only)</div>
  <div class="sb">
    <div class="agrid">
      <div class="arow"><span class="ak">Lot Size (NIFTY)</span><span class="av">{{ params.lot_size }} units</span></div>
      <div class="arow"><span class="ak">Number of Lots</span><span class="av">{{ params.num_lots }}</span></div>
      <div class="arow"><span class="ak">Brokerage per Leg</span><span class="av">₹{{ params.broker_per_leg }}</span></div>
      <div class="arow"><span class="ak">GST on Brokerage</span><span class="av">{{ params.gst_pct }}%</span></div>
      <div class="arow"><span class="ak">Entry STT (sell legs)</span><span class="av">{{ params.stt_entry_pct }}%</span></div>
      <div class="arow"><span class="ak">Settlement STT</span><span class="av">{{ params.stt_settl_pct }}%</span></div>
      <div class="arow"><span class="ak">NSE Txn Charge</span><span class="av">{{ params.txn_pct }}%</span></div>
      <div class="arow"><span class="ak">SEBI Charge</span><span class="av">{{ params.sebi_pct }}%</span></div>
      <div class="arow"><span class="ak">Stamp Duty (buy side)</span><span class="av">{{ params.stamp_pct }}%</span></div>
      <div class="arow"><span class="ak">Slippage per Leg</span><span class="av">{{ params.slip_per_leg }} pts</span></div>
      <div class="arow"><span class="ak">Risk-Free Rate</span><span class="av">{{ params.rfr }}%</span></div>
      <div class="arow"><span class="ak">Min Ann. Return</span><span class="av">{{ params.min_ann_ret }}%</span></div>
      <div class="arow"><span class="ak">Max Spread %</span><span class="av">{{ params.max_spread_pct }}%</span></div>
      <div class="arow"><span class="ak">Fixed Cost/Box (excl STT)</span><span class="av">₹{{ "%.2f"|format(4 * params.broker_per_leg * (1 + params.gst_pct/100)) }}</span></div>
    </div>
  </div>
</div>

<!-- OPTION CHAIN -->
{% if chain %}
<div class="sec">
  <div class="sh">
    <span>Option Chain — {{ active }} ({{ chain|length }} strikes)</span>
    <span class="ref">Buy at Ask · Sell at Bid</span>
  </div>
  <div class="tw">
    <table>
      <thead><tr>
        <th class="l">Strike (K)</th>
        <th>Call Bid</th><th>Call Ask</th><th>Call Mid</th>
        <th>Call IV%</th><th>Call OI</th>
        <th>Put Bid</th><th>Put Ask</th><th>Put Mid</th>
        <th>Put IV%</th><th>Put OI</th>
        <th>Status</th>
      </tr></thead>
      <tbody>
      {% for s in chain %}
        {% set cmid = ((s.cb or 0) + (s.ca or 0)) / 2 if s.cb and s.ca else None %}
        {% set pmid = ((s.pb or 0) + (s.pa or 0)) / 2 if s.pb and s.pa else None %}
        {% set ok = s.cb is not none and s.ca is not none and s.pb is not none and s.pa is not none %}
        <tr>
          <td class="l" style="font-weight:700">{{ "{:,}".format(s.k|int) }}</td>
          <td>{% if s.cb is not none %}{{ "%.2f"|format(s.cb) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.ca is not none %}{{ "%.2f"|format(s.ca) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if cmid is not none %}{{ "%.2f"|format(cmid) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.civ is not none %}{{ "%.1f"|format(s.civ) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.coi is not none %}{{ "{:,}".format(s.coi|int) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.pb is not none %}{{ "%.2f"|format(s.pb) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.pa is not none %}{{ "%.2f"|format(s.pa) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if pmid is not none %}{{ "%.2f"|format(pmid) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.piv is not none %}{{ "%.1f"|format(s.piv) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if s.poi is not none %}{{ "{:,}".format(s.poi|int) }}{% else %}<span class="na">—</span>{% endif %}</td>
          <td>{% if ok %}<span class="pill pg">✔ Active</span>{% else %}<span class="pill ps">⚠ Partial</span>{% endif %}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}

<!-- BOX SPREAD ANALYSIS -->
<div class="sec">
  <div class="sh">
    <span>Box Spread Analysis — {{ total }} complete pairs</span>
    <div class="fbar">
      <a href="/?expiry={{ active }}&sig=all"   class="fb {% if sig_filter=='all' %}on{% endif %}">All ({{ total }})</a>
      <a href="/?expiry={{ active }}&sig=execute"    class="fb {% if sig_filter=='execute' %}on{% endif %}">✔ Execute ({{ arb }})</a>
      <a href="/?expiry={{ active }}&sig=borderline" class="fb {% if sig_filter=='borderline' %}on{% endif %}">⚠ Borderline ({{ bord }})</a>
      <a href="/?expiry={{ active }}&sig=loss"       class="fb {% if sig_filter=='loss' %}on{% endif %}">✘ Loss ({{ loss }})</a>
    </div>
  </div>
  <div class="tw">
    <table>
      <thead><tr>
        <th class="l">K1</th><th class="l">K2</th><th>Width</th><th>DTE</th>
        <th>C Ask(K1)</th><th>C Bid(K2)</th><th>P Ask(K2)</th><th>P Bid(K1)</th>
        <th>Net Debit</th><th>Box Value</th>
        <th>Entry STT</th><th>Settl. STT</th><th>Other Costs</th>
        <th>Net P&L</th><th>Return%</th><th>Ann.%</th><th>Spread%</th><th>Signal</th>
      </tr></thead>
      <tbody>
      {% if pairs %}
        {% for p in pairs %}
        <tr>
          <td class="l">{{ "{:,}".format(p.k1|int) }}</td>
          <td class="l">{{ "{:,}".format(p.k2|int) }}</td>
          <td>{{ "{:,}".format(p.box_w|int) }}</td>
          <td>{{ d.get('dte','?') }}</td>
          <td>{{ "%.2f"|format(p.ca1) }}</td>
          <td>{{ "%.2f"|format(p.cb2) }}</td>
          <td>{{ "%.2f"|format(p.pa2) }}</td>
          <td>{{ "%.2f"|format(p.pb1) }}</td>
          <td>{{ inr(p.net_debit) }}</td>
          <td>{{ inr(p.box_value) }}</td>
          <td>{{ inr(p.entry_stt) }}</td>
          <td>{{ inr(p.settl_stt) }}</td>
          <td>{{ inr(p.other_costs) }}</td>
          <td style="font-weight:700;color:{% if p.net_pnl >= 0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(p.net_pnl) }}</td>
          <td style="color:{% if p.ret_pct >= 0 %}#16a34a{% else %}#dc2626{% endif %}">{{ pct(p.ret_pct) }}</td>
          <td style="font-weight:700;color:{% if p.ann_ret >= 1 %}#16a34a{% elif p.ann_ret >= 0 %}#d97706{% else %}#dc2626{% endif %}">{{ pct(p.ann_ret) }}</td>
          <td>{% if p.spread_pct is not none %}{{ "%.2f"|format(p.spread_pct) }}%{% else %}—{% endif %}</td>
          <td>
            {% if p.signal == 'execute' %}<span class="pill pg">✅ EXECUTE</span>
            {% elif p.signal == 'borderline' %}<span class="pill pa">⚠ BORDERLINE</span>
            {% else %}<span class="pill pr">❌ AVOID</span>{% endif %}
          </td>
        </tr>
        {% endfor %}
      {% else %}
        <tr><td colspan="18"><div class="empty">{% if not authenticated %}Login at /admin to load data{% elif not active %}Select an expiry above{% else %}No complete pairs for this expiry{% endif %}</div></td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>
</div>

<div style="text-align:center;font-size:11px;color:#94a3b8;padding-bottom:20px">
  Live data via Fyers API v3 &nbsp;·&nbsp; NSE European-style cash-settled index options &nbsp;·&nbsp; Not financial advice &nbsp;·&nbsp; Page auto-refreshes every {{ refresh_sec }}s
</div>
</div>
</body></html>"""

ADMIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#f1f5f9;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.box{background:#fff;border-radius:12px;padding:36px;width:100%;max-width:480px;box-shadow:0 4px 20px rgba(0,0,0,.1)}
h1{font-size:20px;margin-bottom:6px}p{font-size:13px;color:#64748b;margin-bottom:20px;line-height:1.5}
label{display:block;font-size:12px;color:#64748b;margin-bottom:4px;font-weight:600}
input[type=password]{width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;margin-bottom:14px}
.btn{display:block;width:100%;padding:11px;background:#0f172a;color:#fff;border:none;border-radius:7px;font-size:14px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none;margin-bottom:8px}
.btn-f{background:#ff6600}.err{background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:10px;color:#b91c1c;font-size:13px;margin-bottom:14px}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px;color:#15803d;font-size:13px;margin-bottom:14px}
.stat{background:#f8fafc;border-radius:8px;padding:14px;font-size:12px;color:#475569;margin-bottom:16px;line-height:2}
.stat b{color:#0f172a}hr{border:none;border-top:1px solid #e2e8f0;margin:20px 0}a{color:#2563eb;font-size:13px}
</style></head><body><div class="box">
  <h1>Scanner Admin</h1>
  <p>Only for you. Share the main URL (<a href="/">/</a>) with everyone else.</p>
  {% if not logged_in %}
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST"><label>Admin password</label>
    <input type="password" name="password" autofocus>
    <button type="submit" class="btn">Login</button></form>
  {% else %}
    {% if request.args.get('success') %}<div class="ok">✓ Fyers login successful! Fetching all expiries now.</div>{% endif %}
    <div class="stat">
      <b>Auth:</b> {{ '✓ Token active today' if state.access_token else '✗ No token' }}<br>
      <b>Expiries:</b> {{ state.expiries|length }} loaded{% if state.expiries %} ({{ ', '.join(state.expiries[:3]) }}...){% endif %}<br>
      <b>Last fetch:</b> {{ state.last_fetch or 'Never' }}<br>
      {% if state.global_error %}<b>Error:</b> <span style="color:#dc2626">{{ state.global_error }}</span>{% endif %}
    </div>
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">Fyers tokens expire at midnight. Click below each morning before market opens.</p>
    {% if auth_url %}<a href="{{ auth_url }}" class="btn btn-f">Login with Fyers (refresh token) →</a>{% endif %}
    <hr><a href="/">← Dashboard</a> &nbsp;·&nbsp; <a href="/admin/logout">Logout</a>
  {% endif %}
</div></body></html>"""

def startup():
    if is_authenticated():
        print("Token found — fetching data")
        threading.Thread(target=fetch_all, daemon=True).start()
    else:
        print("No token — visit /admin")
    threading.Thread(target=refresh_loop, daemon=True).start()

# Pass state_data to template via context processor
@app.context_processor
def inject_state():
    sd = {}
    for exp, d in state["data"].items():
        sd[exp] = {"arb_count": sum(1 for p in d.get("pairs", []) if p["signal"] == "execute")}
    return {"state_data": sd, "state": state}


@app.route("/debug")
def debug():
    out = {"expiries": state["expiries"], "global_error": state["global_error"],
           "last_fetch": state["last_fetch"], "authenticated": is_authenticated()}
    for exp, d in state["data"].items():
        out[exp] = {
            "error": d.get("error"),
            "cmp": d.get("cmp"),
            "dte": d.get("dte"),
            "chain_len": len(d.get("chain", [])),
            "pairs_len": len(d.get("pairs", [])),
            "first_chain": d.get("chain", [])[:2],
        }
    return jsonify(out)

startup()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
