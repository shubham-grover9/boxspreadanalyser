import os, json, time, threading, hashlib, secrets
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, jsonify, session, url_for

# ── DATABASE (Railway Postgres) ───────────────────────────────────────────────
def get_db():
    try:
        import psycopg2
        url = os.environ.get("DATABASE_URL","")
        if not url: return None
        return psycopg2.connect(url, sslmode="require")
    except Exception as e:
        print(f"DB connect: {e}"); return None

def init_db():
    conn = get_db()
    if not conn:
        print("⚠ No DATABASE_URL — history disabled"); return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id            SERIAL PRIMARY KEY,
                    logged_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expiry        TEXT,
                    k1            INTEGER, k2 INTEGER, box_w INTEGER, dte INTEGER,
                    ca1 NUMERIC, cb2 NUMERIC, pa2 NUMERIC, pb1 NUMERIC,
                    net_debit NUMERIC, box_value NUMERIC,
                    entry_stt NUMERIC, settl_stt NUMERIC, other_costs NUMERIC,
                    net_pnl NUMERIC, ann_ret NUMERIC,
                    adj_net_pnl NUMERIC, adj_ann_ret NUMERIC,
                    spread_pct NUMERIC, impact_cost NUMERIC,
                    exec_difficulty TEXT, oi_flag TEXT,
                    signal TEXT, signal_basis TEXT,
                    hold_to_expiry BOOLEAN DEFAULT TRUE,
                    logic_snapshot JSONB
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_opp_time ON opportunities(logged_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_opp_pair ON opportunities(expiry,k1,k2)")
        conn.commit()
        print("✓ DB ready")
    except Exception as e:
        print(f"DB init error: {e}")
    finally:
        conn.close()

def log_opportunities(execute_pairs, expiry, hold_to_expiry=True):
    """Log all Execute-signal pairs to DB with full logic snapshot."""
    if not execute_pairs: return
    conn = get_db()
    if not conn: return
    try:
        snapshot = {k: v for k,v in PARAMS.items() if k != "hold_to_expiry"}
        import json as _json
        snap_json = _json.dumps(snapshot)
        with conn.cursor() as cur:
            for p in execute_pairs:
                cur.execute("""
                    INSERT INTO opportunities (
                        expiry,k1,k2,box_w,dte,
                        ca1,cb2,pa2,pb1,
                        net_debit,box_value,entry_stt,settl_stt,other_costs,
                        net_pnl,ann_ret,adj_net_pnl,adj_ann_ret,
                        spread_pct,impact_cost,exec_difficulty,oi_flag,
                        signal,signal_basis,hold_to_expiry,logic_snapshot
                    ) VALUES (
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s
                    )""", (
                    expiry, p.get("k1"), p.get("k2"), p.get("box_w"), p.get("dte_val"),
                    p.get("ca1"), p.get("cb2"), p.get("pa2"), p.get("pb1"),
                    p.get("net_debit"), p.get("box_value"),
                    p.get("entry_stt"), p.get("settl_stt"), p.get("other_costs"),
                    p.get("net_pnl"), p.get("ann_ret"),
                    p.get("adj_net_pnl"), p.get("adj_ann_ret"),
                    p.get("spread_pct"), p.get("impact_cost"),
                    p.get("exec_difficulty"), p.get("oi_flag"),
                    p.get("signal"), p.get("signal_basis"),
                    hold_to_expiry, snap_json
                ))
        conn.commit()
    except Exception as e:
        print(f"DB log error: {e}")
    finally:
        conn.close()

def get_history(limit=200):
    """Fetch recent opportunity history from DB."""
    conn = get_db()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, logged_at, expiry, k1, k2, box_w, dte,
                       ca1, cb2, pa2, pb1,
                       net_debit, box_value, entry_stt, settl_stt, other_costs,
                       net_pnl, ann_ret, adj_net_pnl, adj_ann_ret,
                       spread_pct, impact_cost, exec_difficulty, oi_flag,
                       signal, signal_basis, hold_to_expiry, logic_snapshot
                FROM opportunities
                ORDER BY logged_at DESC
                LIMIT %s
            """, (limit,))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"DB fetch error: {e}"); return []
    finally:
        conn.close()


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

FYERS_CLIENT_ID  = os.environ.get("FYERS_CLIENT_ID", "")
FYERS_SECRET_KEY = os.environ.get("FYERS_SECRET_KEY", "")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "changeme")
APP_URL          = os.environ.get("APP_URL", "http://localhost:5000")
REFRESH_SEC      = int(os.environ.get("REFRESH_SECONDS", "60"))

PARAMS = {
    "lot_size":       int(os.environ.get("LOT_SIZE", "65")),
    "num_lots":       int(os.environ.get("NUM_LOTS", "1")),
    "broker_per_leg": float(os.environ.get("BROKER_PER_LEG", "20")),
    "stt_entry_pct":  float(os.environ.get("STT_ENTRY_PCT", "0.10")),
    "stt_settl_pct":  float(os.environ.get("STT_SETTL_PCT", "0.125")),
    "txn_pct":        float(os.environ.get("TXN_PCT", "0.03503")),
    "sebi_pct":       float(os.environ.get("SEBI_PCT", "0.0001")),
    "gst_pct":        float(os.environ.get("GST_PCT", "18")),
    "stamp_pct":      float(os.environ.get("STAMP_PCT", "0.003")),
    "slip_per_leg":   float(os.environ.get("SLIP_PER_LEG", "0.5")),
    "rfr":            float(os.environ.get("RFR", "6.5")),
    "min_ann_ret":    float(os.environ.get("MIN_ANN_RET", "12.0")),
    "max_spread_pct": float(os.environ.get("MAX_SPREAD_PCT", "1.0")),
    "hold_to_expiry": True,  # toggled per-request, not an env var
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
    txn_charge = (p["txn_pct"]  / 100) * tp
    sebi_charge = (p["sebi_pct"] / 100) * tp
    brokerage   = 4 * p["broker_per_leg"]
    gst         = (p["gst_pct"]  / 100) * (brokerage + txn_charge + sebi_charge)
    stamp       = (p["stamp_pct"] / 100) * (ca1 + pa2) * lots
    slip        = 4 * p["slip_per_leg"] * lots
    other = txn_charge + sebi_charge + brokerage + gst + stamp + slip
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
        # Dynamic slippage: scale with spread width and depth
        "spread_slip": round((sp / 100 * box_w * PARAMS["lot_size"] * 0.5) if sp else 4 * PARAMS["slip_per_leg"] * PARAMS["lot_size"], 0),
    }

def depth_capacity(depth_map, sym, direction, slippage_pct=0.5):
    """How many lots can be filled within slippage_pct% of mid price?"""
    d = depth_map.get(sym, {})
    book = d.get("ask", []) if direction == "buy" else d.get("bids", [])
    bid1 = (d.get("bids") or [{}])[0].get("price")
    ask1 = (d.get("ask") or [{}])[0].get("price")
    if not book or not bid1 or not ask1:
        return None
    mid = (bid1 + ask1) / 2
    limit = mid * (1 + slippage_pct/100) if direction == "buy" else mid * (1 - slippage_pct/100)
    fillable_units = 0
    for level in book:
        price = level.get("price", 0)
        vol   = level.get("volume", 0)
        within = price <= limit if direction == "buy" else price >= limit
        if within:
            fillable_units += vol
        else:
            break
    lot_size = PARAMS["lot_size"]
    return int(fillable_units / lot_size) if lot_size else 0


def calc_impact_cost(depth_map, sym_ca, dir_ca, qty_ca, sym_cb, dir_cb, qty_cb,
                     sym_pa, dir_pa, qty_pa, sym_pb, dir_pb, qty_pb):
    """Walk the order book for each of 4 legs and compute total impact cost in ₹."""
    def walk_book(sym, direction, qty_units):
        """Walk bids (for sell) or asks (for buy) to find average fill price."""
        d = depth_map.get(sym, {})
        book = d.get("ask", []) if direction == "buy" else d.get("bids", [])
        if not book:
            return None, None
        mid = None
        bid1 = d.get("bids", [{}])[0].get("price") if d.get("bids") else None
        ask1 = d.get("ask", [{}])[0].get("price") if d.get("ask") else None
        if bid1 and ask1:
            mid = (bid1 + ask1) / 2
        remaining = qty_units
        total_cost = 0
        for level in book:
            price = level.get("price", 0)
            vol   = level.get("volume", 0)
            fill  = min(vol, remaining)
            total_cost += price * fill
            remaining  -= fill
            if remaining <= 0:
                break
        if remaining > 0:
            return None, None  # Not enough liquidity
        avg_price = total_cost / qty_units
        return avg_price, mid

    total_impact = 0
    details = []
    for sym, direction, qty in [(sym_ca,dir_ca,qty_ca),(sym_cb,dir_cb,qty_cb),
                                  (sym_pa,dir_pa,qty_pa),(sym_pb,dir_pb,qty_pb)]:
        avg, mid = walk_book(sym, direction, qty)
        if avg is None or mid is None:
            details.append(None)
            continue
        # Impact = difference between fill price and mid, × qty
        impact = abs(avg - mid) * qty
        total_impact += impact
        details.append(round(impact, 2))

    if not any(d is not None for d in details):
        return {"total_impact": None, "impact_pct": None, "flag": "⚪ No depth data"}

    none_count = sum(1 for d in details if d is None)
    if none_count > 0:
        flag = "🟡 Partial depth"
    elif total_impact == 0:
        flag = "🟢 Low impact"
    elif total_impact < 500:
        flag = "🟢 Low impact"
    elif total_impact < 2000:
        flag = "🟡 Moderate impact"
    else:
        flag = "🔴 High impact — arb may not execute at quoted prices"

    return {"total_impact": round(total_impact, 0), "impact_pct": None, "flag": flag}


def fetch_one(fyers, raw_expiry):
    try:
        resp = fyers.optionchain(data={
            "symbol": "NSE:NIFTY50-INDEX",
            "strikecount": "",
            "timestamp": str(raw_expiry),
        })
        if resp.get("s") != "ok":
            return {"error": resp.get("message", "API error"), "chain": [], "pairs": [], "cmp": None, "dte": None}

        opt  = resp.get("data", {})
        cmp  = None
        chain_dict   = {}
        chain_sym_map = {}

        for row in opt.get("optionsChain", []):
            ot = row.get("option_type", "")
            k  = row.get("strike_price")
            if ot == "" and (k is None or k == -1):
                if cmp is None: cmp = row.get("ltp")
                continue
            if k is None or k <= 0: continue
            k = int(k)  # normalise to int — Fyers returns floats
            if k not in chain_dict:
                chain_dict[k] = {"k": k, "cb": None, "ca": None,
                                  "pb": None, "pa": None,
                                  "civ": None, "piv": None,
                                  "coi": None, "poi": None,
                                  "ce_sym": None, "pe_sym": None}
            if ot == "CE":
                chain_dict[k]["cb"]     = row.get("bid") or None
                chain_dict[k]["ca"]     = row.get("ask") or None
                chain_dict[k]["civ"]    = row.get("iv")  or None
                chain_dict[k]["coi"]    = row.get("oi")  or None
                chain_dict[k]["ce_sym"] = row.get("symbol")
            elif ot == "PE":
                chain_dict[k]["pb"]     = row.get("bid") or None
                chain_dict[k]["pa"]     = row.get("ask") or None
                chain_dict[k]["piv"]    = row.get("iv")  or None
                chain_dict[k]["poi"]    = row.get("oi")  or None
                chain_dict[k]["pe_sym"] = row.get("symbol")

        for k, s in chain_dict.items():
            chain_sym_map[int(k)] = {"ce_sym": s.get("ce_sym"), "pe_sym": s.get("pe_sym")}

        chain = sorted(chain_dict.values(), key=lambda x: x["k"])
        dte   = expiry_dte(raw_expiry)

        # ── STAGE 1: PRE-FILTER ──────────────────────────────────────────────
        # Layer 1: Active quotes — both bid AND ask non-zero on all 4 legs
        # Layer 2: Top N strikes by combined OI (call OI + put OI)
        #          Adapts automatically — works for near and far expiries
        # Layer 3: Max box width — skip pairs wider than MAX_WIDTH pts
        MAX_WIDTH    = int(os.environ.get("MAX_BOX_WIDTH", "3000"))
        TOP_STRIKES  = int(os.environ.get("TOP_STRIKES", "20"))

        # Layer 1: active quotes only
        active_chain = [s for s in chain
                        if s.get("cb") and s.get("ca")
                        and s.get("pb") and s.get("pa")]

        # Layer 2: rank by combined OI, take top N
        def combined_oi(s):
            return (s.get("coi") or 0) + (s.get("poi") or 0)

        active_chain.sort(key=combined_oi, reverse=True)
        top_strikes  = active_chain[:TOP_STRIKES]
        # Re-sort by strike price for pair computation
        liquid_chain = sorted(top_strikes, key=lambda x: x["k"])

        # ── STAGE 1: PAIR COMPUTATION (only liquid strikes, limited width) ────
        pairs = []
        for i in range(len(liquid_chain)):
            for j in range(i + 1, len(liquid_chain)):
                s1, s2 = liquid_chain[i], liquid_chain[j]
                if (s2["k"] - s1["k"]) > MAX_WIDTH:
                    break  # chain is sorted, no point checking wider
                r = calc_pair(s1, s2, dte)
                if r:
                    r["dte_val"] = dte
                    pairs.append(r)

        # Initial sort by raw ann_ret (depth not yet computed)
        pairs.sort(key=lambda x: x["ann_ret"], reverse=True)

        # ── STAGE 2: BATCH DEPTH FETCH FOR ALL CANDIDATE PAIRS ───────────────
        # Fetch depth for ALL pairs that passed Stage 1 (not just top 20)
        # Fyers depth API accepts up to 20 symbols per call — batch accordingly
        candidates = [p for p in pairs if p["signal"] in ("execute", "borderline")]

        if candidates and fyers:
            # Collect all unique symbols needed
            all_syms = set()
            for p in candidates:
                for k in [p["k1"], p["k2"]]:
                    sm = chain_sym_map.get(int(k), {})
                    if sm.get("ce_sym"): all_syms.add(sm["ce_sym"])
                    if sm.get("pe_sym"): all_syms.add(sm["pe_sym"])

            # Batch into groups of 20 and fetch
            sym_list  = list(all_syms)
            depth_map = {}
            depth_errors = []
            print(f"[DEPTH] Fetching depth for {len(sym_list)} symbols across {len(candidates)} candidates")
            for i in range(0, len(sym_list), 20):
                batch = sym_list[i:i+20]
                try:
                    dr = fyers.depth(data={"symbol": ",".join(batch), "ohlcv_flag": 0})
                    if dr.get("s") == "ok":
                        depth_map.update(dr.get("d", {}))
                        print(f"[DEPTH] Batch {i//20+1}: got {len(dr.get('d',{}))} entries")
                    else:
                        depth_errors.append(f"Batch {i//20+1}: {dr.get('message','')}")
                        print(f"[DEPTH] Batch {i//20+1} error: {dr.get('message','')}")
                    time.sleep(0.15)
                except Exception as e:
                    depth_errors.append(str(e))
                    print(f"[DEPTH] Exception: {e}")
            print(f"[DEPTH] Total symbols in depth_map: {len(depth_map)}")

            # ── STAGE 2: IMPACT COST + DEPTH CAPACITY FOR ALL CANDIDATES ─────
            # Capital-aware: use lots_possible from capital (passed via pair) if available
            # else fall back to PARAMS num_lots
            lots          = PARAMS["lot_size"] * PARAMS["num_lots"]
            baseline_slip = 4 * PARAMS["slip_per_leg"] * PARAMS["lot_size"] * PARAMS["num_lots"]

            for p in candidates:
                s1 = chain_sym_map.get(int(p["k1"]), {})
                s2 = chain_sym_map.get(int(p["k2"]), {})
                # Capital-aware: impact cost should reflect actual intended position size
                # This is stored on the pair after enrichment; use num_lots as proxy here
                desired_lots = p.get("capital_lots", PARAMS["num_lots"])
                legs = [
                    (s1.get("ce_sym", ""), "buy"),
                    (s2.get("ce_sym", ""), "sell"),
                    (s2.get("pe_sym", ""), "buy"),
                    (s1.get("pe_sym", ""), "sell"),
                ]

                # All 4 legs must have depth — otherwise mark non-executable
                caps = []
                all_have_depth = True
                for sym, dirn in legs:
                    if not sym:
                        all_have_depth = False; break
                    c = depth_capacity(depth_map, sym, dirn, slippage_pct=0.5)
                    if c is None:
                        all_have_depth = False; break
                    caps.append(c)

                if not all_have_depth:
                    p["impact_cost"]  = None
                    p["ic_flag"]      = "⚫ Incomplete depth"
                    p["adj_net_pnl"]  = None
                    p["signal"]       = "borderline"
                    p["signal_basis"] = "no_depth"
                    continue

                # Depth capacity — bottleneck is weakest leg
                depth_lots = min(caps)
                p["depth_capacity"] = depth_lots
                if depth_lots == 0:
                    p["oi_flag"] = "⛔ No depth"
                    p["oi_note"] = "Zero lots fillable within 0.5% slippage"
                    p["signal"]  = "borderline"
                elif desired_lots > depth_lots:
                    p["oi_flag"] = f"🔴 Depth limit: {depth_lots} lots"
                    p["oi_note"] = f"Book absorbs {depth_lots} lots (you want {desired_lots})"
                    p["depth_capped_lots"] = depth_lots
                else:
                    p["oi_flag"] = f"🟢 Depth OK: {depth_lots} lots"
                    p["oi_note"] = f"Book absorbs {desired_lots} lots within 0.5% slippage"

                # Impact cost — walk order book for all 4 legs
                ic = calc_impact_cost(depth_map,
                    s1.get("ce_sym",""), "buy",  lots,
                    s2.get("ce_sym",""), "sell", lots,
                    s2.get("pe_sym",""), "buy",  lots,
                    s1.get("pe_sym",""), "sell", lots,
                )
                p["impact_cost"] = ic["total_impact"]
                p["ic_flag"]     = ic["flag"]

                # Adjusted P&L — subtract only incremental impact above baseline
                if ic["total_impact"] is not None:
                    incremental = max(0, ic["total_impact"] - baseline_slip)
                    adj = round(p["net_pnl"] - incremental, 0)
                else:
                    adj = None
                p["adj_net_pnl"] = adj

                # Rescore signal on adjusted P&L (the realistic number)
                if adj is not None:
                    adj_ann = (adj / p["net_debit"] * 100 * 365 /
                               max(1, p.get("dte_val", 90))) if p["net_debit"] else 0
                    p["adj_ann_ret"] = round(adj_ann, 2)
                    if adj <= 0 or depth_lots == 0:
                        p["signal"]       = "loss"
                        p["signal_basis"] = "adj"
                    elif adj_ann < PARAMS["min_ann_ret"]:
                        p["signal"]       = "borderline"
                        p["signal_basis"] = "adj"
                    else:
                        p["signal_basis"] = "adj"

        # Final sort by adj_ann_ret where available (realistic), else raw ann_ret
        pairs.sort(
            key=lambda x: x.get("adj_ann_ret") if x.get("adj_ann_ret") is not None else x["ann_ret"],
            reverse=True
        )

        return {
            "error": None, "chain": chain, "liquid_chain": liquid_chain, "pairs": pairs,
            "cmp": cmp, "dte": dte,
            "pre_filter_stats": {
                "total_strikes":  len(chain),
                "active_strikes": len(active_chain) if 'active_chain' in dir() else 0,
                "liquid_strikes": len(liquid_chain),
                "total_pairs":    len(pairs),
                "candidates_with_depth": len(candidates) if 'candidates' in dir() else 0,
            }
        }
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
            result = fetch_one(fyers, raw)
            state["data"][disp] = result
            # Log any execute signals to DB
            exec_pairs = [p for p in result.get("pairs",[]) if p.get("signal") == "execute"]
            if exec_pairs:
                threading.Thread(target=log_opportunities,
                    args=(exec_pairs, disp, True), daemon=True).start()
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
    all_pairs = d.get("pairs", [])
    pre_stats = d.get("pre_filter_stats", {})
    sig_filter = request.args.get("sig", "all")
    # Tax bracket
    try:
        tax_rate = float(request.args.get("tax", "30"))
    except Exception:
        tax_rate = 30.0
    # Capital
    try:
        capital = float(request.args.get("capital", "300000"))
    except Exception:
        capital = 300000.0
    hold_to_expiry = request.args.get("hold", "1") != "0"
    # Filter pairs
    pairs = all_pairs if sig_filter == "all" else [p for p in all_pairs if p["signal"] == sig_filter]
    # Use effective signal — hte_signal when early exit mode, else raw signal
    # But hte_signal is computed in enrichment loop below, so we need two passes
    # Pass 1: quick count using raw signal (updated after enrichment)
    arb  = sum(1 for p in all_pairs if p["signal"] == "execute")
    bord = sum(1 for p in all_pairs if p["signal"] == "borderline")
    loss = sum(1 for p in all_pairs if p["signal"] == "loss")
    best    = max((p["net_pnl"]  for p in all_pairs), default=None)
    maxann  = max((p["ann_ret"]  for p in all_pairs), default=None)
    # Enrich pairs with post-tax return and capital analysis
    enriched = []
    chain_by_k = {s["k"]: s for s in d.get("chain", [])}
    for p in pairs:
        lots_possible = int(capital // p["net_debit"]) if p["net_debit"] > 0 else 0

        # If not holding to expiry: settlement STT = 0, but add back bid-ask exit cost estimate
        # Exit cost ≈ spread_pct% of box value (cost to unwind all 4 legs at market)
        if not hold_to_expiry and p.get("settl_stt", 0):
            exit_cost = (p.get("spread_pct", 0) or 0) / 100 * p["box_value"]
            adj_pnl_hte = round(p["net_pnl"] + p["settl_stt"] - exit_cost, 0)
            adj_ann_hte = round((adj_pnl_hte / p["net_debit"] * 100 * 365 / max(1, d.get("dte",90))) if p["net_debit"] else 0, 2)
        else:
            adj_pnl_hte = None
            adj_ann_hte = None

        total_pnl = p["net_pnl"] * lots_possible if lots_possible > 0 else None
        post_tax_ann  = p["ann_ret"] * (1 - tax_rate / 100) if p["ann_ret"] is not None else None
        adj_total_pnl = (p.get("adj_net_pnl", p["net_pnl"]) or p["net_pnl"]) * lots_possible if lots_possible > 0 else None

        # FIX 3: Depth-based capacity (better than OI)
        # We'll populate this after depth data is available; for now use OI as fallback
        s1 = chain_by_k.get(p["k1"], {})
        s2 = chain_by_k.get(p["k2"], {})
        coi1 = s1.get("coi"); poi1 = s1.get("poi")
        coi2 = s2.get("coi"); poi2 = s2.get("poi")
        leg_ois = [x for x in [coi1, coi2, poi2, poi1] if x is not None and x > 0]
        bottleneck_oi = min(leg_ois) if leg_ois else None
        oi_flag = "⚫ No OI data"; oi_pct = None; oi_note = None
        if bottleneck_oi and lots_possible > 0:
            oi_pct = (lots_possible / bottleneck_oi * 100) if bottleneck_oi > 0 else None
            if oi_pct is not None:
                if oi_pct < 1:
                    oi_flag = "🟢 OK (OI)"
                    oi_note = f"{oi_pct:.2f}% of bottleneck OI — use depth check for precision"
                elif oi_pct < 5:
                    oi_flag = "🟡 Caution (OI)"
                    oi_note = f"{oi_pct:.1f}% of OI — depth may be thinner than OI suggests"
                elif oi_pct < 15:
                    oi_flag = "🔴 High Risk (OI)"
                    oi_note = f"{oi_pct:.1f}% of OI — likely to move prices"
                else:
                    oi_flag = "⛔ Avoid (OI)"
                    oi_note = f"{oi_pct:.1f}% of OI — order will exhaust available liquidity"
        elif bottleneck_oi == 0:
            oi_flag = "⛔ No liquidity"; oi_note = "OI is zero on at least one leg"

        # FIX 4: Execution difficulty score
        sp_pct = p.get("spread_pct") or 999
        ic_amt  = p.get("impact_cost") or 0
        depth_c = p.get("depth_capacity")
        exec_score = 0
        exec_reasons = []

        # Spread width scoring
        if sp_pct < 0.3:
            exec_score += 2
        elif sp_pct < 0.7:
            exec_score += 1
            exec_reasons.append(f"Spread {sp_pct:.1f}% is moderate")
        elif sp_pct < 999:
            exec_reasons.append(f"Wide spread {sp_pct:.1f}% — hard to fill at quoted price")

        # Impact cost scoring
        if ic_amt == 0 or ic_amt is None:
            # Don't penalise or explain missing depth — it's a known API limitation
            # Impact cost unavailable — score neutrally, explain via spread only
            pass
        elif ic_amt < 200:
            exec_score += 2
        elif ic_amt < 1000:
            exec_score += 1
            exec_reasons.append(f"Moderate market impact ~₹{ic_amt:,.0f}")
        else:
            exec_reasons.append(f"High market impact ~₹{ic_amt:,.0f} — your order will move prices")

        # Depth capacity scoring
        if depth_c is None:
            # Known limitation — don't surface as a reason
            pass
        elif depth_c == 0:
            exec_reasons.append("Zero lots fillable at quoted price — strike is effectively illiquid")
        elif depth_c >= lots_possible:
            exec_score += 2
        elif depth_c > 0:
            exec_score += 1
            exec_reasons.append(f"Book can only absorb {depth_c} lots (you need {lots_possible})")

        if   exec_score >= 5:
            exec_difficulty = "🟢 Easy"
        elif exec_score >= 3:
            exec_difficulty = "🟡 Medium"
        elif exec_score >= 1:
            exec_difficulty = "🔴 Hard"
            if not exec_reasons:
                exec_reasons.append("Wide bid-ask spread — quoted price may not be your fill price")
        else:
            exec_difficulty = "⛔ Very Hard"
            if not exec_reasons:
                exec_reasons.append("Very wide spread — execution at theoretical price is unlikely")

        exec_reason_str = " · ".join(exec_reasons) if exec_reasons else ""

        # FIX 5: Quote staleness — flag if spread looks stale (zero volume proxy)
        # We don't have last_trade_time from optionchain, but flag zero-bid as suspect
        stale_flag = None
        if p.get("ca1",0) == 0 or p.get("pb1",0) == 0 or p.get("cb2",0) == 0 or p.get("pa2",0) == 0:
            stale_flag = "⚠ Suspect — zero quote on a leg"

        # Effective P&L: use early-exit adjusted if not holding to expiry
        effective_pnl = adj_pnl_hte if (not hold_to_expiry and adj_pnl_hte is not None) else p["net_pnl"]
        effective_ann = adj_ann_hte if (not hold_to_expiry and adj_ann_hte is not None) else p["ann_ret"]

        # Rescore signal for early exit scenario
        if not hold_to_expiry and adj_pnl_hte is not None:
            if adj_pnl_hte <= 0:
                hte_signal = "loss"
            elif adj_ann_hte < PARAMS["min_ann_ret"]:
                hte_signal = "borderline"
            elif (p.get("spread_pct") or 99) < PARAMS["max_spread_pct"]:
                hte_signal = "execute"
            else:
                hte_signal = "borderline"
        else:
            hte_signal = p["signal"]

        # 1-line signal reason
        raw_sig = p["signal"]
        eff = hte_signal
        if eff == "execute":
            signal_reason = f"Ann% {p['ann_ret']:.1f}% beats {PARAMS['min_ann_ret']}% min · spread {p.get('spread_pct',0):.1f}% is tight"
        elif eff == "borderline":
            if p["net_pnl"] <= 0:
                signal_reason = "Net loss after all costs including settlement STT"
            elif p["ann_ret"] < PARAMS["min_ann_ret"]:
                signal_reason = f"Returns {p['ann_ret']:.1f}% p.a. — below {PARAMS['min_ann_ret']}% target"
            elif (p.get("spread_pct") or 99) >= PARAMS["max_spread_pct"]:
                signal_reason = f"Spread {p.get('spread_pct',0):.1f}% too wide — quoted price may not be your fill"
            elif p.get("signal_basis") == "adj":
                signal_reason = f"Impact cost reduces adj return below threshold"
            else:
                signal_reason = "Marginally profitable but below execution quality threshold"
        else:
            if p["net_pnl"] <= 0:
                signal_reason = "Net loss — settlement STT alone wipes the profit margin"
            else:
                signal_reason = f"Ann% {p['ann_ret']:.1f}% is negative or near zero after all costs"

        enriched.append({**p,
            "lots_possible": lots_possible,
            "total_pnl":     round(total_pnl, 0) if total_pnl is not None else None,
            "adj_total_pnl": round(adj_total_pnl, 0) if adj_total_pnl is not None else None,
            "post_tax_ann":  round(post_tax_ann, 2) if post_tax_ann is not None else None,
            "oi_flag": oi_flag, "oi_pct": round(oi_pct, 2) if oi_pct else None,
            "oi_note": oi_note, "bottleneck_oi": bottleneck_oi,
            "exec_difficulty": exec_difficulty,
            "exec_reason": exec_reason_str,
            "stale_flag": stale_flag,
            "adj_pnl_hte":  adj_pnl_hte,
            "adj_ann_hte":  adj_ann_hte,
            "effective_pnl": effective_pnl,
            "effective_ann": effective_ann,
            "hte_signal":   hte_signal,
            "hold_to_expiry": hold_to_expiry,
        })
    # Recount using effective signal after enrichment (respects hold_to_expiry toggle)
    def eff_sig(p):
        return p.get("hte_signal") if not hold_to_expiry and p.get("hte_signal") else p["signal"]

    arb  = sum(1 for p in enriched if eff_sig(p) == "execute")
    bord = sum(1 for p in enriched if eff_sig(p) == "borderline")
    loss = sum(1 for p in enriched if eff_sig(p) == "loss")
    best   = max((p.get("effective_pnl") or p["net_pnl"] for p in enriched), default=None)
    maxann = max((p.get("effective_ann") or p["ann_ret"] for p in enriched), default=None)

    # Also filter pairs list by effective signal
    if sig_filter != "all":
        pairs = [p for p in enriched if eff_sig(p) == sig_filter]
    else:
        pairs = enriched

        return render_template_string(PAGE,
        expiries=state["expiries"], active=active,
        d=d, chain=d.get("liquid_chain", d.get("chain", [])), pairs=enriched,
        arb=arb, bord=bord, loss=loss,
        total=len(all_pairs),
        best=best, maxann=maxann,
        params=PARAMS, inr=inr, pct=pct, num=num,
        last_fetch=state["last_fetch"],
        global_error=state["global_error"],
        authenticated=is_authenticated(),
        sig_filter=sig_filter,
        tax_rate=tax_rate,
        capital=capital,
        hold_to_expiry=hold_to_expiry,
        pre_stats=pre_stats,
        min_oi=int(os.environ.get("MIN_OI_FILTER","500")),
        max_width=int(os.environ.get("MAX_BOX_WIDTH","5000")),
        refresh_sec=REFRESH_SEC,
    )

@app.route("/depthtest")
def depthtest():
    token = load_token()
    if not token:
        return jsonify({"error": "No token"})
    try:
        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=token, log_path="")

        # Get real symbols from chain
        r = fyers.optionchain(data={"symbol": "NSE:NIFTY50-INDEX", "strikecount": "", "timestamp": ""})
        rows = r.get("data", {}).get("optionsChain", [])

        # Collect first 3 CE symbols and their raw fields
        ce_rows = [row for row in rows if row.get("option_type") == "CE" and row.get("ask",0) > 0][:3]
        sample_syms = [row.get("symbol") for row in ce_rows if row.get("symbol")]
        sample_fyTokens = [row.get("fyToken") for row in ce_rows if row.get("fyToken")]

        results = {"chain_sample_symbols": sample_syms, "chain_sample_fyTokens": sample_fyTokens}

        # Try depth with the exact symbol string from optionchain
        if sample_syms:
            d1 = fyers.depth(data={"symbol": [sample_syms[0]], "ohlcv_flag": 0})
            results["depth_with_symbol"] = {"s": d1.get("s"), "msg": d1.get("message",""), "data": str(d1)[:200]}

        # Try quotes API instead — may work where depth doesn't
        if sample_syms:
            q1 = fyers.quotes(data={"symbols": sample_syms[0]})
            results["quotes_with_symbol"] = {"s": q1.get("s"), "msg": q1.get("message",""), "data": str(q1)[:300]}

        # Try depth with comma-separated string instead of list
        if sample_syms:
            d2 = fyers.depth(data={"symbol": sample_syms[0], "ohlcv_flag": 0})
            results["depth_as_string"] = {"s": d2.get("s"), "msg": d2.get("message",""), "data": str(d2)[:200]}

        return jsonify(results)
    except Exception as e:
        import traceback
        return jsonify({"exception": str(e), "trace": traceback.format_exc()})


@app.route("/calc")
def calc():
    # Get inputs from query params or use defaults
    try:
        k1    = float(request.args.get("k1", 24000))
        k2    = float(request.args.get("k2", 25000))
        ca1   = float(request.args.get("ca1", 0))  # Call Ask K1
        cb2   = float(request.args.get("cb2", 0))  # Call Bid K2
        pa2   = float(request.args.get("pa2", 0))  # Put Ask K2
        pb1   = float(request.args.get("pb1", 0))  # Put Bid K1
        dte   = float(request.args.get("dte", 90))
    except Exception:
        k1,k2,ca1,cb2,pa2,pb1,dte = 24000,25000,0,0,0,0,90

    p = PARAMS
    lots     = p["lot_size"] * p["num_lots"]
    box_w    = k2 - k1
    box_val  = box_w * lots

    # Step by step
    net_debit_unit  = ca1 + pa2 - cb2 - pb1
    net_debit_total = net_debit_unit * lots

    sell_prem  = (cb2 + pb1) * lots
    entry_stt  = (p["stt_entry_pct"] / 100) * sell_prem

    settl_stt  = (p["stt_settl_pct"] / 100) * box_val

    total_prem = (ca1 + pa2 + cb2 + pb1) * lots
    txn_charge = (p["txn_pct"]  / 100) * total_prem
    sebi_chg   = (p["sebi_pct"] / 100) * total_prem
    brokerage  = 4 * p["broker_per_leg"]
    gst        = (p["gst_pct"] / 100) * brokerage
    buy_prem   = (ca1 + pa2) * lots
    stamp      = (p["stamp_pct"] / 100) * buy_prem
    slip       = 4 * p["slip_per_leg"] * lots

    other_costs = txn_charge + sebi_chg + brokerage + gst + stamp + slip
    total_cost  = net_debit_total + entry_stt + settl_stt + other_costs
    net_pnl     = box_val - total_cost
    ret_pct     = (net_pnl / net_debit_total * 100) if net_debit_total else 0
    ann_ret     = (ret_pct * 365 / dte) if dte else 0

    has_input = any([ca1, cb2, pa2, pb1])

    return render_template_string(CALC_PAGE,
        k1=k1, k2=k2, ca1=ca1, cb2=cb2, pa2=pa2, pb1=pb1, dte=dte,
        lots=lots, box_w=box_w, box_val=box_val,
        net_debit_unit=net_debit_unit, net_debit_total=net_debit_total,
        sell_prem=sell_prem, entry_stt=entry_stt,
        settl_stt=settl_stt,
        total_prem=total_prem, txn_charge=txn_charge, sebi_chg=sebi_chg,
        brokerage=brokerage, gst=gst, stamp=stamp, slip=slip,
        other_costs=other_costs, total_cost=total_cost,
        net_pnl=net_pnl, ret_pct=ret_pct, ann_ret=ann_ret,
        params=p, has_input=has_input, inr=inr, pct=pct,
    )


@app.route("/history")
def history():
    rows = get_history(limit=500)
    return render_template_string(HISTORY_PAGE, rows=rows, inr=inr, pct=pct)


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
.main{padding:16px 20px;max-width:1600px;margin:0 auto}
.err{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:10px 14px;color:#b91c1c;font-size:12px;margin-bottom:12px}
.ebar{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.elabel{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.eb{padding:4px 12px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;text-decoration:none;font-size:12px;color:#475569;font-weight:500}
.eb:hover{border-color:#94a3b8}.eb.on{background:#0f172a;color:#fff;border-color:#0f172a}
.arbn{display:inline-block;margin-left:4px;background:#dcfce7;color:#15803d;border-radius:3px;padding:1px 4px;font-size:10px;font-weight:700}
.eb.on .arbn{background:#22c55e;color:#fff}
.cards{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:14px}
@media(max-width:900px){.cards{grid-template-columns:repeat(3,1fr)}}
.card{background:#fff;border-radius:9px;padding:12px 14px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.cl{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px}
.cv{font-size:20px;font-weight:700;font-family:'Courier New',monospace}
.g{color:#16a34a}.a{color:#d97706}.r{color:#dc2626}.b{color:#2563eb}
.sec{background:#fff;border-radius:9px;box-shadow:0 1px 2px rgba(0,0,0,.06);margin-bottom:14px;overflow:hidden}
.sh{padding:10px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;cursor:pointer;user-select:none}
.sh-static{cursor:default}
.sb{padding:16px}
.toggle-hint{font-size:11px;color:#94a3b8;font-weight:400}
/* Strategy summary */
.strategy-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.strategy-grid{grid-template-columns:1fr}}
.signal-card{border-radius:8px;padding:14px;border-left:4px solid}
.signal-card.exec{background:#f0fdf4;border-color:#16a34a}
.signal-card.border{background:#fefce8;border-color:#d97706}
.signal-card.avoid{background:#fef2f2;border-color:#dc2626}
.signal-card.impact{background:#eff6ff;border-color:#3b82f6}
.sc-title{font-weight:700;font-size:13px;margin-bottom:6px}
.sc-rule{font-size:12px;color:#374151;line-height:1.7;font-family:'Courier New',monospace;background:rgba(0,0,0,.04);padding:6px 8px;border-radius:4px;margin-bottom:6px}
.sc-note{font-size:11px;color:#64748b;line-height:1.5}
.formula-chain{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin-top:12px}
.fc-title{font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.fc-steps{display:flex;flex-direction:column;gap:6px}
.fc-step{display:flex;align-items:baseline;gap:8px}
.fc-num{width:20px;height:20px;border-radius:50%;background:#0f172a;color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fc-formula{font-family:'Courier New',monospace;font-size:11px;color:#374151}
.fc-arrow{color:#94a3b8;font-size:11px;margin:0 4px}
/* Assumptions */
.agrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
@media(max-width:900px){.agrid{grid-template-columns:repeat(2,1fr)}}
.acard{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px}
.acard.highlight{border-color:#3b82f6;background:#eff6ff}
.acard-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px}
.aname{font-size:12px;font-weight:700;color:#0f172a}
.aval{font-size:14px;font-weight:700;font-family:'Courier New',monospace;color:#2563eb;white-space:nowrap;margin-left:8px}
.atag{display:inline-block;font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;margin-bottom:4px}
.atag-what{background:#e0e7ff;color:#3730a3}
.atag-why{background:#fef3c7;color:#92400e}
.atag-how{background:#dcfce7;color:#166534}
.atext{font-size:11px;color:#374151;line-height:1.5;margin-bottom:3px}
/* Controls */
.ctrl-bar{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;padding:12px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0}
.ctrl-group{display:flex;flex-direction:column;gap:4px}
.ctrl-label{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.ctrl-input{padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;font-family:'Courier New',monospace;background:#fff;width:160px}
.ctrl-btn{padding:7px 18px;background:#0f172a;color:#fff;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;align-self:flex-end}
/* Calc breakdown */
.calc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}
@media(max-width:900px){.calc-grid{grid-template-columns:repeat(2,1fr)}}
.calc-item{background:#f8fafc;border-radius:6px;padding:8px 10px;border-left:3px solid #e2e8f0}
.calc-item.debit{border-color:#3b82f6}
.calc-item.cost{border-color:#f59e0b}
.calc-item.pnl{border-color:#16a34a}
.calc-item.risk{border-color:#ef4444}
.ci-label{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px}
.ci-val{font-size:14px;font-weight:700;font-family:'Courier New',monospace}
.ci-formula{font-size:10px;color:#94a3b8;margin-top:2px;font-family:'Courier New',monospace}
/* Table */
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:11.5px}
th{background:#f1f5f9;padding:7px 10px;text-align:right;font-size:10px;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0;white-space:nowrap;text-transform:uppercase;letter-spacing:.3px}
th.l{text-align:left}
th.group-a{background:#eff6ff;color:#1d4ed8}
th.group-b{background:#fefce8;color:#854d0e}
th.group-c{background:#f0fdf4;color:#166534}
th.group-d{background:#fef2f2;color:#991b1b}
th.group-e{background:#f5f3ff;color:#5b21b6}
td{padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Courier New',monospace;white-space:nowrap}
td.l{text-align:left;font-family:inherit;font-weight:600}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;font-family:inherit}
.pg{background:#dcfce7;color:#15803d}.pa{background:#fef3c7;color:#92400e}
.pr{background:#fee2e2;color:#b91c1c}.ps{background:#f1f5f9;color:#64748b}
.pb{background:#dbeafe;color:#1e40af}
.empty{text-align:center;padding:40px;color:#94a3b8;font-size:13px}
.na{color:#cbd5e1}
</style>
<script>
function toggle(id){var el=document.getElementById(id);el.style.display=el.style.display==='none'?'':'none';}
</script>
</head>
<body>
<div class="topbar">
  <div>
    <div class="t1">NIFTY Box Spread Arbitrage Scanner</div>
    <div class="t2">
      {% if active %}{{ active }} &nbsp;·&nbsp; DTE: {{ d.get('dte','?') }} &nbsp;·&nbsp; CMP: ₹{{ "{:,.0f}".format(d.get('cmp',0) or 0) }} &nbsp;·&nbsp; Lot: {{ params.lot_size }} &nbsp;·&nbsp; Capital: ₹{{ "{:,.0f}".format(capital) }} &nbsp;·&nbsp; Tax: {{ tax_rate|int }}% &nbsp;·&nbsp; {% if hold_to_expiry %}Hold to expiry{% else %}Early exit mode{% endif %}{% endif %}
    </div>
  </div>
  <div class="live"><div class="dot"></div>
    {% if not authenticated %}Not authenticated — <a href="/admin" style="color:#60a5fa">login</a>
    {% elif global_error %}<span style="color:#f87171">{{ global_error }}</span>
    {% else %}Live · Updated {{ last_fetch or '...' }} · Auto-refreshes every {{ refresh_sec }}s{% endif %}
  </div>
</div>
<div class="main">
{% if global_error %}<div class="err">{{ global_error }}</div>{% endif %}

<!-- EXPIRY TABS -->
<div class="ebar">
  <span class="elabel">Expiry</span>
  {% if expiries %}{% for e in expiries %}
    {% set en = state_data.get(e, {}).get('arb_count', 0) %}
    <a href="/?expiry={{ e }}&sig={{ sig_filter }}&tax={{ tax_rate }}&capital={{ capital|int }}" class="eb{% if e==active %} on{% endif %}">
      {{ e }}{% if en > 0 %}<span class="arbn">{{ en }}</span>{% endif %}
    </a>
  {% endfor %}{% else %}
    <span style="font-size:12px;color:#94a3b8">{% if authenticated %}Loading...{% else %}Login at <a href="/admin">/admin</a>{% endif %}</span>
  {% endif %}
</div>

<!-- SCORECARD -->
<div class="cards">
  <div class="card"><div class="cl">Strikes Used</div>
    <div class="cv b">{{ pre_stats.get('liquid_strikes','—') }}</div>
    <div style="font-size:10px;color:#94a3b8;margin-top:2px">top {{ top_strikes }} by OI · of {{ pre_stats.get('total_strikes','—') }} total</div>
  </div>
  <div class="card"><div class="cl">Pairs Computed</div>
    <div class="cv b">{{ total }}</div>
    <div style="font-size:10px;color:#94a3b8;margin-top:2px">width ≤ {{ "{:,}".format(max_width) }} pts</div>
  </div>
  <div class="card"><div class="cl">Depth Evaluated</div>
    <div class="cv b">{{ pre_stats.get('candidates_with_depth','—') }}</div>
    <div style="font-size:10px;color:#94a3b8;margin-top:2px">all arb/borderline pairs</div>
  </div>
  <div class="card"><div class="cl">✅ Execute</div><div class="cv g">{{ arb }}</div></div>
  <div class="card"><div class="cl">Best P&L/lot</div><div class="cv g" style="font-size:14px">{{ inr(best) }}</div></div>
  <div class="card"><div class="cl">Max Ann. Return</div><div class="cv g" style="font-size:14px">{{ pct(maxann) }}</div></div>
</div>

<!-- STRATEGY SUMMARY -->
<div class="sec">
  <div class="sh sh-static" onclick="toggle('summary-body')">
    <span>How this scanner works — Signal logic, cost model &amp; impact cost explained</span>
    <span class="toggle-hint">click to expand/collapse</span>
  </div>
  <div id="summary-body" style="display:none">
  <div class="sb">
    <div class="strategy-grid">
      <div>
        <p style="font-size:13px;line-height:1.7;color:#374151;margin-bottom:12px">
          A <strong>Long Box Spread</strong> is a 4-leg options strategy: Buy Call(K1) + Sell Call(K2) + Buy Put(K2) + Sell Put(K1).
          At expiry, it always settles at exactly <strong>K2 − K1</strong> regardless of where NIFTY is. It is fully direction-neutral.
          Arbitrage exists when you can buy the box cheaper than it will settle for.
        </p>
        <div class="formula-chain">
          <div class="fc-title">Profit Condition</div>
          <div class="fc-steps">
            <div class="fc-step"><span class="fc-num">1</span><span class="fc-formula">Box Value = (K2 − K1) × Lot Size &nbsp;→ always received at expiry</span></div>
            <div class="fc-step"><span class="fc-num">2</span><span class="fc-formula">Net Debit = Call Ask(K1) + Put Ask(K2) − Call Bid(K2) − Put Bid(K1)</span></div>
            <div class="fc-step"><span class="fc-num">3</span><span class="fc-formula">Gross Profit = Box Value − Net Debit &nbsp;(before costs)</span></div>
            <div class="fc-step"><span class="fc-num">4</span><span class="fc-formula">All Costs = Entry STT + Settlement STT + Brokerage + GST + NSE Txn + SEBI + Stamp + Slippage + Impact Cost</span></div>
            <div class="fc-step"><span class="fc-num">5</span><span class="fc-formula">Net P&L = Box Value − Net Debit − All Costs</span></div>
            <div class="fc-step"><span class="fc-num">6</span><span class="fc-formula">Ann. Return = (Net P&L / Net Debit) × (365 / DTE) × 100</span></div>
          </div>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <div class="signal-card exec">
          <div class="sc-title">✅ EXECUTE</div>
          <div class="sc-rule">Profit after all costs &gt; 0 · Yearly return ≥ {{ params.min_ann_ret }}% · Buy/sell price gap &lt; {{ params.max_spread_pct }}% of spread width</div>
          <div class="sc-note">All 3 conditions must be met. Annualized return must beat the minimum threshold (set above the {{ params.rfr }}% risk-free rate). Bid-ask spread must be tight enough that execution is feasible at quoted prices.</div>
        </div>
        <div class="signal-card border">
          <div class="sc-title">⚠ BORDERLINE</div>
          <div class="sc-rule">Profit &gt; 0 BUT yearly return &lt; {{ params.min_ann_ret }}% OR buy/sell gap too wide to execute reliably</div>
          <div class="sc-note">Makes a profit after all costs, but either the yearly return is below {{ params.min_ann_ret }}% (not worth it vs a fixed deposit), or the gap between buy and sell prices is too wide to reliably execute at the quoted price. Worth monitoring — a small price shift can push it to Execute.</div>
        </div>
        <div class="signal-card avoid">
          <div class="sc-title">❌ AVOID</div>
          <div class="sc-rule">Net P&L ≤ 0 after ALL costs including settlement STT</div>
          <div class="sc-note">{% if hold_to_expiry %}The most common reason is Settlement STT (0.125% of box value) which is always charged when holding to expiry. Deep ITM boxes with high Entry STT on sell legs are also frequent losers.{% else %}In early exit mode, Settlement STT is avoided — but you pay the bid-ask spread cost to unwind all 4 legs. Pairs that were previously loss-making may now show a profit.{% endif %}</div>
        </div>
        <div class="signal-card impact">
          <div class="sc-title">📊 Two-Stage Filter</div>
          <div class="sc-rule">Stage 1: OI ≥ {{ min_oi }} contracts · Width ≤ {{ "{:,}".format(max_width) }} pts · Active quotes on all 4 legs</div>
          <div class="sc-rule">Stage 2: Full order-book depth fetched for ALL remaining pairs → impact cost → adj P&L → signal rescore</div>
          <div class="sc-note">Stage 1 removes illiquid and impractically wide pairs before any calculation. Stage 2 then evaluates real execution feasibility for every survivor — not just the top 20. Final sort is by impact-adjusted return, not theoretical return.</div>
        </div>
      </div>
    </div>
  </div>
  </div>
</div>

<!-- CONTROLS -->
<div class="sec">
  <div class="sh sh-static">Analysis Controls</div>
  <form method="GET" action="/">
    <input type="hidden" name="expiry" value="{{ active or '' }}">
    <div class="ctrl-bar">
      <div class="ctrl-group">
        <label class="ctrl-label">Income Tax Bracket</label>
        <select name="tax" class="ctrl-input" style="width:200px">
          {% for t,lbl in [(0,'No tax (exempt)'),(5,'Up to ₹3L income'),(10,'Up to ₹6L income'),(15,'Up to ₹9L income'),(20,'Up to ₹12L income'),(25,'Up to ₹15L income'),(30,'Above ₹15L income')] %}
          <option value="{{ t }}" {% if tax_rate==t %}selected{% endif %}>{{ t }}% — {{ lbl }}</option>
          {% endfor %}
        </select>
        <span style="font-size:10px;color:#94a3b8">Box spread gains = STCG, taxed at slab</span>
      </div>
      <div class="ctrl-group">
        <label class="ctrl-label">Deployable Capital (₹)</label>
        <input type="number" name="capital" class="ctrl-input" value="{{ capital|int }}" step="50000" style="width:180px">
        <span style="font-size:10px;color:#94a3b8">Used for lot sizing &amp; OI liquidity check</span>
      </div>
      <div class="ctrl-group">
        <label class="ctrl-label">Signal Filter</label>
        <select name="sig" class="ctrl-input" style="width:200px">
          <option value="all" {% if sig_filter=='all' %}selected{% endif %}>All pairs ({{ total }})</option>
          <option value="execute" {% if sig_filter=='execute' %}selected{% endif %}>✅ Execute only ({{ arb }})</option>
          <option value="borderline" {% if sig_filter=='borderline' %}selected{% endif %}>⚠ Borderline ({{ bord }})</option>
          <option value="loss" {% if sig_filter=='loss' %}selected{% endif %}>❌ Loss — avoid ({{ loss }})</option>
        </select>
      </div>
      <div class="ctrl-group">
        <label class="ctrl-label">Hold to Expiry?</label>
        <select name="hold" class="ctrl-input" style="width:220px">
          <option value="1" {% if hold_to_expiry %}selected{% endif %}>Yes — hold till expiry date</option>
          <option value="0" {% if not hold_to_expiry %}selected{% endif %}>No — close before expiry</option>
        </select>
        <span style="font-size:10px;color:#94a3b8;margin-top:2px">
          {% if hold_to_expiry %}Settlement STT (0.125%) applies at expiry{% else %}Settlement STT avoided — exit cost estimated from spread width{% endif %}
        </span>
      </div>
      <button type="submit" class="ctrl-btn">Apply →</button>
      <div style="margin-left:auto;font-size:11px;color:#94a3b8;align-self:flex-end;text-align:right">
        <a href="/calc" style="color:#3b82f6">Step-by-step calculator →</a>
      </div>
    </div>
  </form>
</div>

<!-- EXECUTE SUMMARY -->
{% if arb > 0 and active %}
<div class="sec" style="border-left:4px solid #16a34a">
  <div class="sh sh-static" style="background:#f0fdf4">
    <span style="color:#15803d">✅ {{ arb }} Executable Spread{{ 's' if arb > 1 else '' }} Found — {{ active }}</span>
    <span style="font-size:11px;color:#15803d;font-weight:400">Profitable after all costs, yearly return ≥ {{ params.min_ann_ret }}%, and buy/sell price gap is tight enough to execute</span>
  </div>
  <div class="sb" style="background:#f0fdf4">
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px">
    {% for p in pairs if (p.get('hte_signal') if not hold_to_expiry and p.get('hte_signal') else p.signal) == 'execute' %}
    <div style="background:#fff;border:1px solid #bbf7d0;border-radius:8px;padding:12px 14px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
        <div>
          <span style="font-size:14px;font-weight:700;color:#0f172a">K1={{ "{:,}".format(p.k1|int) }} / K2={{ "{:,}".format(p.k2|int) }}</span>
          <span style="font-size:11px;color:#64748b;margin-left:8px">Width: {{ p.box_w|int }}</span>
        </div>
        <span style="font-size:13px;font-weight:700;color:#16a34a">{{ pct(p.ann_ret) }} p.a.</span>
      </div>
      <div style="font-size:11px;color:#374151;line-height:1.8;font-family:'Courier New',monospace;background:#f8fafc;padding:8px 10px;border-radius:6px;margin-bottom:8px">
        Buy  Call {{ "{:,}".format(p.k1|int) }} @ ₹{{ "%.2f"|format(p.ca1) }}&nbsp;&nbsp;Sell Call {{ "{:,}".format(p.k2|int) }} @ ₹{{ "%.2f"|format(p.cb2) }}<br>
        Buy  Put  {{ "{:,}".format(p.k2|int) }} @ ₹{{ "%.2f"|format(p.pa2) }}&nbsp;&nbsp;Sell Put  {{ "{:,}".format(p.k1|int) }} @ ₹{{ "%.2f"|format(p.pb1) }}
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;font-size:11px">
        <div style="text-align:center;background:#f0fdf4;border-radius:4px;padding:4px">
          <div style="color:#64748b">Net P&L/lot</div>
          <div style="font-weight:700;color:#16a34a;font-family:monospace">{{ inr(p.net_pnl) }}</div>
        </div>
        <div style="text-align:center;background:#eff6ff;border-radius:4px;padding:4px">
          <div style="color:#64748b">Post-tax</div>
          <div style="font-weight:700;color:#2563eb;font-family:monospace">{{ pct(p.post_tax_ann) }}</div>
        </div>
        <div style="text-align:center;background:#fefce8;border-radius:4px;padding:4px">
          <div style="color:#64748b">Max lots</div>
          <div style="font-weight:700;color:#854d0e;font-family:monospace">{{ p.lots_possible }}</div>
        </div>
      </div>
      {% if p.lots_possible > 0 %}
      <div style="margin-top:8px;font-size:11px;color:#374151;line-height:1.6">
        <strong>Signal basis:</strong> {% if p.get('signal_basis')=='adj' %}✅ Confirmed using <em>impact-adjusted</em> P&L{% else %}Based on raw P&L (impact cost not yet computed){% endif %}<br>
        <strong>Execution:</strong> {{ p.get('exec_difficulty','—') }}
        {% if p.get('exec_reason') %} — <span style="color:#64748b;font-size:11px">{{ p.get('exec_reason') }}</span>{% endif %}<br>
        <strong>Why executable:</strong>
        Box settles at ₹{{ "{:,}".format(p.box_value|int) }}. You pay ₹{{ "{:,}".format(p.net_debit|int) }} net debit.
        After all costs (Entry STT {{ inr(p.entry_stt) }} + Settl STT {{ inr(p.settl_stt) }} + other {{ inr(p.other_costs) }}),
        net profit is {{ inr(p.net_pnl) }}/lot = {{ pct(p.ann_ret) }} per year (over {{ d.get('dte','?') }} days to expiry).
        {% if p.ann_ret >= params.rfr %}Beats the {{ params.rfr }}% risk-free rate by {{ "%.2f"|format(p.ann_ret - params.rfr) }}%.{% endif %}
        {% if p.spread_pct is not none %}The gap between buy and sell prices ({{ "%.2f"|format(p.spread_pct) }}%) is tight enough to execute reliably.{% endif %}
      </div>
      <div style="margin-top:6px;font-size:11px">
        <strong>Liquidity:</strong> {{ p.get('oi_flag','—') }}
        {% if p.get('oi_note') %} — {{ p.get('oi_note') }}{% endif %}
        {% if p.get('ic_flag') %}&nbsp;·&nbsp; Impact: {{ p.get('ic_flag') }}{% endif %}
        {% if p.get('adj_net_pnl') is not none %}&nbsp;·&nbsp; Adj. P&L after impact: <strong style="color:{% if p.adj_net_pnl >= 0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(p.adj_net_pnl) }}</strong>{% endif %}
      </div>
      {% if p.adj_total_pnl is not none %}
      <div style="margin-top:6px;background:#dcfce7;border-radius:4px;padding:5px 8px;font-size:12px;font-weight:600;color:#15803d">
        Deploy ₹{{ "{:,.0f}".format(capital) }} → {{ p.lots_possible }} lots → Total P&L: {{ inr(p.adj_total_pnl) }}
      </div>
      {% endif %}
      {% endif %}
    </div>
    {% endfor %}
    </div>
    {% if bord > 0 %}
    <div style="margin-top:12px;padding:10px 12px;background:#fefce8;border:1px solid #fde68a;border-radius:6px;font-size:12px;color:#854d0e">
      <strong>⚠ {{ bord }} borderline pairs</strong> make a profit but either return less than {{ params.min_ann_ret }}% per year (barely better than a fixed deposit) or have wide buy/sell price gaps that make execution uncertain.
      Switch to the <a href="/?expiry={{ active }}&sig=borderline&tax={{ tax_rate }}&capital={{ capital|int }}" style="color:#854d0e;font-weight:700">Borderline filter</a> to review them — some may be worth executing if you're comfortable with a lower yearly return than {{ params.min_ann_ret }}%.
    </div>
    {% endif %}
  </div>
</div>
{% elif active and total > 0 %}
<div class="sec" style="border-left:4px solid #e2e8f0">
  <div class="sh sh-static">
    <span style="color:#64748b">No executable spreads for {{ active }}</span>
  </div>
  <div class="sb">
    <div style="font-size:12px;color:#374151;line-height:1.8">
      <strong>{{ bord }} pairs are profitable</strong> but return less than {{ params.min_ann_ret }}% per year after all costs. 
      <strong>{{ loss }} pairs</strong> show net losses — most due to Settlement STT (0.125% × box value) wiping the edge.<br>
      <strong>Try:</strong> switching to a longer-dated expiry (more time = more premium inefficiency to exploit), 
      or reducing the <strong>Min Ann. Return</strong> in Analysis Controls above — that setting filters out pairs below a minimum yearly return. Lowering it from {{ params.min_ann_ret }}% will show more results.
    </div>
  </div>
</div>
{% endif %}

<!-- COST MODEL BREAKDOWN for this expiry -->
{% if d.get('dte') %}
<div class="sec">
  <div class="sh" onclick="toggle('calcbody')">
    <span>Cost Model Breakdown — how each cost is calculated for {{ active }}</span>
    <span class="toggle-hint">click to expand/collapse</span>
  </div>
  <div id="calcbody" style="display:none"><div class="sb">
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">These are the costs applied to every pair in the table below. Variable costs (STT, txn, SEBI, stamp) scale with premium; fixed costs (brokerage, GST) are the same for every pair.</p>
    <div class="calc-grid">
      <div class="calc-item debit">
        <div class="ci-label">Net Debit (capital deployed)</div>
        <div class="ci-val" style="color:#2563eb">Variable per pair</div>
        <div class="ci-formula">= C_Ask(K1) + P_Ask(K2) − C_Bid(K2) − P_Bid(K1)</div>
        <div class="ci-formula" style="margin-top:3px">× {{ params.lot_size }} units (lot size)</div>
      </div>
      <div class="calc-item debit">
        <div class="ci-label">Box Value (settlement)</div>
        <div class="ci-val" style="color:#2563eb">Variable per pair</div>
        <div class="ci-formula">= (K2 − K1) × {{ params.lot_size }} units</div>
        <div class="ci-formula" style="margin-top:3px">Always received at expiry</div>
      </div>
      <div class="calc-item cost">
        <div class="ci-label">Entry STT (sell legs)</div>
        <div class="ci-val" style="color:#d97706">{{ params.stt_entry_pct }}% of sell premium</div>
        <div class="ci-formula">= {{ params.stt_entry_pct }}% × (C_Bid(K2) + P_Bid(K1)) × {{ params.lot_size }}</div>
        <div class="ci-formula" style="margin-top:3px">Charged by NSE at entry on sell side</div>
      </div>
      <div class="calc-item cost">
        <div class="ci-label">Settlement STT ⚠</div>
        <div class="ci-val" style="color:#d97706">{{ params.stt_settl_pct }}% of box value</div>
        <div class="ci-formula">= {{ params.stt_settl_pct }}% × (K2−K1) × {{ params.lot_size }}</div>
        <div class="ci-formula" style="margin-top:3px">Always charged at expiry — unavoidable</div>
      </div>
      <div class="calc-item cost">
        <div class="ci-label">Brokerage + GST</div>
        <div class="ci-val" style="color:#d97706">₹{{ "%.2f"|format(4 * params.broker_per_leg * (1 + params.gst_pct/100)) }}</div>
        <div class="ci-formula">= 4 legs × ₹{{ params.broker_per_leg }} × (1 + {{ params.gst_pct }}%)</div>
        <div class="ci-formula" style="margin-top:3px">Fixed floor — same for every pair</div>
      </div>
      <div class="calc-item cost">
        <div class="ci-label">NSE Txn + SEBI</div>
        <div class="ci-val" style="color:#d97706">{{ params.txn_pct }}% + {{ params.sebi_pct }}%</div>
        <div class="ci-formula">= ({{ params.txn_pct }}% + {{ params.sebi_pct }}%) × total 4-leg premium</div>
        <div class="ci-formula" style="margin-top:3px">Scales with premium value of all 4 legs</div>
      </div>
      <div class="calc-item cost">
        <div class="ci-label">Stamp Duty + Slippage</div>
        <div class="ci-val" style="color:#d97706">Variable</div>
        <div class="ci-formula">Stamp: {{ params.stamp_pct }}% × buy-side premium</div>
        <div class="ci-formula" style="margin-top:3px">Slip: 4 × {{ params.slip_per_leg }}pts × {{ params.lot_size }} = ₹{{ 4 * params.slip_per_leg * params.lot_size }}</div>
      </div>
      <div class="calc-item risk">
        <div class="ci-label">Impact Cost (top 20 pairs)</div>
        <div class="ci-val" style="color:#dc2626">Order-book based</div>
        <div class="ci-formula">Walks 5-level depth for all 4 legs</div>
        <div class="ci-formula" style="margin-top:3px">Mid vs avg fill price × your lot size</div>
      </div>
    </div>
    <div style="background:#fef3c7;border:1px solid #fde68a;border-radius:6px;padding:10px 12px;font-size:11px;color:#78350f;margin-top:4px">
      <strong>Why Settlement STT is the key cost:</strong> On a K2−K1=1000 wide box with lot size {{ params.lot_size }}:
      Settlement STT = {{ params.stt_settl_pct }}% × ₹{{ 1000 * params.lot_size | int }} = ₹{{ (params.stt_settl_pct/100 * 1000 * params.lot_size) | round(2) }} per lot.
      This alone means the box must trade at a discount of more than ₹{{ (params.stt_settl_pct/100 * 1000 * params.lot_size) | round(0) | int }} to be profitable — which is why most pairs show losses.
    </div>
  </div></div>
</div>
{% endif %}

<!-- ASSUMPTIONS -->
<div class="sec">
  <div class="sh" onclick="toggle('assump-body')">
    <span>Assumptions — what each input is, why it matters, and how it's used</span>
    <span class="toggle-hint">click to expand/collapse</span>
  </div>
  <div id="assump-body" style="display:none"><div class="sb">
    <div class="agrid">
      {% set assumptions = [
        ("Lot Size (NIFTY)", params.lot_size|string ~ " units", False,
         "Number of NIFTY units in one options lot. NSE-mandated — currently 65 for monthly expiry contracts.",
         "Every P&L calculation multiplies by lot size. A ₹10/unit edge × 65 = ₹650/lot.",
         "Used in: Net Debit, Box Value, Entry STT, Settlement STT, Stamp Duty, Slippage — literally every formula."),
        ("Number of Lots", params.num_lots|string, False,
         "How many lots you trade per box spread. Set to 1 here; increase to scale position size.",
         "All costs and P&L multiply linearly. 2 lots = 2× capital, 2× P&L, 2× exposure.",
         "Scales Net Debit, Box Value, and all variable costs. Also drives the OI liquidity check."),
        ("Brokerage per Leg", "₹" ~ params.broker_per_leg|string, False,
         "Flat fee charged per order leg by your broker (Fyers). A box spread has exactly 4 legs.",
         "₹80 total brokerage is the fixed floor cost that must be recovered before any profit.",
         "Used in: Fixed Cost = 4 × ₹20 = ₹80, then GST applied on top → ₹94.40 minimum cost."),
        ("GST on Brokerage", params.gst_pct|string ~ "%", False,
         "18% GST charged by the government on brokerage fees only — not on premiums or STT.",
         "Adds ₹14.40 to the ₹80 brokerage. Combined ₹94.40 is the fixed cost floor for every box.",
         "Used in: Other Costs = brokerage × (1 + 18%). Applied before P&L is computed."),
        ("Entry STT (sell legs)", params.stt_entry_pct|string ~ "%", False,
         "Securities Transaction Tax charged at 0.05% on the premium of sell legs at entry: Sell Call(K2) + Sell Put(K1).",
         "Deep ITM sell legs carry high premiums → high STT. Often the #1 cost killer for wide boxes.",
         "Used in: Entry STT = 0.05% × (Call_Bid(K2) + Put_Bid(K1)) × Lot Size. Deducted from gross profit."),
        ("Settlement STT", params.stt_settl_pct|string ~ "%", False,
         "0.125% STT charged on the intrinsic value at expiry settlement. Always charged when holding to expiry — no way to avoid it.",
         "On a ₹1,000 wide box: ₹81.25 per lot in settlement STT alone. This is why most boxes show losses.",
         "Used in: Settlement STT = 0.125% × (K2−K1) × Lot Size. This is the critical cost unique to box spreads."),
        ("NSE Txn Charge", params.txn_pct|string ~ "%", False,
         "NSE exchange fee: ₹3,503 per crore of total premium turnover (0.03503%). Applied on all 4 legs combined.",
         "Scales with total premium. Deep ITM boxes have high total premium → higher NSE charges.",
         "Used in: NSE Txn = 0.03503% × (C_Ask(K1) + C_Bid(K2) + P_Ask(K2) + P_Bid(K1)) × Lot Size."),
        ("SEBI Charge", params.sebi_pct|string ~ "%", False,
         "SEBI regulatory fee: ₹10 per crore of premium turnover (0.0001%). Mandatory but negligible.",
         "Very small in absolute terms but included for completeness — every paisa matters in arbitrage.",
         "Used in: SEBI = 0.0001% × total 4-leg premium × Lot Size. Same base as NSE Txn."),
        ("Stamp Duty", params.stamp_pct|string ~ "%", False,
         "State government stamp duty charged only on buy-side premiums: Buy Call(K1) Ask + Buy Put(K2) Ask.",
         "Only on buy legs. Buying deep ITM calls (high premium) increases this cost.",
         "Used in: Stamp = 0.003% × (C_Ask(K1) + P_Ask(K2)) × Lot Size."),
        ("Slippage per Leg", params.slip_per_leg|string ~ " pts", False,
         "Conservative flat slippage assumption: 0.5 index points per leg. Accounts for not always getting the quoted mid price.",
         "4 legs × 0.5 pts × 65 = ₹130 slippage per box. For illiquid strikes this may be a large underestimate.",
         "Used in: Slippage = 4 × 0.5 × Lot Size = ₹130. Deducted from Net P&L in Other Costs."),
        ("Risk-Free Rate", params.rfr|string ~ "%", False,
         "Current 91-day T-bill / RBI repo rate. The benchmark you compare box spread returns against.",
         "A box returning 6.4% when FDs give 6.5% is NOT an arbitrage — you'd do better in a bank.",
         "Used in: Ann. Return vs RFR comparison. Green if Ann% > RFR, amber if lower. Sets the hurdle."),
        ("Min Ann. Return", params.min_ann_ret|string ~ "%", False,
         "Minimum annualized return for EXECUTE signal. Set above the RFR to ensure true outperformance.",
         "Filters borderline pairs that technically profit but don't beat a simple fixed deposit.",
         "Used in: Signal = EXECUTE if Ann% ≥ Min Ann% AND spread < Max Spread%. Otherwise BORDERLINE."),
        ("Top Strikes by OI", top_strikes|string ~ " strikes", False,
         "Only the top N strikes ranked by combined Open Interest (call OI + put OI) are used for pair analysis.",
         "Concentrates analysis on the most liquid, actively traded strikes. Adapts automatically — works for near-expiry (low OI) and far-expiry (high OI) contracts alike.",
         "Used in Stage 1 pre-filter: all strikes ranked by (Call OI + Put OI), top " ~ top_strikes|string ~ " selected. Active quote check (non-zero bid AND ask) applied first."),
        ("Max Box Width", "{:,}".format(max_width) ~ " pts", False,
         "Maximum allowed distance between K1 and K2 strikes. Pairs wider than this are not computed.",
         "Very wide boxes have enormous settlement STT and net debit — almost never profitable. Limiting width keeps the list focused.",
         "Used in Stage 1 pre-filter: only pairs where K2 − K1 ≤ " ~ "{:,}".format(max_width) ~ " are computed."),
        ("Max Bid-Ask Spread %", params.max_spread_pct|string ~ "%", False,
         "Maximum allowable bid-ask spread (total across 4 legs, as % of box width). Measures execution feasibility.",
         "Wide spreads mean the theoretical arb may vanish when you try to execute at real market prices.",
         "Used in: Signal = EXECUTE only if Spread% < 1%. Spread% = sum of 4 leg spreads ÷ box width."),
        ("Fixed Cost Floor", "₹" ~ (4 * params.broker_per_leg * (1 + params.gst_pct/100))|round(2)|string, True,
         "The minimum unavoidable fixed cost per box: 4 × ₹20 brokerage + 18% GST = ₹94.40.",
         "Any pair where (Box Value − Net Debit) < ₹94.40 is a guaranteed loss before STT or any other cost.",
         "Used in: Breakeven check. Gross profit must exceed ₹94.40 just to cover fixed costs alone."),
      ] %}
      {% for name, val, hl, what, why, how in assumptions %}
      <div class="acard{% if hl %} highlight{% endif %}">
        <div class="acard-top"><span class="aname">{{ name }}</span><span class="aval">{{ val }}</span></div>
        <div style="margin-bottom:5px">
          <span class="atag atag-what">WHAT</span>
          <span class="atext">{{ what }}</span>
        </div>
        <div style="margin-bottom:5px">
          <span class="atag atag-why">WHY</span>
          <span class="atext">{{ why }}</span>
        </div>
        <div>
          <span class="atag atag-how">HOW USED</span>
          <span class="atext">{{ how }}</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div></div>
</div>

<!-- OPTION CHAIN -->
{% if chain %}
<div class="sec">
  <div class="sh" onclick="toggle('chain-body')">
    <span>Option Chain — {{ active }} · Top {{ chain|length }} strikes by OI &nbsp;·&nbsp; Buy at Ask · Sell at Bid</span>
    <span class="toggle-hint">click to expand/collapse</span>
  </div>
  <div id="chain-body"><div class="tw">
    <table>
      <thead><tr>
        <th class="l">Strike (K)</th>
        <th class="group-a">Call Bid</th><th class="group-a">Call Ask</th><th class="group-a">Call Mid</th><th class="group-a">Call IV%</th><th class="group-a">Call OI</th>
        <th class="group-b">Put Bid</th><th class="group-b">Put Ask</th><th class="group-b">Put Mid</th><th class="group-b">Put IV%</th><th class="group-b">Put OI</th>
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
  </div></div>
</div>
{% endif %}

<!-- BOX SPREAD TABLE -->
<div class="sec">
  <div class="sh sh-static">
    <span>Box Spread Analysis — {{ pairs|length }} pairs &nbsp;·&nbsp; ₹{{ "{:,.0f}".format(capital) }} &nbsp;·&nbsp; Tax {{ tax_rate|int }}% &nbsp;·&nbsp; Sorted by Ann. Return ↓</span>
  </div>
  <div class="tw">
    <table>
      <thead><tr>
        <th class="l group-a">K1</th>
        <th class="l group-a">K2</th>
        <th class="group-a">Width</th>
        <th class="group-a">DTE</th>
        <th class="group-b">Net Debit</th>
        <th class="group-b">Total Costs</th>
        <th class="group-c">Net P&L/lot</th>
        <th class="group-c">Ann.%</th>
        <th class="group-c">Post-Tax%</th>
        <th class="group-d">Impact Cost</th>
        <th class="group-d">Adj P&L</th>
        <th class="group-e">Max Lots</th>
        <th class="group-e">Total P&L</th>
        <th class="group-e">OI</th>
        <th class="group-e">Exec</th>
        <th>Signal</th>
        <th class="l">Why</th>
      </tr></thead>
      <tbody>
      {% if pairs %}{% for p in pairs %}
        {% set display_signal = p.get('hte_signal', p.signal) %}
        {% set total_costs = (p.entry_stt or 0) + (p.settl_stt or 0) + (p.other_costs or 0) %}
        <tr>
          <td class="l">{{ "{:,}".format(p.k1|int) }}</td>
          <td class="l">{{ "{:,}".format(p.k2|int) }}</td>
          <td>{{ "{:,}".format(p.box_w|int) }}</td>
          <td>{{ d.get('dte','?') }}</td>
          <td>{{ inr(p.net_debit) }}</td>
          <td title="Entry STT {{ inr(p.entry_stt) }} + Settl STT {{ inr(p.settl_stt) }} + Other {{ inr(p.other_costs) }}">{{ inr(total_costs) }}</td>
          <td style="font-weight:700;color:{% if p.net_pnl>=0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(p.net_pnl) }}</td>
          <td style="font-weight:700;color:{% if p.ann_ret>=params.rfr %}#16a34a{% elif p.ann_ret>=0 %}#d97706{% else %}#dc2626{% endif %}">{{ pct(p.ann_ret) }}</td>
          <td style="color:{% if p.post_tax_ann and p.post_tax_ann>=0 %}#16a34a{% else %}#dc2626{% endif %}">{{ pct(p.post_tax_ann) }}</td>
          <td style="color:{% if p.get('impact_cost') and p.get('impact_cost',0)>2000 %}#dc2626{% elif p.get('impact_cost') and p.get('impact_cost',0)>500 %}#d97706{% else %}#16a34a{% endif %}">
            {% if p.get('impact_cost') is not none %}{{ inr(p.get('impact_cost')) }}{% else %}<span class="na">—</span>{% endif %}
          </td>
          <td style="font-weight:700;color:{% if p.get('adj_net_pnl') is not none %}{% if p.get('adj_net_pnl',0)>=0 %}#16a34a{% else %}#dc2626{% endif %}{% else %}#94a3b8{% endif %}">
            {% if p.get('adj_net_pnl') is not none %}{{ inr(p.get('adj_net_pnl')) }}{% else %}<span class="na">—</span>{% endif %}
          </td>
          <td style="font-weight:600;color:{% if p.lots_possible>=5 %}#16a34a{% elif p.lots_possible>=1 %}#d97706{% else %}#dc2626{% endif %}">
            {% if p.lots_possible>0 %}{{ p.lots_possible }}{% else %}<span class="na">0</span>{% endif %}
          </td>
          <td style="font-weight:700;color:{% if p.adj_total_pnl is not none and p.adj_total_pnl>=0 %}#16a34a{% else %}#dc2626{% endif %}">
            {% if p.adj_total_pnl is not none %}{{ inr(p.adj_total_pnl) }}{% elif p.total_pnl is not none %}{{ inr(p.total_pnl) }}{% else %}<span class="na">—</span>{% endif %}
          </td>
          <td title="{{ p.get('oi_note','') }}" style="font-size:11px">{{ p.get('oi_flag','—') }}</td>
          <td>
            {{ p.get('exec_difficulty','—') }}
            {% set er = p.get('exec_reason','') %}
            {% if er %}<br><span style="font-size:9px;color:#64748b;white-space:normal;display:block;max-width:120px;line-height:1.3">{{ er }}</span>{% endif %}
          </td>
          <td>
            {% if display_signal=='execute' %}<span class="pill pg">✅ EXECUTE{% if p.get('signal_basis')=='adj' %} (adj){% endif %}</span>
            {% elif display_signal=='borderline' %}<span class="pill pa">⚠ BORDERLINE{% if p.get('signal_basis')=='adj' %} (adj){% endif %}</span>
            {% else %}<span class="pill pr">❌ AVOID</span>{% endif %}
          </td>
          <td class="l" style="font-size:11px;color:#475569;max-width:200px;white-space:normal;line-height:1.4">
            {{ p.get('signal_reason','') }}
          </td>
        </tr>
      {% endfor %}{% else %}
        <tr><td colspan="17"><div class="empty">{% if not authenticated %}Login at /admin{% elif not active %}Select an expiry{% else %}No pairs match this filter{% endif %}</div></td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>
</div>

<div style="text-align:center;font-size:11px;color:#94a3b8;padding-bottom:20px">
  Live data via Fyers API v3 &nbsp;·&nbsp; NSE European-style cash-settled index options &nbsp;·&nbsp; Not financial advice &nbsp;·&nbsp;
  Page auto-refreshes every {{ refresh_sec }}s &nbsp;·&nbsp; <a href="/calc" style="color:#3b82f6">Step-by-step calculator</a> &nbsp;·&nbsp; <a href="/history" style="color:#3b82f6">Opportunity history</a>
</div>
</div>
</body></html>"""

CALC_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Box Spread Calculator — Step by Step</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#f0f2f5;color:#1a1a1a}
.topbar{background:#0f172a;padding:12px 20px;display:flex;align-items:center;justify-content:space-between}
.t1{font-size:15px;font-weight:700;color:#f8fafc}
.t2{font-size:11px;color:#94a3b8;margin-top:2px}
.main{padding:20px;max-width:900px;margin:0 auto}
.sec{background:#fff;border-radius:9px;box-shadow:0 1px 2px rgba(0,0,0,.06);margin-bottom:16px;overflow:hidden}
.sh{padding:10px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px}
.sb{padding:16px}
/* Input grid */
.igrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}
.irow{display:flex;flex-direction:column;gap:4px}
.irow label{font-size:11px;color:#64748b;font-weight:600}
.irow span{font-size:10px;color:#94a3b8}
.irow input{padding:8px 10px;border:1.5px solid #e2e8f0;border-radius:6px;font-size:14px;font-family:monospace;background:#fff;transition:border-color .15s}
.irow input:focus{outline:none;border-color:#3b82f6}
.btn{padding:9px 24px;background:#0f172a;color:#fff;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
.btn:hover{background:#1e293b}
/* Steps */
.step{display:flex;align-items:flex-start;gap:14px;padding:10px 0;border-bottom:1px solid #f1f5f9}
.step:last-child{border-bottom:none}
.step-num{width:24px;height:24px;border-radius:50%;background:#0f172a;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}
.step-body{flex:1}
.step-title{font-weight:600;font-size:13px;margin-bottom:2px}
.step-formula{font-family:monospace;font-size:11px;color:#64748b;margin-bottom:4px;background:#f8fafc;padding:3px 7px;border-radius:4px;display:inline-block}
.step-result{font-family:monospace;font-size:15px;font-weight:700;color:#0f172a}
.step-note{font-size:11px;color:#94a3b8;margin-top:3px}
.step-num.g{background:#16a34a}
.step-num.r{background:#dc2626}
.step-num.a{background:#d97706}
/* Summary box */
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:4px}
.scard{border-radius:8px;padding:12px 14px;text-align:center}
.scard-label{font-size:11px;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}
.scard-val{font-size:22px;font-weight:700;font-family:monospace}
.verdict{border-radius:8px;padding:14px 18px;margin-top:12px;font-size:14px;font-weight:600;text-align:center}
.sub{font-size:11px;color:#64748b;margin-top:3px;font-weight:400}
a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}
</style>
</head>
<body>
<div class="topbar">
  <div>
    <div class="t1">Box Spread Step-by-Step Calculator</div>
    <div class="t2">Enter any 4 prices manually — every calculation shown transparently</div>
  </div>
  <div style="display:flex;gap:16px"><a href="/" style="color:#94a3b8;font-size:12px">← Back to scanner</a><a href="/history" style="color:#94a3b8;font-size:12px">History →</a></div>
</div>

<div class="main">
<!-- INPUT FORM -->
<div class="sec">
  <div class="sh">Enter the 4 leg prices (from any source — live quote, Excel, or manual)</div>
  <div class="sb">
    <form method="GET" action="/calc">
      <div class="igrid">
        <div class="irow">
          <label>K1 — Lower Strike</label>
          <input type="number" name="k1" value="{{ k1|int }}" step="50">
          <span>e.g. 24000</span>
        </div>
        <div class="irow">
          <label>K2 — Higher Strike</label>
          <input type="number" name="k2" value="{{ k2|int }}" step="50">
          <span>e.g. 25000</span>
        </div>
        <div class="irow">
          <label>Days to Expiry (DTE)</label>
          <input type="number" name="dte" value="{{ dte|int }}" step="1">
          <span>e.g. 89</span>
        </div>
        <div style=""></div>
        <div class="irow">
          <label>📞 Call Ask at K1 (BUY)</label>
          <input type="number" name="ca1" value="{{ ca1 }}" step="0.05">
          <span>You pay this — debit leg</span>
        </div>
        <div class="irow">
          <label>📞 Call Bid at K2 (SELL)</label>
          <input type="number" name="cb2" value="{{ cb2 }}" step="0.05">
          <span>You receive this — credit leg</span>
        </div>
        <div class="irow">
          <label>🔵 Put Ask at K2 (BUY)</label>
          <input type="number" name="pa2" value="{{ pa2 }}" step="0.05">
          <span>You pay this — debit leg</span>
        </div>
        <div class="irow">
          <label>🔵 Put Bid at K1 (SELL)</label>
          <input type="number" name="pb1" value="{{ pb1 }}" step="0.05">
          <span>You receive this — credit leg</span>
        </div>
      </div>
      <button type="submit" class="btn">Calculate →</button>
      &nbsp;&nbsp;<span style="font-size:11px;color:#94a3b8">Lot size: {{ params.lot_size }} · Lots: {{ params.num_lots }} · Total units: {{ lots }}</span>
    </form>
  </div>
</div>

{% if has_input %}
<!-- STEP BY STEP BREAKDOWN -->
<div class="sec">
  <div class="sh">Step-by-Step Calculation — K1={{ k1|int }} / K2={{ k2|int }} / DTE={{ dte|int }}</div>
  <div class="sb">

    <div class="step">
      <div class="step-num">1</div>
      <div class="step-body">
        <div class="step-title">Box Width &amp; Settlement Value</div>
        <div class="step-formula">Box Width = K2 − K1 = {{ k2|int }} − {{ k1|int }} = {{ box_w|int }}</div><br>
        <div class="step-formula">Box Value (per lot) = Box Width × Lot Size = {{ box_w|int }} × {{ params.lot_size }} = {{ box_val|int }}</div>
        <div class="step-note">This is what the box ALWAYS settles at on expiry — regardless of where NIFTY is. Fully direction-neutral.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">2</div>
      <div class="step-body">
        <div class="step-title">Net Debit (what you pay to enter)</div>
        <div class="step-formula">Per unit = Call Ask(K1) + Put Ask(K2) − Call Bid(K2) − Put Bid(K1)</div>
        <div class="step-formula">= {{ ca1 }} + {{ pa2 }} − {{ cb2 }} − {{ pb1 }} = {{ "%.4f"|format(net_debit_unit) }} per unit</div>
        <div class="step-formula">Per lot = {{ "%.4f"|format(net_debit_unit) }} × {{ lots }} units = <strong>{{ inr(net_debit_total) }}</strong></div>
        <div class="step-note">This is your capital deployed. You pay this upfront to enter the position.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">3</div>
      <div class="step-body">
        <div class="step-title">Gross Profit (before all costs)</div>
        <div class="step-formula">Box Value − Net Debit = {{ inr(box_val) }} − {{ inr(net_debit_total) }} = {{ inr(box_val - net_debit_total) }}</div>
        <div class="step-note">This is the theoretical profit if there were zero transaction costs. Real profit will be lower.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">4</div>
      <div class="step-body">
        <div class="step-title">Entry STT — Securities Transaction Tax (sell legs)</div>
        <div class="step-formula">Sell Premium = Call Bid(K2) + Put Bid(K1) = {{ cb2 }} + {{ pb1 }} = {{ cb2 + pb1 }} per unit</div>
        <div class="step-formula">Sell Premium (lot) = {{ cb2 + pb1 }} × {{ lots }} = {{ (cb2 + pb1) * lots }}</div>
        <div class="step-formula">Entry STT = {{ params.stt_entry_pct }}% × {{ (cb2 + pb1) * lots }} = <strong>{{ inr(entry_stt) }}</strong></div>
        <div class="step-note">STT charged only on sell-side premiums at entry. Deep ITM sells (high premium) = high STT.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">5</div>
      <div class="step-body">
        <div class="step-title">Settlement STT — charged at expiry (always)</div>
        <div class="step-formula">Settlement STT = {{ params.stt_settl_pct }}% × Box Value = {{ params.stt_settl_pct }}% × {{ inr(box_val) }} = <strong>{{ inr(settl_stt) }}</strong></div>
        <div class="step-note">⚠ This is unique to box spreads held to expiry. NSE charges 0.125% on the intrinsic settlement value. Cannot be avoided.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">6</div>
      <div class="step-body">
        <div class="step-title">Brokerage + GST</div>
        <div class="step-formula">Brokerage = 4 legs × ₹{{ params.broker_per_leg }} = ₹{{ brokerage }}</div>
        <div class="step-formula">GST ({{ params.gst_pct }}%) = ₹{{ "%.2f"|format(gst) }}</div>
        <div class="step-formula">Total = <strong>₹{{ "%.2f"|format(brokerage + gst) }}</strong></div>
        <div class="step-note">Fixed regardless of trade size — hurts small capital boxes disproportionately.</div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">7</div>
      <div class="step-body">
        <div class="step-title">NSE Transaction Charges</div>
        <div class="step-formula">Total Premium (all 4 legs) = ({{ ca1 }} + {{ pa2 }} + {{ cb2 }} + {{ pb1 }}) × {{ lots }} = {{ "%.2f"|format(total_prem) }}</div>
        <div class="step-formula">NSE Txn ({{ params.txn_pct }}%) = <strong>{{ inr(txn_charge) }}</strong> &nbsp;&nbsp; SEBI ({{ params.sebi_pct }}%) = <strong>{{ inr(sebi_chg) }}</strong></div>
      </div>
    </div>

    <div class="step">
      <div class="step-num">8</div>
      <div class="step-body">
        <div class="step-title">Stamp Duty + Slippage</div>
        <div class="step-formula">Buy Premium = ({{ ca1 }} + {{ pa2 }}) × {{ lots }} = {{ "%.2f"|format(buy_prem) }}</div>
        <div class="step-formula">Stamp Duty ({{ params.stamp_pct }}% of buy premium) = <strong>{{ inr(stamp) }}</strong></div>
        <div class="step-formula">Slippage = 4 legs × {{ params.slip_per_leg }} pts × {{ lots }} units = <strong>{{ inr(slip) }}</strong></div>
      </div>
    </div>

    <div class="step">
      <div class="step-num {% if net_pnl >= 0 %}g{% else %}r{% endif %}">9</div>
      <div class="step-body">
        <div class="step-title">Final Net P&L</div>
        <div class="step-formula">Box Value − Net Debit − Entry STT − Settlement STT − Other Costs</div>
        <div class="step-formula">= {{ inr(box_val) }} − {{ inr(net_debit_total) }} − {{ inr(entry_stt) }} − {{ inr(settl_stt) }} − {{ inr(other_costs) }}</div>
        <div class="step-formula" style="font-size:13px">= <strong style="color:{% if net_pnl >= 0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(net_pnl) }}</strong></div>
      </div>
    </div>

    <div class="step">
      <div class="step-num {% if ann_ret >= params.rfr %}g{% elif ann_ret >= 0 %}a{% else %}r{% endif %}">10</div>
      <div class="step-body">
        <div class="step-title">Annualised Return</div>
        <div class="step-formula">Return % = Net P&L ÷ Net Debit = {{ inr(net_pnl) }} ÷ {{ inr(net_debit_total) }} = {{ "%.4f"|format(ret_pct) }}%</div>
        <div class="step-formula">Annualised = Return% × (365 ÷ DTE) = {{ "%.4f"|format(ret_pct) }}% × (365 ÷ {{ dte|int }}) = <strong>{{ pct(ann_ret) }}</strong></div>
        <div class="step-note">Risk-free rate (FD/T-bill): {{ params.rfr }}% — {% if ann_ret >= params.rfr %}✅ Beats RFR by {{ "%.2f"|format(ann_ret - params.rfr) }}%{% else %}❌ Below RFR — not a true arbitrage{% endif %}</div>
      </div>
    </div>

  </div>
</div>

<!-- SUMMARY -->
<div class="sec">
  <div class="sh">Summary</div>
  <div class="sb">
    <div class="summary">
      <div class="scard" style="background:#f0fdf4">
        <div class="scard-label">Net P&L per lot</div>
        <div class="scard-val" style="color:{% if net_pnl >= 0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(net_pnl) }}</div>
      </div>
      <div class="scard" style="background:#eff6ff">
        <div class="scard-label">Annualised Return</div>
        <div class="scard-val" style="color:#2563eb">{{ pct(ann_ret) }}</div>
      </div>
      <div class="scard" style="background:#f8fafc">
        <div class="scard-label">Capital Deployed</div>
        <div class="scard-val" style="color:#0f172a">{{ inr(net_debit_total) }}</div>
      </div>
    </div>
    <div class="verdict" style="background:{% if net_pnl > 0 and ann_ret >= params.rfr %}#f0fdf4;color:#15803d;border:1px solid #bbf7d0{% elif net_pnl > 0 %}#fefce8;color:#854d0e;border:1px solid #fef08a{% else %}#fef2f2;color:#b91c1c;border:1px solid #fecaca{% endif %}">
      {% if net_pnl > 0 and ann_ret >= params.rfr %}
        ✅ EXECUTE — Net profit {{ inr(net_pnl) }}/lot at {{ pct(ann_ret) }} p.a. — beats risk-free rate by {{ "%.2f"|format(ann_ret - params.rfr) }}%
      {% elif net_pnl > 0 %}
        ⚠ BORDERLINE — Profitable ({{ inr(net_pnl) }}/lot) but {{ pct(ann_ret) }} p.a. does not beat the {{ params.rfr }}% risk-free rate
      {% else %}
        ❌ AVOID — Net loss of {{ inr(net_pnl|abs) }}/lot after all costs
      {% endif %}
      <div class="sub">Cost breakdown: Entry STT {{ inr(entry_stt) }} + Settlement STT {{ inr(settl_stt) }} + Brokerage+GST ₹{{ "%.2f"|format(brokerage+gst) }} + Txn/SEBI {{ inr(txn_charge+sebi_chg) }} + Stamp+Slip {{ inr(stamp+slip) }} = Total costs {{ inr(entry_stt+settl_stt+other_costs) }}</div>
    </div>
  </div>
</div>
{% endif %}

</div></body></html>"""

HISTORY_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opportunity History — NIFTY Box Spread</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#f0f2f5;color:#1a1a1a}
.topbar{background:#0f172a;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.t1{font-size:15px;font-weight:700;color:#f8fafc}
.t2{font-size:11px;color:#94a3b8;margin-top:2px}
.main{padding:16px 20px;max-width:1600px;margin:0 auto}
.sec{background:#fff;border-radius:9px;box-shadow:0 1px 2px rgba(0,0,0,.06);margin-bottom:14px;overflow:hidden}
.sh{padding:10px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px;display:flex;justify-content:space-between;align-items:center}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:11.5px}
th{background:#f1f5f9;padding:7px 10px;text-align:right;font-size:10px;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0;white-space:nowrap;text-transform:uppercase;letter-spacing:.3px}
th.l{text-align:left}
td{padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Courier New',monospace;white-space:nowrap;vertical-align:top}
td.l{text-align:left;font-family:inherit}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700}
.pg{background:#dcfce7;color:#15803d}.pa{background:#fef3c7;color:#92400e}.pr{background:#fee2e2;color:#b91c1c}
.logic{font-size:10px;color:#64748b;line-height:1.6;font-family:'Courier New',monospace;background:#f8fafc;padding:4px 6px;border-radius:4px;max-width:280px;white-space:pre-wrap}
.na{color:#cbd5e1}
.empty{text-align:center;padding:48px;color:#94a3b8}
.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;margin-left:4px}
.badge-new{background:#dbeafe;color:#1e40af}
.badge-adj{background:#fef3c7;color:#92400e}
.filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.fi{padding:5px 10px;border:1px solid #e2e8f0;border-radius:5px;background:#fff;font-size:12px;font-family:inherit}
</style>
<script>
function filterTable(){
  var exp = document.getElementById('fExp').value.toLowerCase();
  var sig = document.getElementById('fSig').value;
  var rows = document.querySelectorAll('tbody tr');
  rows.forEach(function(r){
    var show = true;
    if(exp && !r.dataset.expiry.includes(exp)) show=false;
    if(sig && r.dataset.signal !== sig) show=false;
    r.style.display = show?'':'none';
  });
}
</script>
</head>
<body>
<div class="topbar">
  <div>
    <div class="t1">Opportunity History</div>
    <div class="t2">Every Execute signal logged with timestamp and assumptions in force at that moment</div>
  </div>
  <a href="/" style="color:#94a3b8;font-size:12px">← Live Scanner</a>
</div>
<div class="main">

<div class="sec">
  <div class="sh">
    <span>{{ rows|length }} records</span>
    <div class="filters">
      <input id="fExp" class="fi" style="width:140px" placeholder="Filter expiry..." oninput="filterTable()">
      <select id="fSig" class="fi" onchange="filterTable()">
        <option value="">All signals</option>
        <option value="execute">Execute</option>
        <option value="borderline">Borderline</option>
        <option value="loss">Loss</option>
      </select>
    </div>
  </div>
  <div class="tw">
  <table>
    <thead><tr>
      <th class="l">Logged At (IST)</th>
      <th class="l">Expiry</th>
      <th>K1</th><th>K2</th><th>Width</th><th>DTE</th>
      <th>C Ask(K1)</th><th>C Bid(K2)</th><th>P Ask(K2)</th><th>P Bid(K1)</th>
      <th>Net Debit</th><th>Box Value</th>
      <th>Entry STT</th><th>Settl STT</th><th>Other Costs</th>
      <th>Net P&amp;L</th><th>Ann%</th>
      <th>Adj P&amp;L</th><th>Adj Ann%</th>
      <th>Spread%</th><th>Impact Cost</th>
      <th>Exec</th><th>OI Flag</th>
      <th>Signal</th>
      <th class="l">Assumptions at time of signal</th>
    </tr></thead>
    <tbody>
    {% if rows %}
      {% for r in rows %}
      {% set snap = r.logic_snapshot if r.logic_snapshot else {} %}
      <tr data-expiry="{{ (r.expiry or '')|lower }}" data-signal="{{ r.signal or '' }}">
        <td class="l" style="white-space:nowrap;font-family:monospace;font-size:11px">
          {{ r.logged_at.strftime('%d %b %Y %H:%M:%S') if r.logged_at else '—' }}
        </td>
        <td class="l" style="font-weight:600">{{ r.expiry or '—' }}</td>
        <td>{{ "{:,}".format(r.k1) if r.k1 else '—' }}</td>
        <td>{{ "{:,}".format(r.k2) if r.k2 else '—' }}</td>
        <td>{{ "{:,}".format(r.box_w) if r.box_w else '—' }}</td>
        <td>{{ r.dte or '—' }}</td>
        <td>{{ "%.2f"|format(r.ca1) if r.ca1 else '—' }}</td>
        <td>{{ "%.2f"|format(r.cb2) if r.cb2 else '—' }}</td>
        <td>{{ "%.2f"|format(r.pa2) if r.pa2 else '—' }}</td>
        <td>{{ "%.2f"|format(r.pb1) if r.pb1 else '—' }}</td>
        <td>{{ inr(r.net_debit) }}</td>
        <td>{{ inr(r.box_value) }}</td>
        <td>{{ inr(r.entry_stt) }}</td>
        <td>{{ inr(r.settl_stt) }}</td>
        <td>{{ inr(r.other_costs) }}</td>
        <td style="font-weight:700;color:{% if r.net_pnl and r.net_pnl>=0 %}#16a34a{% else %}#dc2626{% endif %}">{{ inr(r.net_pnl) }}</td>
        <td style="color:{% if r.ann_ret and r.ann_ret>=12 %}#16a34a{% elif r.ann_ret and r.ann_ret>=0 %}#d97706{% else %}#dc2626{% endif %}">{{ pct(r.ann_ret|float if r.ann_ret else None) }}</td>
        <td style="font-weight:700;color:{% if r.adj_net_pnl and r.adj_net_pnl>=0 %}#16a34a{% else %}#94a3b8{% endif %}">{{ inr(r.adj_net_pnl) if r.adj_net_pnl else '—' }}</td>
        <td style="color:{% if r.adj_ann_ret and r.adj_ann_ret>=12 %}#16a34a{% elif r.adj_ann_ret and r.adj_ann_ret>=0 %}#d97706{% else %}#94a3b8{% endif %}">{{ pct(r.adj_ann_ret|float if r.adj_ann_ret else None) }}</td>
        <td>{{ "%.2f"|format(r.spread_pct) ~ "%" if r.spread_pct else '—' }}</td>
        <td style="color:{% if r.impact_cost and r.impact_cost>2000 %}#dc2626{% elif r.impact_cost and r.impact_cost>500 %}#d97706{% else %}#16a34a{% endif %}">{{ inr(r.impact_cost) if r.impact_cost else '—' }}</td>
        <td>{{ r.exec_difficulty or '—' }}</td>
        <td style="font-size:10px">{{ r.oi_flag or '—' }}</td>
        <td>
          {% if r.signal == 'execute' %}<span class="pill pg">✅ EXECUTE{% if r.signal_basis == 'adj' %}<span class="badge badge-adj">adj</span>{% endif %}</span>
          {% elif r.signal == 'borderline' %}<span class="pill pa">⚠ BORDERLINE</span>
          {% else %}<span class="pill pr">❌ AVOID</span>{% endif %}
          {% if not r.hold_to_expiry %}<br><span class="badge badge-new">early exit</span>{% endif %}
        </td>
        <td class="l">
          <div class="logic">Lot: {{ snap.get('lot_size','?') }} | Entry STT: {{ snap.get('stt_entry_pct','?') }}%
Settl STT: {{ snap.get('stt_settl_pct','?') }}% | Min Ann: {{ snap.get('min_ann_ret','?') }}%
Brokerage: ₹{{ snap.get('broker_per_leg','?') }}/leg | RFR: {{ snap.get('rfr','?') }}%
Max Spread: {{ snap.get('max_spread_pct','?') }}% | Slip: {{ snap.get('slip_per_leg','?') }}pts</div>
        </td>
      </tr>
      {% endfor %}
    {% else %}
      <tr><td colspan="25"><div class="empty">No history yet — Execute signals will appear here once the scanner finds them.</div></td></tr>
    {% endif %}
    </tbody>
  </table>
  </div>
</div>

<div style="text-align:center;font-size:11px;color:#94a3b8;padding-bottom:20px">
  History stored in Railway Postgres · Survives redeploys · Assumptions column shows exact logic in force when each signal was logged
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
    init_db()
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




@app.route("/livetest")
def livetest():
    token = load_token()
    if not token:
        return jsonify({"error": "No token"})
    try:
        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=token, log_path="")
        r = fyers.optionchain(data={"symbol": "NSE:NIFTY50-INDEX", "strikecount": "", "timestamp": ""})
        rows = r.get("data", {}).get("optionsChain", [])
        first_ce = next((row for row in rows if row.get("option_type") == "CE"), None)
        first_pe = next((row for row in rows if row.get("option_type") == "PE"), None)
        return jsonify({
            "status": r.get("s"),
            "total_rows": len(rows),
            "first_CE_all_fields": first_ce,
            "first_PE_all_fields": first_pe,
            "CE_field_names": sorted(first_ce.keys()) if first_ce else [],
            "PE_field_names": sorted(first_pe.keys()) if first_pe else [],
        })
    except Exception as e:
        return jsonify({"exception": str(e)})


def startup():
    init_db()
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
