import os
import sys
import json
import time
import uuid
import threading
import requests
import hmac
import base64
import hashlib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- NASTAVENÍ TELEGRAM NOTIFIKACÍ A PARAMETRŮ ---
TELEGRAM_BOT_TOKEN = "9068673685:AAEwXgVLOdO-kZ3Pvm3ATu87vZ6eZ-zP-cY"
TELEGRAM_CHAT_ID = "9209356727"
ALERT_STATE_FILE = "/tmp/okx_telegram_buffer_v9.json"
WEEKLY_LOG_FILE = "/tmp/okx_weekly_trades_log.json"

DEFAULT_SL_PCT = 0.0030       # Výchozí Market Stop-Loss 0.30 % (Skupina 1 Macro & Setup 2)
S2_LIMIT_PCT = 0.0005         # Limit Entry u Setupu 2 na 0.05 % od sweepnuté hladiny
PENDING_ORDER_TTL_SEC = 900   # Automatické zrušení nevyplněné VSTUPNÍ limitky po 15 minutách (900 s)
S1_MEMORY_TTL_SEC = 1200      # Paměť potvrzeného 5M Setupu 1 při čekání na 1M strukturu (20 min)

# --- ZABEZPEČENÉ NAČTENÍ OKX API KLÍČŮ ZE STREAMLIT SECRETS ---
try:
    OKX_SECRETS = {
        "API_KEY": st.secrets.get("OKX_API_KEY", ""),
        "SECRET_KEY": st.secrets.get("OKX_SECRET_KEY", ""),
        "PASSPHRASE": st.secrets.get("OKX_PASSPHRASE", ""),
        "INST_ID": st.secrets.get("OKX_INST_ID", "BTC-USD_UM_XPERP-310404"),
        "CONTRACT_BTC": float(st.secrets.get("OKX_CONTRACT_BTC", "0.0001")),
        "ENABLED": str(st.secrets.get("AI_TRADING_ENABLED", "false")).lower() == "true"
    }
except Exception:
    OKX_SECRETS = {"ENABLED": False}

@st.cache_resource
def get_realtime_engine():
    if "OKX_GLOBAL_LOCK" not in sys.__dict__:
        sys.__dict__["OKX_GLOBAL_LOCK"] = threading.Lock()
    return {
        "lock": sys.__dict__["OKX_GLOBAL_LOCK"],
        "fut_buckets": {},
        "spot_buckets": {},
        "fut_1m_buckets": {},
        "spot_1m_buckets": {},
        "last_fut_trade_id": None,
        "last_spot_trade_id": None,
        "oi_start_map": {},
        "oi_live_delta": {},
        "last_oi_btc": None,
        "liq_cache": {
            "candle_ts": 0,
            "upper_p": 0.0,
            "upper_btc": 0.0,
            "lower_p": 0.0,
            "lower_btc": 0.0
        },
        "s1_memory": {
            "active": False,
            "direction": "",
            "group_id": "",
            "setup_label": "",
            "header_text": "",
            "confirm_1m_ts": 0,
            "locked_at_sec": 0.0,
            "zone_extreme_p": 0.0,
            "pb_pct": 0.0012,
            "sl_pct": 0.0030,
            "tp_mode": "SPLIT_50_50",
            "box_mins": 0,
            "box_spread_pct": 0.0,
            "box_cvd": 0.0,
            "box_spot": 0.0
        },
        "tp_plan": {
            "active": False,
            "tp_mode": "SPLIT_50_50",
            "close_side": "",
            "entry_px": 0.0,
            "tp1_px": 0,
            "tp2_px": 0,
            "ct1": 0,
            "ct2": 0,
            "tp_placed": False
        },
        "be_moved_algos": set()
    }

ENGINE = get_realtime_engine()

def _load_alert_history():
    try:
        if os.path.exists(ALERT_STATE_FILE):
            with open(ALERT_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_alert_history(history_dict):
    try:
        with open(ALERT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(history_dict, f)
    except Exception:
        pass

def log_weekly_trade_event(record_dict):
    try:
        with ENGINE["lock"]:
            logs = []
            if os.path.exists(WEEKLY_LOG_FILE):
                try:
                    with open(WEEKLY_LOG_FILE, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except Exception:
                    logs = []
            logs.append(record_dict)
            with open(WEEKLY_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_weekly_trade_logs():
    try:
        if os.path.exists(WEEKLY_LOG_FILE):
            with open(WEEKLY_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def get_setup_cooldown_remaining(lock_key, lock_duration=3600):
    now_ts = time.time()
    with ENGINE["lock"]:
        history = _load_alert_history()
        last_trig = float(history.get(lock_key, 0.0))
        elapsed = now_ts - last_trig
        if elapsed < lock_duration:
            return int(lock_duration - elapsed)
    return 0

def _okx_signed_request(method, path, body=""):
    api_key = OKX_SECRETS.get("API_KEY", "")
    sec_key = OKX_SECRETS.get("SECRET_KEY", "")
    passphrase = OKX_SECRETS.get("PASSPHRASE", "")
    base_url = "https://eea.okx.com"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    msg = ts + method + path + body
    mac = hmac.new(bytes(sec_key, "utf-8"), bytes(msg, "utf-8"), digestmod=hashlib.sha256)
    sign = base64.b64encode(mac.digest()).decode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "x-simulated-trading": "0"
    }
    if method == "GET":
        return requests.get(base_url + path, headers=headers, timeout=5).json()
    else:
        return requests.post(base_url + path, headers=headers, data=body, timeout=5).json()

def odesli_upozorneni(lock_key, setup_nazev, detail_zpravy, lock_duration=3600, force=False):
    now_ts = time.time()
    with ENGINE["lock"]:
        history = _load_alert_history()
        if not force:
            last_lock = float(history.get(lock_key, 0.0))
            if (now_ts - last_lock) < lock_duration:
                return False
        history[lock_key] = now_ts
        _save_alert_history(history)

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚨 <b>{setup_nazev}</b>\n\n{detail_zpravy}",
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"Telegram alert selhal: {e}")
        return False

# --- AKTIVNÍ SPRÁVA POZIC: 15M TTL VSTUPU + DYNAMICKÝ MAKER (POST-ONLY) TP + AUTO BREAK-EVEN ---
def manage_active_okx_lifecycle():
    if not OKX_SECRETS.get("ENABLED"):
        return
    if not OKX_SECRETS.get("API_KEY") or not OKX_SECRETS.get("SECRET_KEY"):
        return

    inst_id = OKX_SECRETS["INST_ID"]
    ct_val = OKX_SECRETS["CONTRACT_BTC"]
    base_url = "https://eea.okx.com"
    now_ms = int(time.time() * 1000)

    try:
        pend = _okx_signed_request("GET", f"/api/v5/trade/orders-pending?instId={inst_id}")
        pend_list = pend.get("data", []) if isinstance(pend, dict) else []

        entry_pend = []
        tp_pend = []
        for ord_item in pend_list:
            is_ro = str(ord_item.get("reduceOnly", "false")).lower() == "true"
            if is_ro:
                tp_pend.append(ord_item)
            else:
                entry_pend.append(ord_item)

        # 1. Kontrola čekajících VSTUPNÍCH Limit příkazů – zrušení po 15 minutách (900 s), nikdy nerušíme TP!
        for ord_item in entry_pend:
            c_time = int(ord_item.get("cTime", now_ms))
            ord_id = str(ord_item.get("ordId", ""))
            if ord_id and (now_ms - c_time) >= (PENDING_ORDER_TTL_SEC * 1000):
                cancel_body = json.dumps({"instId": inst_id, "ordId": ord_id})
                c_res = _okx_signed_request("POST", "/api/v5/trade/cancel-order", cancel_body)
                if str(c_res.get("code")) == "0":
                    odesli_upozorneni(
                        f"CANCEL_{ord_id}",
                        "AI AGENT: ZRUŠENA EXPIROVANÁ VSTUPNÍ LIMITKA (15 MIN)",
                        f"⏱️ Nevyplněná vstupní Post-Only objednávka ({ord_id}) byla po 15 minutách automaticky zrušena, protože cena utekla.",
                        lock_duration=300,
                        force=True
                    )

        # 2. Kontrola otevřené pozice
        pos = _okx_signed_request("GET", f"/api/v5/account/positions?instId={inst_id}")
        pos_list = pos.get("data", []) if isinstance(pos, dict) else []

        active_pos = None
        for p in pos_list:
            pos_sz = abs(float(p.get("pos", "0") or 0.0))
            avg_px = float(p.get("avgPx", "0") or 0.0)
            if pos_sz > 0 and avg_px > 0:
                active_pos = p
                break

        if active_pos is None and len(entry_pend) == 0:
            with ENGINE["lock"]:
                if ENGINE["tp_plan"].get("active"):
                    ENGINE["tp_plan"]["active"] = False
            return

        if active_pos is not None:
            raw_pos = float(active_pos.get("pos", "0") or 0.0)
            pos_sz = abs(raw_pos)
            avg_px = float(active_pos.get("avgPx", "0") or 0.0)
            pos_side_val = str(active_pos.get("posSide", "net")).lower()

            with ENGINE["lock"]:
                tp_plan = dict(ENGINE["tp_plan"])
                if not tp_plan.get("active"):
                    saved_hist = _load_alert_history()
                    if isinstance(saved_hist.get("ACTIVE_TP_PLAN"), dict):
                        tp_plan = saved_hist["ACTIVE_TP_PLAN"]
                        ENGINE["tp_plan"] = dict(tp_plan)

            tp_mode = tp_plan.get("tp_mode", "SPLIT_50_50")

            # 2A. Jakmile je pozice otevřená a v knize ještě neleží Maker TP, vložíme je podle tp_mode
            if len(entry_pend) == 0 and len(tp_pend) == 0 and tp_plan.get("active") and not tp_plan.get("tp_placed"):
                close_side = tp_plan.get("close_side") or ("buy" if raw_pos < 0 or pos_side_val == "short" else "sell")
                tp1_px = int(tp_plan.get("tp1_px", 0))
                tp2_px = int(tp_plan.get("tp2_px", 0))
                total_pos_ct = int(round(pos_sz))

                best_bid, best_ask = avg_px, avg_px
                try:
                    tk = requests.get(f"{base_url}/api/v5/market/ticker?instId={inst_id}", timeout=3).json().get("data", [])
                    if tk:
                        best_bid = float(tk[0].get("bidPx") or avg_px)
                        best_ask = float(tk[0].get("askPx") or avg_px)
                except Exception:
                    pass

                def place_maker_tp(sz_ct, target_px):
                    if sz_ct <= 0 or target_px <= 0:
                        return {"code": "-1"}
                    safe_px = int(round(target_px))
                    if close_side == "buy" and safe_px >= best_ask:
                        safe_px = int(round(best_bid - 1.0))
                    elif close_side == "sell" and safe_px <= best_bid:
                        safe_px = int(round(best_ask + 1.0))
                    tp_body = {
                        "instId": inst_id,
                        "tdMode": "isolated",
                        "side": close_side,
                        "ordType": "post_only",
                        "reduceOnly": True,
                        "px": str(safe_px),
                        "sz": str(sz_ct)
                    }
                    return _okx_signed_request("POST", "/api/v5/trade/order", json.dumps(tp_body))

                placed_ok = False
                tp_notif_txt = ""

                if tp_mode == "FULL_LIQ" and tp2_px > 0:
                    res_tp = place_maker_tp(total_pos_ct, tp2_px)
                    placed_ok = (str(res_tp.get("code")) == "0")
                    tp_notif_txt = f"🎯 Pozice (MACRO) otevřena @ <b>{avg_px:.0f}$</b>.\nDo knihy vložen 100% <b>Post-Only TP na Likvidační level: {tp2_px}$</b>"
                elif tp_mode == "HALF_LIQ" and tp1_px > 0:
                    res_tp = place_maker_tp(total_pos_ct, tp1_px)
                    placed_ok = (str(res_tp.get("code")) == "0")
                    tp_notif_txt = f"🎯 Pozice (MICRO) otevřena @ <b>{avg_px:.0f}$</b>.\nDo knihy vložen 100% <b>Post-Only TP na 1/2 Likvidačního levelu: {tp1_px}$</b>"
                elif tp1_px > 0 and tp2_px > 0:
                    c1 = total_pos_ct // 2
                    c2 = total_pos_ct - c1
                    res_tp1 = place_maker_tp(c1, tp1_px)
                    res_tp2 = place_maker_tp(c2, tp2_px)
                    placed_ok = (str(res_tp1.get("code")) == "0" or str(res_tp2.get("code")) == "0")
                    tp_notif_txt = f"🎯 Pozice (50/50) otevřena @ <b>{avg_px:.0f}$</b>.\nDo knihy vloženy 2x <b>Post-Only TP</b>:\n• TP1 (50 % – 1/2 Liq): <b>{tp1_px}$</b>\n• TP2 (50 % – Plný Liq): <b>{tp2_px}$</b>"

                if placed_ok:
                    with ENGINE["lock"]:
                        ENGINE["tp_plan"]["tp_placed"] = True
                        hist = _load_alert_history()
                        hist["ACTIVE_TP_PLAN"] = dict(ENGINE["tp_plan"])
                        _save_alert_history(hist)
                    odesli_upozorneni(
                        f"MAKER_TP_{int(time.time())}",
                        "AI AGENT: MAKER TP VLOŽEN DO ORDERBOOKU",
                        tp_notif_txt,
                        lock_duration=60,
                        force=True
                    )

            # 2B. Auto Break-Even (platí pro režim SPLIT_50_50 po zasažení TP1)
            if tp_mode == "SPLIT_50_50":
                expected_full_ct = int((1000.0 / avg_px) / ct_val)
                if len(entry_pend) == 0 and expected_full_ct >= 2 and pos_sz <= (expected_full_ct * 0.65):
                    be_px_str = str(int(round(avg_px)))
                    for algo_type in ["conditional", "oco"]:
                        algos = _okx_signed_request("GET", f"/api/v5/trade/orders-algo-pending?instId={inst_id}&ordType={algo_type}")
                        algo_list = algos.get("data", []) if isinstance(algos, dict) else []
                        for al in algo_list:
                            algo_id = str(al.get("algoId", ""))
                            curr_sl = float(al.get("slTriggerPx", "0") or 0.0)
                            if not algo_id or algo_id in ENGINE["be_moved_algos"]:
                                continue
                            if abs(curr_sl - avg_px) > 3.0:
                                amend_body = json.dumps({
                                    "instId": inst_id,
                                    "algoId": algo_id,
                                    "newSlTriggerPx": be_px_str,
                                    "newSlOrdPx": "-1"
                                })
                                am_res = _okx_signed_request("POST", "/api/v5/trade/amend-algos", amend_body)
                                if str(am_res.get("code")) == "0":
                                    ENGINE["be_moved_algos"].add(algo_id)
                                    odesli_upozorneni(
                                        f"BE_{algo_id}",
                                        "AI AGENT: STOP-LOSS POSUNUT NA BREAK-EVEN",
                                        f"🛡️ TP1 (první 50 % pozice) byl zasažen!\nStop-Loss zbývající poloviny pozice byl automaticky posunut na vstupní cenu Break-Even: <b>{be_px_str}$</b>.",
                                        lock_duration=300,
                                        force=True
                                    )
    except Exception:
        pass

# --- INTERNÍ AI AGENT (PŘÍMÁ MAKER POST-ONLY EXEKUCE NA OKX V5 S DYNAMICKÝM SL A TP REŽIMEM) ---
def execute_okx_agent_trade(plan):
    if not OKX_SECRETS.get("ENABLED"):
        return "🤖 AI Agent: Exekuce vypnuta (AI_TRADING_ENABLED=false)"

    try:
        api_key = OKX_SECRETS["API_KEY"]
        sec_key = OKX_SECRETS["SECRET_KEY"]
        inst_id = OKX_SECRETS["INST_ID"]
        ct_val = OKX_SECRETS["CONTRACT_BTC"]
        base_url = "https://eea.okx.com"

        if not api_key or not sec_key:
            return "🤖 AI Agent: Chybí API klíče v Secrets!"

        # 1. Kontrola otevřených pozic
        pos = _okx_signed_request("GET", f"/api/v5/account/positions?instId={inst_id}")
        if pos.get("data") and len(pos["data"]) > 0:
            for p in pos["data"]:
                if abs(float(p.get("pos", "0"))) > 0:
                    return "🤖 AI Agent: Zamítnuto (Už existuje otevřená pozice)"

        # 2. Kontrola čekajících limit příkazů
        pend = _okx_signed_request("GET", f"/api/v5/trade/orders-pending?instId={inst_id}")
        if pend.get("data") and len(pend["data"]) > 0:
            return "🤖 AI Agent: Zamítnuto (Už existuje čekající limitka)"

        # 3. Nastavení páky 10x (Isolated)
        _okx_signed_request("POST", "/api/v5/account/set-leverage", json.dumps({
            "instId": inst_id,
            "lever": "10",
            "mgnMode": "isolated"
        }))

        # 4. Kontrola živého Orderbooku (Bid/Ask), aby post_only 100% prošel jako Maker
        side = plan["side"]
        desired_px = float(plan["entry"])
        sl_pct = float(plan.get("sl_pct", DEFAULT_SL_PCT))
        tp_mode = str(plan.get("tp_mode", "SPLIT_50_50"))
        maker_px = desired_px

        try:
            tk = requests.get(f"{base_url}/api/v5/market/ticker?instId={inst_id}", timeout=3).json().get("data", [])
            if tk:
                best_bid = float(tk[0].get("bidPx") or desired_px)
                best_ask = float(tk[0].get("askPx") or desired_px)
                if side == "buy" and maker_px >= best_ask:
                    maker_px = best_bid
                elif side == "sell" and maker_px <= best_bid:
                    maker_px = best_ask
        except Exception:
            pass

        # Přepočet SL podle skupiny (0.30% / 0.20% / 0.10%) a finální Maker vstupní ceny
        if side == "sell":
            sl_px = round(maker_px * (1.0 + sl_pct))
            close_side = "buy"
        else:
            sl_px = round(maker_px * (1.0 - sl_pct))
            close_side = "sell"

        # 5. Výpočet kontraktů pro pozici 1000 USD (Marže 100 USD * Páka 10x)
        pos_usd = 1000.0
        total_btc = pos_usd / maker_px
        total_ct = int(total_btc / ct_val)

        if total_ct < 2:
            return "🤖 AI Agent: Zamítnuto (Příliš malý kapitál)"

        tp1_int = int(round(plan["tp1_limit_50pct"]))
        tp2_int = int(round(plan["tp2_limit_50pct"]))

        def place_entry_ord(sz):
            body = {
                "instId": inst_id,
                "tdMode": "isolated",
                "side": side,
                "ordType": "post_only",
                "px": str(int(round(maker_px))),
                "sz": str(sz),
                "attachAlgoOrds": [{
                    "slTriggerPx": str(int(sl_px)),
                    "slOrdPx": "-1"
                }]
            }
            return _okx_signed_request("POST", "/api/v5/trade/order", json.dumps(body))

        if tp_mode in ["FULL_LIQ", "HALF_LIQ"]:
            ct1 = total_ct
            ct2 = 0
            r1 = place_entry_ord(total_ct)
            ok_entry = (str(r1.get("code")) == "0")
            err_msg = r1.get("msg", "")
        else:
            ct1 = total_ct // 2
            ct2 = total_ct - ct1
            r1 = place_entry_ord(ct1)
            r2 = place_entry_ord(ct2)
            ok_entry = (str(r1.get("code")) == "0" or str(r2.get("code")) == "0")
            err_msg = f"{r1.get('msg', '')} {r2.get('msg', '')}"

        if ok_entry:
            new_tp_plan = {
                "active": True,
                "tp_mode": tp_mode,
                "close_side": close_side,
                "entry_px": float(round(maker_px)),
                "tp1_px": tp1_int,
                "tp2_px": tp2_int,
                "ct1": ct1,
                "ct2": ct2,
                "tp_placed": False
            }
            with ENGINE["lock"]:
                ENGINE["tp_plan"] = new_tp_plan
                hist = _load_alert_history()
                hist["ACTIVE_TP_PLAN"] = dict(new_tp_plan)
                _save_alert_history(hist)

            if tp_mode == "FULL_LIQ":
                tp_desc = f"100% Maker TP na Liq: {tp2_int}$"
            elif tp_mode == "HALF_LIQ":
                tp_desc = f"100% Maker TP na 1/2 Liq: {tp1_int}$"
            else:
                tp_desc = f"50/50 Maker TP1: {tp1_int}$ & TP2: {tp2_int}$ + Auto-BE"

            return f"🤖 AI AGENT: ZADAL MAKER (POST-ONLY) VSTUP @ {maker_px:.0f}$ (SL {sl_pct*100:.2f}%: {sl_px}$ | {tp_desc})"
        else:
            return f"⚠️ AI AGENT CHYBA: {err_msg}"

    except Exception as e:
        return f"⚠️ AI AGENT VÝJIMKA: {str(e)}"

def build_trade_plan(direction, entry_p, upper_liq_p, lower_liq_p, setup_label, sl_pct=DEFAULT_SL_PCT, tp_mode="SPLIT_50_50"):
    if direction == "SHORT":
        sl_p = entry_p * (1.0 + sl_pct)
        tp2_p = lower_liq_p if (0 < lower_liq_p < entry_p) else (entry_p * 0.988)
        tp1_p = entry_p - 0.5 * (entry_p - tp2_p)
        side_str = "sell"
    else:
        sl_p = entry_p * (1.0 - sl_pct)
        tp2_p = upper_liq_p if (upper_liq_p > entry_p) else (entry_p * 1.012)
        tp1_p = entry_p + 0.5 * (tp2_p - entry_p)
        side_str = "buy"

    sl_dist = abs(entry_p - sl_p)
    if tp_mode == "FULL_LIQ":
        eff_tp_dist = abs(entry_p - tp2_p)
    elif tp_mode == "HALF_LIQ":
        eff_tp_dist = abs(entry_p - tp1_p)
    else:
        eff_tp_dist = 0.5 * abs(entry_p - tp1_p) + 0.5 * abs(entry_p - tp2_p)

    rrr = (eff_tp_dist / sl_dist) if sl_dist > 0 else 0.0

    return {
        "setup": setup_label,
        "direction": direction,
        "side": side_str,
        "entry_type": "post_only",
        "position_usd": 1000.0,
        "margin_usd": 100.0,
        "leverage": 10,
        "sl_pct": sl_pct,
        "tp_mode": tp_mode,
        "entry": round(entry_p, 1),
        "sl_market": round(sl_p, 1),
        "tp1_limit_50pct": round(tp1_p, 1),
        "tp2_limit_50pct": round(tp2_p, 1),
        "rrr": round(rrr, 2)
    }

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide", initial_sidebar_state="collapsed")

js_theme_code = "\n".join([
    "<script>",
    "try {",
    "    const doc = window.parent.document;",
    "    let meta = doc.querySelector('meta[name=\"theme-color\"]');",
    "    if (!meta) {",
    "        meta = doc.createElement('meta');",
    "        meta.name = 'theme-color';",
    "        doc.head.appendChild(meta);",
    "    }",
    "    meta.content = '#040609';",
    "    doc.body.style.backgroundColor = '#040609';",
    "    doc.documentElement.style.backgroundColor = '#040609';",
    "} catch (e) {}",
    "</script>"
])
components.html(js_theme_code, height=0)

css_styles = "\n".join([
    "<style>",
    "@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;800;900&display=swap');",
    "#MainMenu {visibility: hidden !important; display: none !important;}",
    "header[data-testid='stHeader'] {visibility: hidden !important; display: none !important;}",
    "footer {visibility: hidden !important; display: none !important;}",
    ".viewerBadge_container__1QSob {display: none !important;}",
    "[data-testid='stAppViewBlockContainer'] {",
    "    padding-top: 0rem !important;",
    "    padding-bottom: 1.5rem !important;",
    "    padding-left: 0.4rem !important;",
    "    padding-right: 0.4rem !important;",
    "    margin-top: -65px !important;",
    "}",
    "iframe[height='0'] {display: none !important;}",
    "@keyframes app-heart-pulse {",
    "    0% { background-size: 230% auto; }",
    "    50% { background-size: 260% auto; }",
    "    100% { background-size: 230% auto; }",
    "}",
    ".stApp {",
    "    background-color: #040609;",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.35), rgba(4, 6, 9, 0.75)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_glowing_ruby_red_neon_heart.jpg');",
    "    background-attachment: fixed;",
    "    background-position: center 45%;",
    "    background-repeat: no-repeat;",
    "    animation: app-heart-pulse 3.5s infinite ease-in-out;",
    "    color: #f0f6fc;",
    "}",
    ".gold-btc-banner {",
    "    width: 100vw;",
    "    margin-left: calc(-50vw + 50%);",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.05), rgba(4, 6, 9, 0.45)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_luxurious_glowing_golden_Bi%20(1).jpg');",
    "    background-position: center center;",
    "    background-size: cover;",
    "    background-repeat: no-repeat;",
    "    height: 480px;",
    "    display: flex;",
    "    flex-direction: column;",
    "    align-items: center;",
    "    justify-content: flex-end;",
    "    padding-bottom: 25px;",
    "    margin-bottom: 25px;",
    "    box-shadow: 0 15px 45px rgba(0, 0, 0, 0.85);",
    "    border-bottom: 2px solid rgba(247, 147, 26, 0.4);",
    "}",
    ".matrix-unified {",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.55), rgba(4, 6, 9, 0.88)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');",
    "    background-position: center top;",
    "    background-size: cover;",
    "    border: 1px solid #2dd4bf;",
    "    border-radius: 18px;",
    "    padding: 16px 8px 18px 8px;",
    "    text-align: center;",
    "    margin-bottom: 18px;",
    "    box-shadow: 0 8px 35px rgba(0, 243, 255, 0.2);",
    "    position: relative;",
    "    overflow: hidden;",
    "}",
    ".matrix-grid {",
    "    display: grid;",
    "    grid-template-columns: 1.05fr 1.55fr 1.05fr;",
    "    gap: 8px;",
    "    align-items: stretch;",
    "}",
    ".thermo-card {",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.25), rgba(4, 6, 9, 0.65)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_vertical_futuristic_3D_cybernetic_glass_thermometer_gauge.jpg');",
    "    background-position: center center;",
    "    background-size: cover;",
    "    border: 1px solid rgba(0, 243, 255, 0.45);",
    "    border-radius: 14px;",
    "    padding: 10px 4px;",
    "    display: flex;",
    "    flex-direction: column;",
    "    justify-content: space-between;",
    "    align-items: center;",
    "    min-height: 350px;",
    "    box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.85), 0 0 15px rgba(0, 243, 255, 0.12);",
    "    position: relative;",
    "}",
    ".thermo-tube-wrap {",
    "    display: flex;",
    "    flex-direction: row;",
    "    align-items: center;",
    "    justify-content: center;",
    "    width: 100%;",
    "    height: 175px;",
    "    margin: 6px 0;",
    "    gap: 5px;",
    "}",
    ".thermo-scale {",
    "    display: flex;",
    "    flex-direction: column;",
    "    justify-content: space-between;",
    "    height: 100%;",
    "    font-family: 'Orbitron', sans-serif;",
    "    font-size: 8px;",
    "    font-weight: 800;",
    "    color: #cbd5e1;",
    "    text-align: right;",
    "    text-shadow: 0 1px 3px #000;",
    "}",
    ".thermo-glass {",
    "    width: 22px;",
    "    height: 100%;",
    "    background: rgba(4, 8, 15, 0.82);",
    "    border: 1.5px solid rgba(247, 147, 26, 0.65);",
    "    border-radius: 12px;",
    "    position: relative;",
    "    overflow: hidden;",
    "    box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.35), 0 0 10px rgba(247, 147, 26, 0.25);",
    "}",
    ".thermo-zero-line {",
    "    position: absolute;",
    "    top: 50%;",
    "    left: 0;",
    "    width: 100%;",
    "    height: 2px;",
    "    background: #ffffff;",
    "    z-index: 4;",
    "    box-shadow: 0 0 6px #00f3ff;",
    "}",
    "@keyframes plasma-pump {",
    "    0% { filter: brightness(1.0) drop-shadow(0 0 6px currentColor); }",
    "    50% { filter: brightness(1.45) drop-shadow(0 0 14px currentColor); }",
    "    100% { filter: brightness(1.0) drop-shadow(0 0 6px currentColor); }",
    "}",
    ".thermo-mercury-up {",
    "    position: absolute;",
    "    bottom: 50%;",
    "    left: 2px;",
    "    right: 2px;",
    "    background: linear-gradient(180deg, #00f3ff 0%, #3fb950 100%);",
    "    border-radius: 8px 8px 0 0;",
    "    color: #3fb950;",
    "    animation: plasma-pump 1.8s infinite ease-in-out;",
    "    z-index: 2;",
    "}",
    ".thermo-mercury-down {",
    "    position: absolute;",
    "    top: 50%;",
    "    left: 2px;",
    "    right: 2px;",
    "    background: linear-gradient(180deg, #f85149 0%, #ff0055 100%);",
    "    border-radius: 0 0 8px 8px;",
    "    color: #f85149;",
    "    animation: plasma-pump 1.8s infinite ease-in-out;",
    "    z-index: 2;",
    "}",
    ".liq-bumper-box {",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.35), rgba(4, 6, 9, 0.72)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_futuristic_3D_horizontal_HUD_target_bumper_frame_on_a_pitc.jpg');",
    "    background-position: center center;",
    "    background-size: cover;",
    "    border: 1.5px solid rgba(247, 147, 26, 0.65);",
    "    border-radius: 13px;",
    "    padding: 10px 6px;",
    "    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.85), inset 0 0 14px rgba(0, 243, 255, 0.18);",
    "}",
    ".matrix-live-price {",
    "    font-family: 'Orbitron', sans-serif;",
    "    font-size: 31px;",
    "    font-weight: 900;",
    "    color: #f0f6fc;",
    "    letter-spacing: 1px;",
    "    text-align: center;",
    "    padding: 10px 2px;",
    "    margin: 6px 0;",
    "    background: radial-gradient(circle, rgba(0, 243, 255, 0.14) 0%, rgba(4, 6, 9, 0.65) 80%);",
    "    border-top: 1px solid rgba(0, 243, 255, 0.35);",
    "    border-bottom: 1px solid rgba(0, 243, 255, 0.35);",
    "    border-radius: 10px;",
    "    text-shadow: 0 0 14px rgba(0, 243, 255, 0.65), 0 2px 6px rgba(0, 0, 0, 1);",
    "}",
    ".oi-center-box {",
    "    background: linear-gradient(180deg, rgba(10, 16, 28, 0.88), rgba(4, 6, 9, 0.95));",
    "    border: 1px solid rgba(0, 243, 255, 0.45);",
    "    border-radius: 12px;",
    "    padding: 8px 6px;",
    "    margin-top: 8px;",
    "    box-shadow: inset 0 0 12px rgba(0, 243, 255, 0.15);",
    "}",
    ".oi-bar-track {",
    "    width: 100%;",
    "    height: 10px;",
    "    background: rgba(4, 8, 15, 0.9);",
    "    border: 1px solid rgba(247, 147, 26, 0.5);",
    "    border-radius: 6px;",
    "    position: relative;",
    "    overflow: hidden;",
    "    margin: 5px 0;",
    "}",
    ".setups-container {",
    "    background-image: linear-gradient(rgba(4, 6, 9, 0.75), rgba(4, 6, 9, 0.92)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');",
    "    background-position: center bottom;",
    "    background-size: cover;",
    "    border: 1px solid #2dd4bf;",
    "    border-radius: 16px;",
    "    padding: 15px;",
    "    margin-bottom: 18px;",
    "    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.8);",
    "}",
    ".alert-box {",
    "    background: rgba(13, 19, 31, 0.35);",
    "    border: 1px solid rgba(31, 41, 55, 0.6);",
    "    padding: 14px;",
    "    border-radius: 15px;",
    "    margin-bottom: 12px;",
    "    backdrop-filter: blur(1px);",
    "    min-height: 125px;",
    "    display: flex;",
    "    flex-direction: column;",
    "    justify-content: center;",
    "    text-align: center;",
    "}",
    ".signal-triggered {",
    "    background-color: rgba(35, 12, 16, 0.55) !important;",
    "    border: 2px solid #f85149 !important;",
    "    animation: pulse-alert 1s infinite alternate;",
    "}",
    "@keyframes pulse-alert { 0% { box-shadow: 0 0 10px rgba(248, 81, 73, 0.4); } 100% { box-shadow: 0 0 30px rgba(248, 81, 73, 0.9); } }",
    ".money-journal {",
    "    background-image: linear-gradient(rgba(2, 10, 5, 0.3), rgba(2, 10, 5, 0.6)), url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_neat_pile_of_crisp_US_dolla.jpg');",
    "    background-position: center;",
    "    background-size: cover;",
    "    border-radius: 15px;",
    "    padding: 26px 20px;",
    "    text-align: center;",
    "    margin-bottom: 18px;",
    "    box-shadow: 0 10px 40px rgba(39, 174, 96, 0.4);",
    "    border: 1px solid #1f7a43;",
    "}",
    ".money-content { position: relative; z-index: 2; display: flex; justify-content: space-around; align-items: center; }",
    "div.stButton > button { width: 100%; background: rgba(17, 24, 39, 0.85); color: #f0f6fc !important; border: 1px solid #374151 !important; border-radius: 10px; padding: 14px; font-size: 15px !important; font-weight: 900 !important; margin-bottom: 10px; }",
    "div.stButton > button:hover { border-color: #00f3ff !important; color: #00f3ff !important; }",
    "</style>"
])
st.markdown(css_styles, unsafe_allow_html=True)

def get_prague_now():
    try:
        return datetime.now(ZoneInfo("Europe/Prague"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=1)))

def check_liquid_hours():
    now_p = get_prague_now()
    try:
        cutoff_24_7 = datetime(2026, 11, 20, 13, 59, 59, tzinfo=now_p.tzinfo)
        if now_p <= cutoff_24_7:
            return True, f"🟢 24/7 TÝDENNÍ SBĚR DAT AKTIVNÍ ({now_p.strftime('%d.%m. %H:%M')}) | Do 20.11. 13:59 (před NY Open)"
    except Exception:
        return True, f"🟢 24/7 TÝDENNÍ SBĚR DAT AKTIVNÍ ({now_p.strftime('%H:%M')})"

    if now_p.weekday() >= 5:
        return False, f"⏸️ VÍKENDOVÝ REŽIM ({now_p.strftime('%H:%M')}) – Alarmy vypnuty"

    mins = now_p.hour * 60 + now_p.minute
    in_asia = (2 * 60) <= mins < (5 * 60)
    in_london = (9 * 60) <= mins <= (10 * 60 + 30)
    in_ny = (14 * 60) <= mins < (19 * 60)

    if in_asia or in_london or in_ny:
        return True, f"🟢 LIKVIDNÍ OKNO AKTIVNÍ ({now_p.strftime('%H:%M')}) | Top-Down S1 (Macro/Med/Micro) + 100% Maker"
    return False, f"⏸️ MIMO LIKVIDNÍ HODINY ({now_p.strftime('%H:%M')}) – Alarmy v pohotovosti"

@st.cache_data(ttl=30)
def load_trading_data():
    try:
        sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url, header=None)
        row_summary = df.iloc[17]
        pnl_raw = str(row_summary.iloc[2])
        pnl_clean = pnl_raw.replace("$", "").replace("€", "").replace(" ", "").replace(",", ".")
        total_pnl = float(pnl_clean) if pnl_clean.lower() not in ["nan", "0", "0.0", ""] else 0.0
        win_raw = str(row_summary.iloc[6])
        win_clean = win_raw.replace("%", "").replace(" ", "").replace(",", ".")
        win_rate = float(win_clean) if win_clean.lower() not in ["nan", "0", "0.0", ""] else 0.0
        return total_pnl, win_rate
    except Exception:
        return 0.0, 0.0

def get_okx_candles(bar, limit, ts, inst_priority=None):
    if inst_priority is None:
        inst_priority = ["BTC-USD_UM_XPERP-310404", "BTC-USDT-SWAP", "BTC-USD-SWAP"]
    for inst in inst_priority:
        hosts = ["https://www.okx.com", "https://eea.okx.com"] if "USDT" in inst else ["https://eea.okx.com", "https://www.okx.com"]
        for host in hosts:
            try:
                u = f"{host}/api/v5/market/candles?instId={inst}&bar={bar}&limit={limit}&t={ts}"
                data = requests.get(u, timeout=4).json().get("data", [])
                if data:
                    return data
            except Exception:
                continue
    return []

def get_live_xperp_price(fallback_price, ts):
    for host in ["https://eea.okx.com", "https://www.okx.com"]:
        try:
            u = f"{host}/api/v5/market/ticker?instId=BTC-USD_UM_XPERP-310404&t={ts}"
            data = requests.get(u, timeout=3).json().get("data", [])
            if data and data[0].get("last"):
                return float(data[0]["last"])
        except Exception:
            continue
    return fallback_price

def poll_realtime_okx_flow():
    ts = int(time.time() * 1000)
    curr_5m_open = (ts // 300000) * 300000

    try:
        u_fut = f"https://www.okx.com/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=500&t={ts}"
        trades_f = requests.get(u_fut, timeout=3).json().get("data", [])
        if trades_f:
            with ENGINE["lock"]:
                last_id = ENGINE["last_fut_trade_id"]
                new_trades = []
                for tr in trades_f:
                    tid = str(tr.get("tradeId", ""))
                    if last_id is not None and tid == last_id:
                        break
                    new_trades.append(tr)
                ENGINE["last_fut_trade_id"] = str(trades_f[0].get("tradeId", ""))

                for tr in reversed(new_trades):
                    t_ts = int(tr["ts"])
                    bucket_5m = (t_ts // 300000) * 300000
                    bucket_1m = (t_ts // 60000) * 60000
                    vol_btc = float(tr["sz"]) * 0.01
                    delta = vol_btc if tr.get("side") == "buy" else -vol_btc
                    ENGINE["fut_buckets"][bucket_5m] = ENGINE["fut_buckets"].get(bucket_5m, 0.0) + delta
                    ENGINE["fut_1m_buckets"][bucket_1m] = ENGINE["fut_1m_buckets"].get(bucket_1m, 0.0) + delta
    except Exception:
        pass

    try:
        u_spot = f"https://www.okx.com/api/v5/market/trades?instId=BTC-USDT&limit=500&t={ts}"
        trades_s = requests.get(u_spot, timeout=3).json().get("data", [])
        if trades_s:
            with ENGINE["lock"]:
                last_s_id = ENGINE["last_spot_trade_id"]
                new_s_trades = []
                for tr in trades_s:
                    tid = str(tr.get("tradeId", ""))
                    if last_s_id is not None and tid == last_s_id:
                        break
                    new_s_trades.append(tr)
                ENGINE["last_spot_trade_id"] = str(trades_s[0].get("tradeId", ""))

                for tr in reversed(new_s_trades):
                    t_ts = int(tr["ts"])
                    bucket_5m = (t_ts // 300000) * 300000
                    bucket_1m = (t_ts // 60000) * 60000
                    vol_btc = float(tr["sz"])
                    delta = vol_btc if tr.get("side") == "buy" else -vol_btc
                    ENGINE["spot_buckets"][bucket_5m] = ENGINE["spot_buckets"].get(bucket_5m, 0.0) + delta
                    ENGINE["spot_1m_buckets"][bucket_1m] = ENGINE["spot_1m_buckets"].get(bucket_1m, 0.0) + delta
    except Exception:
        pass

    try:
        u_oi = f"https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP&t={ts}"
        oi_data = requests.get(u_oi, timeout=3).json().get("data", [])
        if oi_data and oi_data[0].get("oiCcy"):
            live_oi_btc = float(oi_data[0]["oiCcy"])
            with ENGINE["lock"]:
                if curr_5m_open not in ENGINE["oi_start_map"]:
                    base_oi = ENGINE["last_oi_btc"] if ENGINE["last_oi_btc"] is not None else live_oi_btc
                    ENGINE["oi_start_map"][curr_5m_open] = base_oi
                ENGINE["last_oi_btc"] = live_oi_btc
                ENGINE["oi_live_delta"][curr_5m_open] = live_oi_btc - ENGINE["oi_start_map"][curr_5m_open]
    except Exception:
        pass

# === KONEC ČÁSTI 1 ===# === ZAČÁTEK ČÁSTI 2 ===

def compute_anchored_1m_map(candles_1m, map_5m, is_spot=False):
    with ENGINE["lock"]:
        b_1m_src = dict(ENGINE["spot_1m_buckets"] if is_spot else ENGINE["fut_1m_buckets"])

    groups = {}
    for m in candles_1m:
        try:
            m_ts = int(m[0])
            b5 = (m_ts // 300000) * 300000
            vol_btc = float(m[5]) if is_spot else float(m[6])
            groups.setdefault(b5, []).append((m_ts, max(vol_btc, 0.0001)))
        except Exception:
            continue

    anchored = {}
    for b5, items in groups.items():
        real_vals = [b_1m_src.get(t, 0.0) for t, _ in items]
        if map_5m and (b5 in map_5m):
            official_5m = float(map_5m[b5])
            total_vol = sum(v for _, v in items)
            if any(abs(x) > 0.0 for x in real_vals):
                diff = official_5m - sum(real_vals)
                for (t, v), r_val in zip(items, real_vals):
                    anchored[t] = r_val + diff * (v / total_vol)
            else:
                for t, v in items:
                    anchored[t] = official_5m * (v / total_vol)
        else:
            for (t, _), r_val in zip(items, real_vals):
                anchored[t] = r_val
    return anchored

def compute_single_1m_delta(m_candle, is_spot=False, anchored_map=None):
    m_ts = int(m_candle[0])
    if anchored_map is not None and m_ts in anchored_map:
        return anchored_map[m_ts]
    with ENGINE["lock"]:
        b_map = ENGINE["spot_1m_buckets"] if is_spot else ENGINE["fut_1m_buckets"]
        return b_map.get(m_ts, 0.0)

def get_1m_extreme_ts(c_1m_list, start_ts, end_ts, is_high):
    extreme_val = -1.0 if is_high else float("inf")
    extreme_ts = start_ts
    for m in c_1m_list:
        t = int(m[0])
        if start_ts <= t < end_ts:
            val = float(m[2]) if is_high else float(m[3])
            if is_high and val > extreme_val:
                extreme_val, extreme_ts = val, t
            elif not is_high and val < extreme_val:
                extreme_val, extreme_ts = val, t
    return extreme_ts

def get_cum_val_at_ts(cum_map, target_ts):
    if target_ts in cum_map:
        return cum_map[target_ts]
    prior_keys = [k for k in cum_map.keys() if k <= target_ts]
    if prior_keys:
        return cum_map[max(prior_keys)]
    all_keys = sorted(cum_map.keys())
    return cum_map[all_keys[0]] if all_keys else 0.0

def get_1m_real_or_calibrated_delta(candles_1m, candle_open_ts, is_spot=False):
    with ENGINE["lock"]:
        bucket_map = ENGINE["spot_buckets"] if is_spot else ENGINE["fut_buckets"]
        real_collected = bucket_map.get(candle_open_ts, 0.0)
        b_1m_map = ENGINE["spot_1m_buckets"] if is_spot else ENGINE["fut_1m_buckets"]
        sum_1m = sum(
            v for k, v in b_1m_map.items()
            if candle_open_ts <= k < candle_open_ts + 300000
        )
    if abs(real_collected) > 0.0:
        return real_collected
    return sum_1m

def compute_1h_trend_info(candles_1h, btc_price):
    try:
        if not candles_1h or len(candles_1h) < 6:
            return "NEUTRAL (0.00%)"
        c_asc = candles_1h[:12][::-1]
        closes = [float(c[4]) for c in c_asc]
        ema_fast = sum(closes[-4:]) / 4.0
        ema_slow = sum(closes) / len(closes)
        diff_pct = ((btc_price - ema_slow) / ema_slow) * 100.0 if ema_slow > 0 else 0.0
        if btc_price > ema_fast > ema_slow:
            return f"BULLISH ({diff_pct:+.2f}%)"
        elif btc_price < ema_fast < ema_slow:
            return f"BEARISH ({diff_pct:+.2f}%)"
        return f"RANGING ({diff_pct:+.2f}%)"
    except Exception:
        return "NEUTRAL"

# --- EXEKUČNÍ ENGINE SETUPU 1: BOD A (T_confirm) -> BOD B (1M FUTURES CVD BREAK) -> BOD C (DYNAMICKÝ PULLBACK 0.18% / 0.12% / 0.08%) ---
def evaluate_setup1_1m_entry(direction, confirm_1m_ts, c1f, btc_price, upper_p, lower_p, setup_label, fut_map=None, pb_pct=0.0012, sl_pct=0.0030, tp_mode="SPLIT_50_50"):
    mf = c1f[:60][::-1] if len(c1f) >= 60 else c1f[::-1]

    if len(mf) < 10:
        pl = build_trade_plan(direction, btc_price, upper_p, lower_p, setup_label, sl_pct=sl_pct, tp_mode=tp_mode)
        return False, "⏳ Čekám na 1M data...", pl

    n = len(mf)
    anch_f = compute_anchored_1m_map(mf, fut_map, is_spot=False)

    cf, rf = [], 0.0
    ts_list, o1, h1, l1, c1 = [], [], [], [], []

    for i in range(n):
        rf += compute_single_1m_delta(mf[i], is_spot=False, anchored_map=anch_f)
        cf.append(rf)
        ts_list.append(int(mf[i][0]))
        o1.append(float(mf[i][1]))
        h1.append(float(mf[i][2]))
        l1.append(float(mf[i][3]))
        c1.append(float(mf[i][4]))

    c1[-1] = btc_price
    h1[-1] = max(h1[-1], btc_price)
    l1[-1] = min(l1[-1], btc_price)

    c_idx = 3
    for idx, t_val in enumerate(ts_list):
        if t_val <= confirm_1m_ts:
            c_idx = idx
    c_idx = max(3, min(c_idx, n - 1))

    def _track_dynamic_1m_cvd_break(series, is_bullish):
        lookback_start = max(1, c_idx - 10)
        ref_level = None

        for k in range(c_idx - 1, lookback_start - 1, -1):
            if is_bullish:
                if series[k] >= series[k - 1] and series[k] >= series[k + 1]:
                    ref_level = series[k]
                    break
            else:
                if series[k] <= series[k - 1] and series[k] <= series[k + 1]:
                    ref_level = series[k]
                    break

        if ref_level is None:
            pre_slice = series[max(0, c_idx - 6):c_idx + 1]
            ref_level = max(pre_slice) if is_bullish else min(pre_slice)

        for k in range(c_idx + 1, n):
            if is_bullish:
                if series[k] > ref_level:
                    return True, k, ref_level
                if (k - 1) > c_idx and series[k - 1] > series[k - 2] and series[k] < series[k - 1]:
                    ref_level = series[k - 1]
            else:
                if series[k] < ref_level:
                    return True, k, ref_level
                if (k - 1) > c_idx and series[k - 1] < series[k - 2] and series[k] > series[k - 1]:
                    ref_level = series[k - 1]

        return False, -1, ref_level

    trg = False
    txt = ""
    plan_entry = btc_price
    confirm_dt_str = datetime.fromtimestamp(confirm_1m_ts / 1000, get_prague_now().tzinfo).strftime("%H:%M")

    if direction == "SHORT":
        f_ok, f_brk_idx, _ = _track_dynamic_1m_cvd_break(cf, is_bullish=False)

        if f_ok:
            trough_p = min(l1[f_brk_idx:])
            lmt_p = trough_p * (1.0 + pb_pct)
            plan_entry = lmt_p
            if btc_price >= lmt_p or (f_brk_idx + 1 < n and max(h1[f_brk_idx + 1:]) >= lmt_p):
                trg = True
                plan_entry = max(btc_price, lmt_p)
                txt = f"✅ MAKER SHORT AKTIVOVÁN (Potvrzeno {confirm_dt_str} -> 1M CVD LL + PB {pb_pct*100:.2f}%) | Vstup: {plan_entry:.0f}$"
            else:
                txt = f"⏳ Bod B splněn (1M CVD LL po {confirm_dt_str}) – čekám na Bod C ({pb_pct*100:.2f}% PB nahoru na {lmt_p:.0f}$)"
        else:
            txt = f"⏳ Bod A uzamčen ({confirm_dt_str}) – čekám na Bod B (průraz 1M Futures CVD Low po {confirm_dt_str})"
    else:
        f_ok, f_brk_idx, _ = _track_dynamic_1m_cvd_break(cf, is_bullish=True)

        if f_ok:
            peak_p = max(h1[f_brk_idx:])
            lmt_p = peak_p * (1.0 - pb_pct)
            plan_entry = lmt_p
            if btc_price <= lmt_p or (f_brk_idx + 1 < n and min(l1[f_brk_idx + 1:]) <= lmt_p):
                trg = True
                plan_entry = min(btc_price, lmt_p)
                txt = f"✅ MAKER LONG AKTIVOVÁN (Potvrzeno {confirm_dt_str} -> 1M CVD HH + PB {pb_pct*100:.2f}%) | Vstup: {plan_entry:.0f}$"
            else:
                txt = f"⏳ Bod B splněn (1M CVD HH po {confirm_dt_str}) – čekám na Bod C ({pb_pct*100:.2f}% PB dolů na {lmt_p:.0f}$)"
        else:
            txt = f"⏳ Bod A uzamčen ({confirm_dt_str}) – čekám na Bod B (průraz 1M Futures CVD High po {confirm_dt_str})"

    pl = build_trade_plan(direction, plan_entry, upper_p, lower_p, setup_label, sl_pct=sl_pct, tp_mode=tp_mode)
    pl["trigger_ready"] = trg

    if tp_mode == "FULL_LIQ":
        tp_info_str = f"Maker TP (100% Liq): {pl['tp2_limit_50pct']:.0f}$"
    elif tp_mode == "HALF_LIQ":
        tp_info_str = f"Maker TP (100% 1/2 Liq): {pl['tp1_limit_50pct']:.0f}$"
    else:
        tp_info_str = f"Maker TP1 (50%): {pl['tp1_limit_50pct']:.0f}$ | Maker TP2 (50%): {pl['tp2_limit_50pct']:.0f}$"

    txt += f" | SL ({sl_pct*100:.2f}% Mkt): {pl['sl_market']:.0f}$ | {tp_info_str}"
    return trg, txt, pl

def compute_liquidation_magnets(c_300, oi_change_map, btc_price):
    curr_5m_candle = (int(time.time() * 1000) // 300000) * 300000
    with ENGINE["lock"]:
        cache = ENGINE["liq_cache"]
        if (cache["candle_ts"] == curr_5m_candle and
            cache["upper_p"] > btc_price + 30.0 and
            0 < cache["lower_p"] < btc_price - 30.0):
            return cache["upper_p"], cache["upper_btc"], cache["lower_p"], cache["lower_btc"]

    min_up = btc_price * 1.002
    max_up = btc_price * 1.020
    min_down = btc_price * 0.980
    max_down = btc_price * 0.998

    short_clusters = {}
    long_clusters = {}

    recent_desc = c_300[:144] if len(c_300) >= 144 else c_300
    recent_asc = recent_desc[::-1]
    n_c = len(recent_asc)

    highs_asc = [float(c[2]) for c in recent_asc]
    lows_asc = [float(c[3]) for c in recent_asc]

    for idx, c in enumerate(recent_asc):
        try:
            c_ts = int(c[0])
            h, l = float(c[2]), float(c[3])
            vol_btc = float(c[6]) if len(c) > 6 and float(c[6]) > 0 else float(c[5])
            oi_ch = oi_change_map.get(c_ts, 0.0)

            pos_weight = max(oi_ch, 0.0) * 1.6 + (vol_btc * 0.14)
            if pos_weight <= 0:
                continue

            max_h_after = max(highs_asc[idx + 1:]) if (idx + 1) < n_c else h
            min_l_after = min(lows_asc[idx + 1:]) if (idx + 1) < n_c else l

            for lev_mult, share in [(1.0085, 0.40), (1.0125, 0.35), (1.0175, 0.25)]:
                liq_s = round((h * lev_mult) / 25.0) * 25.0
                if liq_s > max_h_after and min_up <= liq_s <= max_up:
                    short_clusters[liq_s] = short_clusters.get(liq_s, 0.0) + (pos_weight * share)

            for lev_mult, share in [(0.9915, 0.40), (0.9875, 0.35), (0.9825, 0.25)]:
                liq_l = round((l * lev_mult) / 25.0) * 25.0
                if liq_l < min_l_after and min_down <= liq_l <= max_down:
                    long_clusters[liq_l] = long_clusters.get(liq_l, 0.0) + (pos_weight * share)
        except Exception:
            continue

    if short_clusters:
        upper_p = max(short_clusters, key=short_clusters.get)
        upper_btc = short_clusters[upper_p]
    else:
        upper_p = round((btc_price * 1.012) / 25.0) * 25.0
        upper_btc = 85.0

    if long_clusters:
        lower_p = max(long_clusters, key=long_clusters.get)
        lower_btc = long_clusters[lower_p]
    else:
        lower_p = round((btc_price * 0.988) / 25.0) * 25.0
        lower_btc = 92.0

    with ENGINE["lock"]:
        ENGINE["liq_cache"] = {
            "candle_ts": curr_5m_candle,
            "upper_p": upper_p,
            "upper_btc": upper_btc,
            "lower_p": lower_p,
            "lower_btc": lower_btc
        }

    return upper_p, upper_btc, lower_p, lower_btc

def compute_1h_volume_profile(candles_1m_vp, c_12_asc):
    source_candles = candles_1m_vp[:60] if len(candles_1m_vp) >= 30 else c_12_asc
    if not source_candles:
        return 0.0, 0.0, 0.0

    lows = [float(c[3]) for c in source_candles]
    highs = [float(c[2]) for c in source_candles]
    min_p, max_p = min(lows), max(highs)
    if max_p <= min_p:
        return min_p, max_p, min_p

    num_bins = 24
    bin_size = (max_p - min_p) / num_bins
    bins = [0.0] * num_bins
    bin_centers = [min_p + (i + 0.5) * bin_size for i in range(num_bins)]

    for c in source_candles:
        h, l = float(c[2]), float(c[3])
        vol = float(c[6]) if len(c) > 6 and float(c[6]) > 0 else float(c[5])
        if vol <= 0:
            vol = 1.0
        start_b = max(0, min(num_bins - 1, int((l - min_p) / bin_size)))
        end_b = max(0, min(num_bins - 1, int((h - min_p) / bin_size)))
        span = (end_b - start_b) + 1
        vol_per_bin = vol / span
        for b_idx in range(start_b, end_b + 1):
            bins[b_idx] += vol_per_bin

    total_vol = sum(bins)
    if total_vol <= 0:
        return bin_centers[num_bins // 2], max_p, min_p

    poc_idx = max(range(num_bins), key=lambda i: bins[i])
    poc_price = bin_centers[poc_idx]

    target_vol = total_vol * 0.70
    curr_vol = bins[poc_idx]
    low_idx, high_idx = poc_idx, poc_idx

    while curr_vol < target_vol and (low_idx > 0 or high_idx < num_bins - 1):
        up_vol = bins[high_idx + 1] if high_idx < num_bins - 1 else -1.0
        down_vol = bins[low_idx - 1] if low_idx > 0 else -1.0
        if up_vol >= down_vol:
            high_idx += 1
            curr_vol += bins[high_idx]
        else:
            low_idx -= 1
            curr_vol += bins[low_idx]

    vah_price = bin_centers[high_idx] + (bin_size * 0.5)
    val_price = bin_centers[low_idx] - (bin_size * 0.5)
    return poc_price, vah_price, val_price

def fetch_okx_data():
    poll_realtime_okx_flow()
    ts = int(time.time() * 1000)
    try:
        candles_300 = get_okx_candles("5m", 300, ts, ["BTC-USD_UM_XPERP-310404", "BTC-USDT-SWAP"])
        fallback_p = float(candles_300[0][4]) if candles_300 else 75000.0
        btc_price = get_live_xperp_price(fallback_p, ts)
        candles_1h = get_okx_candles("1H", 72, ts, ["BTC-USD_UM_XPERP-310404", "BTC-USDT-SWAP"])

        if candles_300:
            candles_300[0] = list(candles_300[0])
            candles_300[0][4] = str(btc_price)
            if btc_price > float(candles_300[0][2]):
                candles_300[0][2] = str(btc_price)
            if btc_price < float(candles_300[0][3]):
                candles_300[0][3] = str(btc_price)

        c_12_desc = [list(c) for c in candles_300[0:12]] if len(candles_300) >= 12 else [list(c) for c in candles_300]
        c_12_asc = c_12_desc[::-1]
        candle_close_map = {int(c[0]): float(c[4]) for c in candles_300}

        vol_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&limit=100&t={ts}", timeout=5).json().get("data", [])
        fut_map = {}
        for row in vol_res:
            try:
                open_ts = int(row[0]) - 300000
                sell_usd, buy_usd = float(row[1]), float(row[2])
                ref_p = candle_close_map.get(open_ts, btc_price)
                fut_map[open_ts] = (buy_usd - sell_usd) / ref_p if ref_p > 0 else 0.0
            except Exception:
                continue

        spot_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SPOT&period=5m&limit=100&t={ts}", timeout=5).json().get("data", [])
        spot_map = {}
        for row in spot_res:
            try:
                open_ts = int(row[0]) - 300000
                spot_map[open_ts] = float(row[2]) - float(row[1])
            except Exception:
                continue

        candles_1m_fut = get_okx_candles("1m", 120, ts, ["BTC-USDT-SWAP", "BTC-USD_UM_XPERP-310404"])
        candles_1m_spot = get_okx_candles("1m", 120, ts, ["BTC-USDT"])

        live_open_ts = int(c_12_asc[-1][0]) if c_12_asc else 0
        if live_open_ts > 0:
            fut_map[live_open_ts] = get_1m_real_or_calibrated_delta(candles_1m_fut, live_open_ts, is_spot=False)
            spot_map[live_open_ts] = get_1m_real_or_calibrated_delta(candles_1m_spot, live_open_ts, is_spot=True)

        cvd_12, scvd_12 = [], []
        for idx, c in enumerate(c_12_asc):
            open_ts = int(c[0])
            cvd_12.append(fut_map.get(open_ts, 0.0))
            scvd_12.append(spot_map.get(open_ts, 0.0))

        oi_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&limit=100&t={ts}", timeout=5).json().get("data", [])
        oi_change_map = {}
        if len(oi_res) >= 2:
            for idx in range(len(oi_res) - 1):
                try:
                    ts_curr, val_curr = int(oi_res[idx][0]), float(oi_res[idx][1])
                    ts_prev, val_prev = int(oi_res[idx + 1][0]), float(oi_res[idx + 1][1])
                    open_curr = ts_curr - 300000
                    open_prev = ts_prev - 300000
                    p_curr = candle_close_map.get(open_curr, btc_price)
                    p_prev = candle_close_map.get(open_prev, btc_price)
                    if p_curr > 0 and p_prev > 0 and val_curr > 0 and val_prev > 0:
                        oi_change_map[open_curr] = (val_curr / p_curr) - (val_prev / p_prev)
                except Exception:
                    continue

        with ENGINE["lock"]:
            for k_ts, v_oi in ENGINE["oi_live_delta"].items():
                if k_ts not in oi_change_map or k_ts == live_open_ts:
                    oi_change_map[k_ts] = v_oi

        oi_12 = [oi_change_map.get(int(c[0]), 0.0) for c in c_12_asc]

        vp_data = compute_1h_volume_profile(candles_1m_fut, c_12_asc)
        liq_data = compute_liquidation_magnets(candles_300, oi_change_map, btc_price)

        cvd_1 = sum(cvd_12[-1:]) if len(cvd_12) >= 1 else 0.0
        cvd_5 = sum(cvd_12[-5:]) if len(cvd_12) >= 5 else 0.0
        cvd_9 = sum(cvd_12[-9:]) if len(cvd_12) >= 9 else 0.0

        scvd_1 = sum(scvd_12[-1:]) if len(scvd_12) >= 1 else 0.0
        scvd_5 = sum(scvd_12[-5:]) if len(scvd_12) >= 5 else 0.0
        scvd_9 = sum(scvd_12[-9:]) if len(scvd_12) >= 9 else 0.0

        oi_1 = sum(oi_12[-1:]) if len(oi_12) >= 1 else 0.0
        oi_5 = sum(oi_12[-5:]) if len(oi_12) >= 5 else 0.0
        oi_9 = sum(oi_12[-9:]) if len(oi_12) >= 9 else 0.0

        return (cvd_1, cvd_5, cvd_9, scvd_1, scvd_5, scvd_9, oi_1, oi_5, oi_9,
                cvd_12, scvd_12, c_12_asc, candles_300, candles_1h, fut_map, spot_map, oi_change_map,
                btc_price, vp_data, liq_data, candles_1m_fut, candles_1m_spot)
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                [], [], [], [], [], {}, {}, {}, 75000.0, (0.0, 0.0, 0.0), (74500.0, 95.0, 72500.0, 95.0), [], [])

# --- SETUP 1: TOP-DOWN 3 SKUPINY (MACRO 60-180M ≤0.45% | MEDIUM 30-90M ≤0.30% | MICRO 15-45M ≤0.15% | BODY-TO-BODY | POUZE FUTURES CVD) ---
def scan_setup_1(candles_300, candles_1h, liquid_ok, candles_1m_fut, btc_price, upper_p, lower_p, fut_map, spot_map, vp_data, flow_metrics):
    try:
        rem_s1 = get_setup_cooldown_remaining("S1_LOCK_1H", 3600)
        if rem_s1 > 0:
            with ENGINE["lock"]:
                ENGINE["s1_memory"]["active"] = False
            return f"🔒 Setup 1 uzamčen na 1H (zbývá {rem_s1 // 60 + 1} min) | Setup 2 povolen.", False

        if len(candles_300) < 36:
            return "Načítám Top-Down 15M–180M strukturu svíček...", False

        now_sec = time.time()
        with ENGINE["lock"]:
            mem = ENGINE["s1_memory"]
            if mem["active"]:
                if (now_sec - mem["locked_at_sec"]) > S1_MEMORY_TTL_SEC:
                    mem["active"] = False
                elif mem["direction"] == "SHORT" and btc_price > mem["zone_extreme_p"] * 1.0018:
                    mem["active"] = False
                elif mem["direction"] == "LONG" and btc_price < mem["zone_extreme_p"] * 0.9982:
                    mem["active"] = False

        c_36_desc = [list(c) for c in candles_300[:36]]
        c_36_asc = c_36_desc[::-1]

        opens_36 = [float(c[1]) for c in c_36_asc]
        highs_36 = [float(c[2]) for c in c_36_asc]
        lows_36 = [float(c[3]) for c in c_36_asc]
        closes_36 = [float(c[4]) for c in c_36_asc]
        body_highs_36 = [max(opens_36[i], closes_36[i]) for i in range(36)]
        body_lows_36 = [min(opens_36[i], closes_36[i]) for i in range(36)]
        ts_36 = [int(c[0]) for c in c_36_asc]

        prefix = "" if liquid_ok else "⏸️ "

        # Definice 3 Top-Down skupin:
        # (group_id, min_bars, max_bars, max_body_spread_pct, min_touches, min_cvd_btc, pb_pct, sl_pct, tp_mode)
        groups_cfg = [
            ("MACRO",  12, 36, 0.45, 3, 250.0, 0.0018, 0.0030, "FULL_LIQ"),
            ("MEDIUM",  6, 18, 0.30, 2, 100.0, 0.0012, 0.0020, "SPLIT_50_50"),
            ("MICRO",   3,  9, 0.15, 1,  50.0, 0.0008, 0.0010, "HALF_LIQ")
        ]

        detected_dir = None
        detected_group = ""
        detected_label = ""
        detected_header = ""
        detected_confirm_ts = 0
        detected_zone_p = 0.0
        detected_pb = 0.0012
        detected_sl = 0.0020
        detected_tp_mode = "SPLIT_50_50"
        detected_mins = 0
        detected_spread = 0.0
        detected_cvd = 0.0
        detected_spot = 0.0

        status_summaries = []

        for g_name, min_b, max_b, max_spr, req_touches, req_cvd, g_pb, g_sl, g_tp_mode in groups_cfg:
            # 1. Nalezení nejdelšího souvislého Body-to-Body úseku od přítomnosti dozadu v rámci dané skupiny
            max_valid_k = 0
            for k in range(min_b, max_b + 1):
                b_mx = max(body_highs_36[-k:])
                b_mn = min(body_lows_36[-k:])
                spr = ((b_mx - b_mn) / b_mn) * 100.0 if b_mn > 0 else 99.0
                if spr <= max_spr:
                    max_valid_k = k
                else:
                    if k == min_b:
                        max_valid_k = 0
                    break

            if max_valid_k < min_b:
                base_mx = max(body_highs_36[-min_b:])
                base_mn = min(body_lows_36[-min_b:])
                base_spr = ((base_mx - base_mn) / max(base_mn, 1.0)) * 100.0
                status_summaries.append(f"{g_name}: {min_b*5}M těla {base_spr:.2f}% > {max_spr:.2f}%")
                continue

            # Testujeme od nejdelšího platného úseku max_valid_k směrem k min_b
            for k_test in range(max_valid_k, min_b - 1, -1):
                sub_bh = body_highs_36[-k_test:]
                sub_bl = body_lows_36[-k_test:]
                sub_h = highs_36[-k_test:]
                sub_l = lows_36[-k_test:]
                sub_c = closes_36[-k_test:]
                sub_ts = ts_36[-k_test:]

                box_max_b = max(sub_bh)
                box_min_b = min(sub_bl)
                box_height = max(box_max_b - box_min_b, 1.0)
                box_mid = (box_max_b + box_min_b) / 2.0
                box_spr_pct = (box_height / box_min_b) * 100.0 if box_min_b > 0 else 0.0

                # Kontrola vodorovné krabice (zákaz jednosměrného šikmého trendu)
                half_k = max(1, k_test // 2)
                mean_first = sum(sub_c[:half_k]) / half_k
                mean_second = sum(sub_c[half_k:]) / max(1, k_test - half_k)
                slope_diff_pct = (abs(mean_second - mean_first) / box_min_b) * 100.0 if box_min_b > 0 else 0.0
                is_flat_box = (slope_diff_pct <= (max_spr * 0.70))

                # Čisté CVD uvnitř krabice (ošetření příjezdové svíčky na začátku boxu)
                cvd_all = sum(fut_map.get(t_o, 0.0) for t_o in sub_ts)
                cvd_no_first = sum(fut_map.get(t_o, 0.0) for t_o in sub_ts[1:]) if k_test > 3 else cvd_all
                box_cvd_short = max(cvd_all, cvd_no_first)
                box_cvd_long = min(cvd_all, cvd_no_first)
                box_spot_val = sum(spot_map.get(t_o, 0.0) for t_o in sub_ts)

                # Počet oddělených otestů horní hrany (horních 25 % Body-to-Body krabice)
                top_floor = box_max_b - (box_height * 0.25)
                top_reset = box_max_b - (box_height * 0.35)
                upper_touches = []
                in_top_touch = False
                best_top_idx = 0
                for idx_b in range(k_test):
                    if sub_h[idx_b] >= top_floor or sub_bh[idx_b] >= top_floor:
                        if not in_top_touch:
                            in_top_touch = True
                            best_top_idx = idx_b
                        elif sub_h[idx_b] > sub_h[best_top_idx]:
                            best_top_idx = idx_b
                    elif sub_l[idx_b] <= top_reset or sub_c[idx_b] <= top_reset:
                        if in_top_touch:
                            upper_touches.append(best_top_idx)
                            in_top_touch = False
                if in_top_touch:
                    upper_touches.append(best_top_idx)

                # Počet oddělených otestů spodní hrany (spodních 25 % Body-to-Body krabice)
                bot_ceil = box_min_b + (box_height * 0.25)
                bot_reset = box_min_b + (box_height * 0.35)
                lower_touches = []
                in_bot_touch = False
                best_bot_idx = 0
                for idx_b in range(k_test):
                    if sub_l[idx_b] <= bot_ceil or sub_bl[idx_b] <= bot_ceil:
                        if not in_bot_touch:
                            in_bot_touch = True
                            best_bot_idx = idx_b
                        elif sub_l[idx_b] < sub_l[best_bot_idx]:
                            best_bot_idx = idx_b
                    elif sub_h[idx_b] >= bot_reset or sub_c[idx_b] >= bot_reset:
                        if in_bot_touch:
                            lower_touches.append(best_bot_idx)
                            in_bot_touch = False
                if in_bot_touch:
                    lower_touches.append(best_bot_idx)

                in_upper_half = (btc_price >= box_mid)
                in_lower_half = (btc_price <= box_mid)

                if k_test == max_valid_k:
                    best_abs_cvd = box_cvd_short if abs(box_cvd_short) >= abs(box_cvd_long) else box_cvd_long
                    status_summaries.append(
                        f"{g_name} ({k_test*5}M | {box_spr_pct:.2f}%≤{max_spr:.2f}% | CVD {best_abs_cvd:+.0f}/{req_cvd:.0f})"
                    )

                if is_flat_box and len(upper_touches) >= req_touches and in_upper_half and box_cvd_short > req_cvd:
                    last_t_ts = sub_ts[upper_touches[-1]]
                    tm_conf = get_1m_extreme_ts(candles_1m_fut, last_t_ts, last_t_ts + 300000, is_high=True)
                    detected_dir = "SHORT"
                    detected_group = g_name
                    detected_label = f"SETUP 1 ({g_name}): BEARISH BOX"
                    detected_header = (
                        f"🔥 S1 [{g_name}] BEARISH BOX ({k_test*5}M | Body {box_spr_pct:.2f}% ≤ {max_spr:.2f}% | "
                        f"{len(upper_touches)}x horní otest | CVD {box_cvd_short:+.1f} > +{req_cvd:.0f} BTC [Spot bg: {box_spot_val:+.1f}])"
                    )
                    detected_confirm_ts = tm_conf
                    detected_zone_p = max(sub_h)
                    detected_pb = g_pb
                    detected_sl = g_sl
                    detected_tp_mode = g_tp_mode
                    detected_mins = k_test * 5
                    detected_spread = box_spr_pct
                    detected_cvd = box_cvd_short
                    detected_spot = box_spot_val
                    break

                elif is_flat_box and len(lower_touches) >= req_touches and in_lower_half and box_cvd_long < -req_cvd:
                    last_t_ts = sub_ts[lower_touches[-1]]
                    tm_conf = get_1m_extreme_ts(candles_1m_fut, last_t_ts, last_t_ts + 300000, is_high=False)
                    detected_dir = "LONG"
                    detected_group = g_name
                    detected_label = f"SETUP 1 ({g_name}): BULLISH BOX"
                    detected_header = (
                        f"🔥 S1 [{g_name}] BULLISH BOX ({k_test*5}M | Body {box_spr_pct:.2f}% ≤ {max_spr:.2f}% | "
                        f"{len(lower_touches)}x spodní otest | CVD {box_cvd_long:+.1f} < -{req_cvd:.0f} BTC [Spot bg: {box_spot_val:+.1f}])"
                    )
                    detected_confirm_ts = tm_conf
                    detected_zone_p = min(sub_l)
                    detected_pb = g_pb
                    detected_sl = g_sl
                    detected_tp_mode = g_tp_mode
                    detected_mins = k_test * 5
                    detected_spread = box_spr_pct
                    detected_cvd = box_cvd_long
                    detected_spot = box_spot_val
                    break

            if detected_dir is not None:
                break

        with ENGINE["lock"]:
            mem = ENGINE["s1_memory"]
            if detected_dir is not None:
                if not mem["active"] or mem["direction"] != detected_dir or mem.get("group_id") != detected_group:
                    mem["active"] = True
                    mem["direction"] = detected_dir
                    mem["group_id"] = detected_group
                    mem["setup_label"] = detected_label
                    mem["header_text"] = detected_header
                    mem["confirm_1m_ts"] = detected_confirm_ts
                    mem["locked_at_sec"] = now_sec
                    mem["zone_extreme_p"] = detected_zone_p
                    mem["pb_pct"] = detected_pb
                    mem["sl_pct"] = detected_sl
                    mem["tp_mode"] = detected_tp_mode
                    mem["box_mins"] = detected_mins
                    mem["box_spread_pct"] = round(detected_spread, 2)
                    mem["box_cvd"] = round(detected_cvd, 1)
                    mem["box_spot"] = round(detected_spot, 1)
                else:
                    mem["header_text"] = detected_header
                    mem["box_mins"] = detected_mins
                    mem["box_spread_pct"] = round(detected_spread, 2)
                    mem["box_cvd"] = round(detected_cvd, 1)
                    mem["box_spot"] = round(detected_spot, 1)

            is_mem_active = mem["active"]
            active_dir = mem["direction"]
            active_group = mem.get("group_id", "MEDIUM")
            active_label = mem["setup_label"]
            active_header = mem["header_text"]
            active_confirm_ts = mem["confirm_1m_ts"]
            active_pb = mem.get("pb_pct", 0.0012)
            active_sl = mem.get("sl_pct", 0.0020)
            active_tp_mode = mem.get("tp_mode", "SPLIT_50_50")
            m_mins = mem.get("box_mins", detected_mins)
            m_spr = mem.get("box_spread_pct", detected_spread)
            m_cvd = mem.get("box_cvd", detected_cvd)
            m_spot = mem.get("box_spot", detected_spot)

        if is_mem_active:
            entry_ok, entry_txt, t_payload = evaluate_setup1_1m_entry(
                active_dir, active_confirm_ts, candles_1m_fut, btc_price, upper_p, lower_p,
                active_label, fut_map, pb_pct=active_pb, sl_pct=active_sl, tp_mode=active_tp_mode
            )
            msg = f"{prefix}{active_header}\n{entry_txt}"
            if liquid_ok and entry_ok:
                agent_msg = execute_okx_agent_trade(t_payload)
                poc_v, vah_v, val_v = vp_data
                cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9 = flow_metrics
                trend_1h_str = compute_1h_trend_info(candles_1h, btc_price)
                now_str = get_prague_now().strftime("%Y-%m-%d %H:%M:%S")
                log_block = (
                    f"\n📊 <b>DATA PRO TÝDENNÍ ANALÝZU & ARGON 4 AI:</b>\n"
                    f"• Čas: {now_str} | Skupina: {active_group} | Směr: {active_dir} | RRR: {t_payload['rrr']}\n"
                    f"• Parametry: PB {active_pb*100:.2f}% | SL {active_sl*100:.2f}% | TP Režim: {active_tp_mode}\n"
                    f"• Krabice: {m_mins}M | Body šířka: {m_spr:.2f}% | Box CVD: {m_cvd:+.1f} | Box Spot (bg): {m_spot:+.1f}\n"
                    f"• Matrix 5M/25M/45M: CVD ({cvd1:+.1f}/{cvd5:+.1f}/{cvd9:+.1f}) | Spot ({scvd1:+.1f}/{scvd5:+.1f}/{scvd9:+.1f}) | OI ({oi1:+.1f}/{oi5:+.1f}/{oi9:+.1f})\n"
                    f"• Kontext: 1H Trend {trend_1h_str} | VAH {vah_v:.0f}$ | POC {poc_v:.0f}$ | VAL {val_v:.0f}$"
                )
                msg += f"\n{agent_msg}{log_block}"
                log_weekly_trade_event({
                    "timestamp": now_str,
                    "setup": f"SETUP_1_{active_group}",
                    "group": active_group,
                    "direction": active_dir,
                    "entry": t_payload["entry"],
                    "sl": t_payload["sl_market"],
                    "sl_pct": round(active_sl * 100, 2),
                    "pb_pct": round(active_pb * 100, 2),
                    "tp_mode": active_tp_mode,
                    "tp1": t_payload["tp1_limit_50pct"],
                    "tp2": t_payload["tp2_limit_50pct"],
                    "rrr": t_payload["rrr"],
                    "box_mins": m_mins,
                    "box_body_spread_pct": m_spr,
                    "box_cvd": m_cvd,
                    "box_spot_bg": m_spot,
                    "trend_1h": trend_1h_str,
                    "cvd_5m_25m_45m": [round(cvd1, 1), round(cvd5, 1), round(cvd9, 1)],
                    "spot_5m_25m_45m": [round(scvd1, 1), round(scvd5, 1), round(scvd9, 1)],
                    "oi_5m_25m_45m": [round(oi1, 1), round(oi5, 1), round(oi9, 1)],
                    "vp_vah_poc_val": [round(vah_v, 0), round(poc_v, 0), round(val_v, 0)],
                    "agent_status": agent_msg
                })
                with ENGINE["lock"]:
                    ENGINE["s1_memory"]["active"] = False
                odesli_upozorneni("S1_LOCK_1H", f"SETUP 1 [{active_group}]: {active_dir} MAKER ENTRY", msg, lock_duration=3600)
            return msg, bool(liquid_ok and entry_ok)

        return " 📦 ".join(status_summaries), False
    except Exception:
        return "Načítám data Setupu 1...", False

# --- SETUP 2: MACRO SFP (OVĚŘENÝ SWING ≥30M + SFP RECLAIM + 3–9 SVÍČEK | OI <= -50 | FUTURES CVD |Δ| >= 100 | LIMIT 0.05 %) ---
def scan_setup_2(candles_300, candles_1h, fut_map, oi_change_map, liquid_ok, btc_price, upper_p, lower_p, vp_data, flow_metrics):
    try:
        rem_s2 = get_setup_cooldown_remaining("S2_LOCK_1H", 3600)
        if rem_s2 > 0:
            return f"🔒 Setup 2 uzamčen na 1H (zbývá {rem_s2 // 60 + 1} min) | Setup 1 povolen.", False, ""

        if len(candles_300) < 20 or len(candles_1h) < 10:
            return "Načítám historii trhu...", False, "Skenuji levely..."

        try:
            tz_p = ZoneInfo("Europe/Prague")
        except Exception:
            tz_p = timezone(timedelta(hours=1))

        now_prague = datetime.now(tz_p)
        yesterday_date = now_prague.date() - timedelta(days=1)
        current_date = now_prague.date()

        pdh, pdl = 0.0, float("inf")
        for c in candles_1h:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_p)
            if dt.date() == yesterday_date:
                pdh, pdl = max(pdh, float(c[2])), min(pdl, float(c[3]))
        if pdh == 0.0:
            pdh, pdl = 0.0, 0.0

        all_5m_asc = candles_300[::-1]
        today_candles = []
        asia_h, asia_l = 0.0, float("inf")
        asia_h_idx, asia_l_idx = -100, -100
        lon_h, lon_l = 0.0, float("inf")
        lon_h_idx, lon_l_idx = -100, -100

        for c in all_5m_asc:
            ts_c = int(c[0])
            dt = datetime.fromtimestamp(ts_c / 1000, tz_p)
            if dt.date() != current_date:
                continue
            c_idx = len(today_candles)
            h_v, l_v = float(c[2]), float(c[3])
            today_candles.append((ts_c, float(c[1]), h_v, l_v, float(c[4]), dt.hour))
            if 1 <= dt.hour < 7:
                if h_v > asia_h:
                    asia_h, asia_h_idx = h_v, c_idx
                if l_v < asia_l:
                    asia_l, asia_l_idx = l_v, c_idx
            elif 9 <= dt.hour < 14:
                if h_v > lon_h:
                    lon_h, lon_h_idx = h_v, c_idx
                if l_v < lon_l:
                    lon_l, lon_l_idx = l_v, c_idx

        if asia_h == 0.0:
            asia_h, asia_l = 0.0, 0.0
        if lon_h == 0.0:
            lon_h, lon_l = 0.0, 0.0

        raw_levels = [
            ("PDH", pdh, True, 0, -100),
            ("PDL", pdl, False, 0, -100),
            ("ASIA H", asia_h, True, 7, asia_h_idx),
            ("ASIA L", asia_l, False, 7, asia_l_idx),
            ("LON H", lon_h, True, 14, lon_h_idx),
            ("LON L", lon_l, False, 14, lon_l_idx)
        ]

        cum_cvd_today = []
        running_cvd = 0.0
        for tc in today_candles:
            running_cvd += fut_map.get(tc[0], 0.0)
            cum_cvd_today.append(running_cvd)

        def is_valid_macro_swing_sweep(lvl_val, is_high, form_idx, candidate_idx):
            if form_idx >= 0:
                if (candidate_idx - form_idx) < 6:
                    return False
                between = today_candles[form_idx + 1:candidate_idx]
                if not between:
                    return False
                if is_high:
                    min_pullback = min(x[3] for x in between)
                    if ((lvl_val - min_pullback) / lvl_val) < 0.0025:
                        return False
                else:
                    max_bounce = max(x[2] for x in between)
                    if ((max_bounce - lvl_val) / lvl_val) < 0.0025:
                        return False
            else:
                if candidate_idx >= 2:
                    pre_c = today_candles[max(0, candidate_idx - 4):candidate_idx]
                    if is_high and max(x[2] for x in pre_c) >= lvl_val:
                        return False
                    if not is_high and min(x[3] for x in pre_c) <= lvl_val:
                        return False
            return True

        untouched_levels = []
        for n, v, h, valid, f_idx in raw_levels:
            if v > 0 and now_prague.hour >= valid:
                already_touched = any(
                    tc[5] >= valid and ((h and tc[2] >= v) or (not h and tc[3] <= v))
                    for tc in today_candles
                )
                if not already_touched:
                    untouched_levels.append(f"{n}: {v:.0f}")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"

        pending_retest_msgs = []
        triggered_msg, is_triggered = None, False
        prefix = "" if liquid_ok else "⏸️ "
        n_today = len(today_candles)

        for name, val, is_high, valid_from_hour, form_idx in raw_levels:
            if val <= 0 or now_prague.hour < valid_from_hour:
                continue

            first_touch_idx = next(
                (idx for idx, tc in enumerate(today_candles)
                 if tc[5] >= valid_from_hour and ((is_high and tc[2] >= val) or (not is_high and tc[3] <= val))),
                None
            )
            if first_touch_idx is None:
                continue

            if not is_valid_macro_swing_sweep(val, is_high, form_idx, first_touch_idx):
                continue

            sweep_idx = first_touch_idx
            ts_sweep = today_candles[sweep_idx][0]
            limit_entry_p = val * (1.0 - S2_LIMIT_PCT) if is_high else val * (1.0 + S2_LIMIT_PCT)
            cvd_at_sweep = cum_cvd_today[sweep_idx]
            retest_hit = False

            min_r_idx = sweep_idx + 2
            max_r_idx = min(sweep_idx + 8, n_today - 1)

            if (n_today - 1) >= min_r_idx:
                for r_idx in range(min_r_idx, max_r_idx + 1):
                    tc_r = today_candles[r_idx]
                    ts_r = tc_r[0]
                    cvd_diff = cum_cvd_today[r_idx] - cvd_at_sweep

                    oi_sweep = min(oi_change_map.get(ts_sweep, 0.0), oi_change_map.get(ts_sweep, 0.0) + oi_change_map.get(ts_sweep + 300000, 0.0))
                    oi_retest = min(oi_change_map.get(ts_r, 0.0), sum(oi_change_map.get(today_candles[k][0], 0.0) for k in range(sweep_idx, r_idx + 1)))
                    best_oi_flush = min(oi_sweep, oi_retest)

                    if is_high:
                        reclaimed = any(today_candles[k][4] < val for k in range(sweep_idx, r_idx + 1))
                        reached_005 = reclaimed and (tc_r[2] >= limit_entry_p) and (tc_r[4] <= val)
                    else:
                        reclaimed = any(today_candles[k][4] > val for k in range(sweep_idx, r_idx + 1))
                        reached_005 = reclaimed and (tc_r[3] <= limit_entry_p) and (tc_r[4] >= val)

                    if reached_005 and best_oi_flush <= -50.0 and abs(cvd_diff) >= 100.0:
                        if r_idx >= (n_today - 2):
                            direction = "SHORT" if is_high else "LONG"
                            t_payload = build_trade_plan(
                                direction, limit_entry_p, upper_p, lower_p,
                                f"SETUP 2: SFP {name} {direction}", sl_pct=DEFAULT_SL_PCT, tp_mode="SPLIT_50_50"
                            )
                            t_payload["trigger_ready"] = True
                            entry_txt = f"✅ MAKER {direction} (0.05% z {name}): {limit_entry_p:.0f}$ (1000$) | SL (0.30% Mkt): {t_payload['sl_market']:.0f}$ | Maker TP1: {t_payload['tp1_limit_50pct']:.0f}$ | Maker TP2: {t_payload['tp2_limit_50pct']:.0f}$"
                            triggered_msg = f"{prefix}🔥 SETUP 2 AKTIVNÍ ({name} {val:.0f}$): OI {best_oi_flush:.1f} | CVD Δ {cvd_diff:+.1f}\n{entry_txt}"
                            if liquid_ok:
                                agent_msg = execute_okx_agent_trade(t_payload)
                                poc_v, vah_v, val_v = vp_data
                                cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9 = flow_metrics
                                trend_1h_str = compute_1h_trend_info(candles_1h, btc_price)
                                now_str = get_prague_now().strftime("%Y-%m-%d %H:%M:%S")
                                log_block = (
                                    f"\n📊 <b>DATA PRO TÝDENNÍ ANALÝZU & ARGON 4 AI:</b>\n"
                                    f"• Čas: {now_str} | Setup: S2 ({name}) | Směr: {direction} | RRR: {t_payload['rrr']}\n"
                                    f"• SFP Metriky: Level {val:.0f}$ | OI Flush {best_oi_flush:+.1f} BTC | CVD Δ {cvd_diff:+.1f} BTC\n"
                                    f"• Matrix 5M/25M/45M: CVD ({cvd1:+.1f}/{cvd5:+.1f}/{cvd9:+.1f}) | Spot ({scvd1:+.1f}/{scvd5:+.1f}/{scvd9:+.1f}) | OI ({oi1:+.1f}/{oi5:+.1f}/{oi9:+.1f})\n"
                                    f"• Kontext: 1H Trend {trend_1h_str} | VAH {vah_v:.0f}$ | POC {poc_v:.0f}$ | VAL {val_v:.0f}$"
                                )
                                triggered_msg += f"\n{agent_msg}{log_block}"
                                log_weekly_trade_event({
                                    "timestamp": now_str,
                                    "setup": f"SETUP_2_SFP_{name}",
                                    "group": "S2_MACRO_SFP",
                                    "direction": direction,
                                    "level_price": round(val, 1),
                                    "entry": t_payload["entry"],
                                    "sl": t_payload["sl_market"],
                                    "sl_pct": 0.30,
                                    "tp_mode": "SPLIT_50_50",
                                    "tp1": t_payload["tp1_limit_50pct"],
                                    "tp2": t_payload["tp2_limit_50pct"],
                                    "rrr": t_payload["rrr"],
                                    "oi_flush": round(best_oi_flush, 1),
                                    "sfp_cvd_diff": round(cvd_diff, 1),
                                    "trend_1h": trend_1h_str,
                                    "cvd_5m_25m_45m": [round(cvd1, 1), round(cvd5, 1), round(cvd9, 1)],
                                    "spot_5m_25m_45m": [round(scvd1, 1), round(scvd5, 1), round(scvd9, 1)],
                                    "oi_5m_25m_45m": [round(oi1, 1), round(oi5, 1), round(oi9, 1)],
                                    "vp_vah_poc_val": [round(vah_v, 0), round(poc_v, 0), round(val_v, 0)],
                                    "agent_status": agent_msg
                                })
                                odesli_upozorneni("S2_LOCK_1H", f"SETUP 2: {name} MAKER {direction}", triggered_msg, lock_duration=3600)
                            is_triggered = bool(liquid_ok)
                        retest_hit = True
                        break

            total_elapsed = (n_today - sweep_idx)
            if not retest_hit and 1 <= total_elapsed <= 9:
                pending_retest_msgs.append(f"⏳ {name} vybrán – čekám SFP retest na 0.05% ({limit_entry_p:.0f}$) | CVD Δ {cum_cvd_today[-1] - cvd_at_sweep:+.1f} (zbývá {9 - total_elapsed} sv.)")

        if triggered_msg:
            return triggered_msg, is_triggered, levels_str
        elif pending_retest_msgs:
            return " | ".join(pending_retest_msgs), False, levels_str
        return "Skenuji Setup 2 (Ověřený Swing ≥30M & 0.25% odraz | SFP Reclaim 3–9 sv. | OI ≤ -50 | CVD |Δ| ≥ 100 | Maker 0.05%)...", False, levels_str
    except Exception:
        return "Načítám levely...", False, ""

@st.cache_resource
def start_background_guardian():
    my_token = str(uuid.uuid4())
    sys.__dict__["OKX_GUARDIAN_TOKEN"] = my_token

    def _guardian_loop(thread_token):
        tick = 0
        while True:
            if sys.__dict__.get("OKX_GUARDIAN_TOKEN") != thread_token:
                break
            try:
                poll_realtime_okx_flow()
                if tick % 5 == 0:
                    manage_active_okx_lifecycle()
                if tick % 15 == 0:
                    liq_ok, _ = check_liquid_hours()
                    if liq_ok:
                        data = fetch_okx_data()
                        f_metrics = data[0:9]
                        c_300, c_1h, fut_map, spot_map, oi_change_map = data[12], data[13], data[14], data[15], data[16]
                        b_p, vp_d, liq_d, m1_f = data[17], data[18], data[19], data[20]
                        up_p, _, low_p, _ = liq_d
                        scan_setup_1(c_300, c_1h, liq_ok, m1_f, b_p, up_p, low_p, fut_map, spot_map, vp_d, f_metrics)
                        scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liq_ok, b_p, up_p, low_p, vp_d, f_metrics)
                tick += 1
            except Exception:
                pass
            time.sleep(2)

    t = threading.Thread(target=_guardian_loop, args=(my_token,), daemon=True)
    t.start()
    return my_token

start_background_guardian()

liquid_ok, liq_status_text = check_liquid_hours()
total_pnl, win_rate = load_trading_data()
(cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9,
 cvd_12, scvd_12, c_12_asc, c_300, c_1h, fut_map, spot_map, oi_change_map,
 b_price, vp_data, liq_data, m1_fut, m1_spot) = fetch_okx_data()
poc_1h, vah_1h, val_1h = vp_data
upper_p, upper_btc, lower_p, lower_btc = liq_data
flow_metrics_tuple = (cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9)

msg1, trg1 = scan_setup_1(c_300, c_1h, liquid_ok, m1_fut, b_price, upper_p, lower_p, fut_map, spot_map, vp_data, flow_metrics_tuple)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liquid_ok, b_price, upper_p, lower_p, vp_data, flow_metrics_tuple)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

c_cvd1 = "#3fb950" if cvd1 >= 0 else "#f85149"
c_cvd5 = "#3fb950" if cvd5 >= 0 else "#f85149"
c_cvd9 = "#3fb950" if cvd9 >= 0 else "#f85149"
c_scvd1 = "#3fb950" if scvd1 >= 0 else "#f85149"
c_scvd5 = "#3fb950" if scvd5 >= 0 else "#f85149"
c_scvd9 = "#3fb950" if scvd9 >= 0 else "#f85149"
c_oi1 = "#3fb950" if oi1 >= 0 else "#f85149"
c_oi5 = "#3fb950" if oi5 >= 0 else "#f85149"
c_oi9 = "#3fb950" if oi9 >= 0 else "#f85149"

pnl_color = "#3fb950" if total_pnl >= 0 else "#f85149"
pnl_sign = "+$" if total_pnl >= 0 else "-$"

cvd_bar_pct = min(48.0, max(4.0, (abs(cvd5) / 150.0) * 48.0))
cvd_mercury_cls = "thermo-mercury-up" if cvd5 >= 0 else "thermo-mercury-down"
spot_bar_pct = min(48.0, max(4.0, (abs(scvd5) / 30.0) * 48.0))
spot_mercury_cls = "thermo-mercury-up" if scvd5 >= 0 else "thermo-mercury-down"
oi_bar_pct = min(48.0, max(4.0, (abs(oi5) / 120.0) * 48.0))
oi_bar_left = "50%" if oi5 >= 0 else f"{50.0 - oi_bar_pct:.1f}%"
oi_bar_color = "#3fb950" if oi5 >= 0 else "#f85149"

st.markdown('<div class="gold-btc-banner"></div>', unsafe_allow_html=True)

matrix_html = "\n".join([
    '<div class="matrix-unified">',
    '<div style="color: #ffffff; font-weight: 900; font-size: 18px; margin-bottom: 12px; letter-spacing: 2px; text-shadow: 0px 2px 8px rgba(0,0,0,1);">OKX ORDER FLOW & LIQUIDATION MATRIX</div>',
    '<div class="matrix-grid">',
    '<div class="thermo-card">',
    '<div style="color: #00f3ff; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 2px 4px #000;">CVD (FUT)</div>',
    f'<div style="font-size: 20px; font-weight: 900; color: {c_cvd1}; text-shadow: 0 0 10px #000;">{cvd1:+,.1f}</div>',
    '<div class="thermo-tube-wrap">',
    '<div class="thermo-scale"><span style="color:#3fb950;">+150</span><span style="color:#7ee787;">+75</span><span style="color:#ffffff;">0</span><span style="color:#ffa198;">-75</span><span style="color:#f85149;">-150</span></div>',
    '<div class="thermo-glass"><div class="thermo-zero-line"></div>',
    f'<div class="{cvd_mercury_cls}" style="height: {cvd_bar_pct:.1f}%;"></div>',
    '</div></div>',
    '<div style="width: 100%; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px;">',
    '<div style="font-size: 9px; color: #94a3b8; font-weight: 800;">25M / 45M DELTA</div>',
    f'<div style="font-size: 13px; font-weight: 900; color: {c_cvd5};">{cvd5:+,.1f}</div>',
    f'<div style="font-size: 11px; font-weight: 900; color: {c_cvd9}; opacity: 0.85;">{cvd9:+,.1f}</div>',
    '</div></div>',
    '<div style="display: flex; flex-direction: column; justify-content: space-between;">',
    '<div class="liq-bumper-box">',
    '<div style="color: #f85149; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 TP2 LONG (50%) / SHORT LIQ (+2%)</div>',
    f'<div style="font-size: 19px; font-weight: 900; color: #ffffff; font-family: \'Orbitron\', sans-serif; text-shadow: 0 0 10px rgba(248,81,73,0.7);">{upper_p:,.0f} $</div>',
    f'<div style="color: #f1e05a; font-size: 11px; font-weight: 900; text-shadow: 0 1px 3px #000;">({upper_btc:.1f} BTC)</div>',
    '</div>',
    f'<div class="matrix-live-price">{b_price:,.0f}</div>',
    '<div class="liq-bumper-box">',
    '<div style="color: #3fb950; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 TP2 SHORT (50%) / LONG LIQ (-2%)</div>',
    f'<div style="font-size: 19px; font-weight: 900; color: #ffffff; font-family: \'Orbitron\', sans-serif; text-shadow: 0 0 10px rgba(63,185,80,0.7);">{lower_p:,.0f} $</div>',
    f'<div style="color: #f1e05a; font-size: 11px; font-weight: 900; text-shadow: 0 1px 3px #000;">({lower_btc:.1f} BTC)</div>',
    '</div>',
    '<div class="oi-center-box">',
    '<div style="color: #00f3ff; font-size: 10px; font-weight: 900; letter-spacing: 1px;">OPEN INTEREST (OI)</div>',
    '<div class="oi-bar-track">',
    '<div style="position:absolute; left:50%; top:0; bottom:0; width:2px; background:#fff; z-index:3;"></div>',
    f'<div style="position:absolute; top:1px; bottom:1px; left:{oi_bar_left}; width:{oi_bar_pct:.1f}%; background:{oi_bar_color}; border-radius:4px; box-shadow: 0 0 8px {oi_bar_color};"></div>',
    '</div>',
    f'<div style="font-size: 15px; font-weight: 900; color: {c_oi1};">{oi1:+,.1f} BTC</div>',
    f'<div style="font-size: 11px; font-weight: 800; color: #cbd5e1;"><span style="color:{c_oi5};">{oi5:+,.1f}</span> | <span style="color:{c_oi9};">{oi9:+,.1f}</span></div>',
    '</div></div>',
    '<div class="thermo-card">',
    '<div style="color: #f1e05a; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 2px 4px #000;">SPOT CVD (BG)</div>',
    f'<div style="font-size: 20px; font-weight: 900; color: {c_scvd1}; text-shadow: 0 0 10px #000;">{scvd1:+,.1f}</div>',
    '<div class="thermo-tube-wrap">',
    '<div class="thermo-glass"><div class="thermo-zero-line"></div>',
    f'<div class="{spot_mercury_cls}" style="height: {spot_bar_pct:.1f}%;"></div>',
    '</div>',
    '<div class="thermo-scale" style="text-align: left;"><span style="color:#3fb950;">+30</span><span style="color:#7ee787;">+15</span><span style="color:#ffffff;">0</span><span style="color:#ffa198;">-15</span><span style="color:#f85149;">-30</span></div>',
    '</div>',
    '<div style="width: 100%; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px;">',
    '<div style="font-size: 9px; color: #94a3b8; font-weight: 800;">25M / 45M DELTA</div>',
    f'<div style="font-size: 13px; font-weight: 900; color: {c_scvd5};">{scvd5:+,.1f}</div>',
    f'<div style="font-size: 11px; font-weight: 900; color: {c_scvd9}; opacity: 0.85;">{scvd9:+,.1f}</div>',
    '</div></div></div></div>'
])
st.markdown(matrix_html, unsafe_allow_html=True)

vp_header_html = "\n".join([
    '<div style="text-align: center; margin-top: 5px; margin-bottom: -15px; z-index: 10; position: relative;">',
    '<div style="color: #ffffff; font-weight: 900; font-size: 16px; letter-spacing: 2px; text-shadow: 0 2px 5px black;">ABSORPCE & 1H VOLUME PROFILE (LIVE 5M VELO MODE)</div>',
    f'<div style="color: #2dd4bf; font-size: 10px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 1px 3px black;">VAH: {vah_1h:.0f} 🔸 POC: {poc_1h:.0f} 🔸 VAL: {val_1h:.0f}</div>',
    '</div>'
])
st.markdown(vp_header_html, unsafe_allow_html=True)

if len(c_12_asc) == 12 and len(cvd_12) == 12 and len(scvd_12) == 12:
    x_axis = list(range(12))
    cum_cvd_chart, cum_scvd_chart = [], []
    curr_c, curr_s = 0.0, 0.0
    for i in range(12):
        curr_c += cvd_12[i]
        curr_s += scvd_12[i]
        cum_cvd_chart.append(curr_c)
        cum_scvd_chart.append(curr_s)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.56, 0.22, 0.22])

    if poc_1h > 0 and vah_1h > val_1h:
        fig.add_shape(type="rect", x0=-0.8, x1=11.3, y0=val_1h, y1=vah_1h, fillcolor="rgba(247, 147, 26, 0.06)", line=dict(width=0), layer="below", row=1, col=1)
        fig.add_trace(go.Scatter(x=[-0.8, 11.3], y=[vah_1h, vah_1h], mode="lines", line=dict(color="rgba(247, 147, 26, 0.65)", width=1.3, dash="dash"), hoverinfo="skip", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=[-0.8, 11.3], y=[poc_1h, poc_1h], mode="lines", line=dict(color="#f7931a", width=2.2), hoverinfo="skip", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=[-0.8, 11.3], y=[val_1h, val_1h], mode="lines", line=dict(color="rgba(247, 147, 26, 0.65)", width=1.3, dash="dash"), hoverinfo="skip", showlegend=False), row=1, col=1)

        for lbl_txt, lbl_val, lbl_col in [("VAH", vah_1h, "#f59e0b"), ("POC", poc_1h, "#f7931a"), ("VAL", val_1h, "#f59e0b")]:
            fig.add_annotation(
                x=0.0, y=lbl_val, xref="paper", yref="y",
                text=f"<b>{lbl_txt} {lbl_val:.0f}</b>",
                showarrow=False, xanchor="left", yanchor="middle",
                font=dict(family="Orbitron, sans-serif", size=9, color=lbl_col),
                bgcolor="rgba(4, 6, 9, 0.85)", bordercolor=lbl_col, borderwidth=1, borderpad=2
            )

    fig.add_trace(go.Candlestick(
        x=x_axis,
        open=[float(c[1]) for c in c_12_asc],
        high=[float(c[2]) for c in c_12_asc],
        low=[float(c[3]) for c in c_12_asc],
        close=[float(c[4]) for c in c_12_asc],
        increasing_line_color="#3fb950", decreasing_line_color="#f85149",
        increasing_fillcolor="#3fb950", decreasing_fillcolor="#f85149",
        increasing_line_width=1.8, decreasing_line_width=1.8, whiskerwidth=0.3, showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=[-0.8, 13.6], y=[b_price, b_price], mode="lines", line=dict(color="rgba(0, 243, 255, 0.55)", width=1.4, dash="dot"), hoverinfo="skip", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[11.0], y=[b_price], mode="markers", marker=dict(color="#00f3ff", size=7, line=dict(color="#ffffff", width=1.5)), hoverinfo="skip", showlegend=False), row=1, col=1)

    fig.add_annotation(
        x=1.0, y=b_price, xref="paper", yref="y",
        text=f"<b>LIVE {b_price:.0f}</b>",
        showarrow=False, xanchor="right", yanchor="middle",
        font=dict(family="Orbitron, sans-serif", size=11, color="#00f3ff"),
        bgcolor="rgba(4, 6, 9, 0.95)", bordercolor="#00f3ff", borderwidth=1.5, borderpad=4
    )

    fig.add_trace(go.Scatter(x=x_axis, y=cum_cvd_chart, mode="lines+markers", marker=dict(size=[0]*11 + [6], color="#00f3ff"), line=dict(color="#00f3ff", width=3, shape="spline", smoothing=1.1), showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=x_axis, y=cum_scvd_chart, mode="lines+markers", marker=dict(size=[0]*11 + [6], color="#f1e05a"), line=dict(color="#f1e05a", width=3, shape="spline", smoothing=1.1), showlegend=False), row=3, col=1)

    def get_smart_range(arr, pad_ratio=0.02):
        if not arr:
            return [0, 1]
        mn, mx = min(arr), max(arr)
        pd_val = (mx - mn) * pad_ratio
        if pd_val == 0:
            pd_val = 10
        return [mn - pd_val, mx + pd_val]

    price_points = [float(c[3]) for c in c_12_asc] + [float(c[2]) for c in c_12_asc] + [float(b_price)]
    if vah_1h > 0 and val_1h > 0:
        price_points.extend([vah_1h, val_1h])
    p_rng = get_smart_range(price_points, pad_ratio=0.04)
    c_rng = get_smart_range(cum_cvd_chart, pad_ratio=0.02)
    s_rng = get_smart_range(cum_scvd_chart, pad_ratio=0.02)

    fig.update_layout(
        height=760, margin=dict(l=6, r=6, t=20, b=0, pad=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, rangeslider=dict(visible=False), fixedrange=True, range=[-0.8, 13.6]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=p_rng),
        xaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=c_rng),
        xaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=s_rng)
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

liq_color = "#3fb950" if liquid_ok else "#94a3b8"
box1_cls = "alert-box signal-triggered" if trg1 else "alert-box"
box2_cls = "alert-box signal-triggered" if trg2 else "alert-box"

setups_html = "\n".join([
    '<div class="setups-container">',
    f'<div style="text-align: center; font-size: 11px; font-weight: 900; color: {liq_color}; letter-spacing: 1px; margin-bottom: 10px;">{liq_status_text}</div>',
    f'<div class="{box1_cls}">',
    '<div style="color: #f7931a; font-weight: 900; font-size: 17px; margin-bottom: 5px;">⚡ S1 TOP-DOWN (MACRO 60-180M ≤0.45% | MED 30-90M ≤0.30% | MICRO 15-45M ≤0.15%)</div>',
    f'<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg1.replace(chr(10), "<br>")}</div>',
    '</div>',
    f'<div class="{box2_cls}" style="margin-bottom: 0;">',
    '<div style="color: #f7931a; font-weight: 900; font-size: 17px; margin-bottom: 5px;">🎯 S2: MACRO SFP (OVĚŘENÝ SWING ≥30M | SFP RECLAIM | MAKER 0.05% | MAKER TP1/TP2)</div>',
    f'<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg2.replace(chr(10), "<br>")}</div>',
    f'<div style="color: #00f3ff; font-size: 12px; margin-top: 6px; font-weight: 800;">Zbývající levely: {l_str}</div>',
    '</div>',
    '</div>'
])
st.markdown(setups_html, unsafe_allow_html=True)

journal_html = "\n".join([
    '<div class="money-journal">',
    '<div class="money-content">',
    '<div style="text-align: center;">',
    '<div style="color: #7ee787; font-size: 14px; font-weight: 900; letter-spacing: 2px; text-shadow: 0px 2px 6px rgba(0,0,0,0.9);">CELKOVÝ PNL</div>',
    f'<div style="font-size: 34px; font-weight: 900; color: {pnl_color}; text-shadow: 0px 2px 10px rgba(0,0,0,0.9);">{pnl_sign}{abs(total_pnl):,.2f}</div>',
    '</div>',
    '<div style="text-align: center;">',
    '<div style="color: #f1e05a; font-size: 14px; font-weight: 900; letter-spacing: 2px; text-shadow: 0px 2px 6px rgba(0,0,0,0.9);">WIN RATE</div>',
    f'<div style="font-size: 34px; font-weight: 900; color: #f1e05a; text-shadow: 0px 2px 10px rgba(0,0,0,0.9);">{win_rate:.2f} %</div>',
    '</div>',
    '</div>',
    '</div>'
])
st.markdown(journal_html, unsafe_allow_html=True)

weekly_logs = load_weekly_trade_logs()
if weekly_logs:
    df_weekly = pd.DataFrame(weekly_logs)
    csv_bytes = df_weekly.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"📥 STÁHNOUT DATA TÝDENNÍHO TESTU PRO ANALÝZU ({len(weekly_logs)} záznamů)",
        data=csv_bytes,
        file_name=f"okx_weekly_test_{get_prague_now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

if st.button("🔄 AKTUALIZOVAT"):
    st.rerun()

if st.button("📲 OTESTOVAT TELEGRAM & AI AGENTA"):
    test_plan = build_trade_plan("SHORT", b_price, upper_p, lower_p, "TEST AI AGENT", sl_pct=0.0020, tp_mode="SPLIT_50_50")
    test_msg = execute_okx_agent_trade(test_plan)
    ok = odesli_upozorneni(
        "TEST_PING",
        "TEST SPOJENÍ TERMINÁL + TOP-DOWN 24/7 SBĚR",
        f"✅ Režim 24/7 (do 20.11. 13:59) běží!\n• S1 Top-Down (MACRO / MEDIUM / MICRO) Body-to-Body + čisté Futures CVD\n• Dynamický PB (0.18% / 0.12% / 0.08%), SL (0.30% / 0.20% / 0.10%) a Maker TP\nLive BTC: {b_price:.0f}$\n\n{test_msg}",
        force=True
    )
    if ok:
        st.success("Zpráva odeslána na Telegram!")
    else:
        st.error("Odeslání selhalo.")

if st.toggle("⏱️ Auto Refresh (20s)", value=False):
    time.sleep(20)
    st.rerun()
