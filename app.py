# === ZAČÁTEK ČÁSTI 1 ===
import os
import sys
import re
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
ALERT_STATE_FILE = "/tmp/okx_telegram_buffer_v14.json"
WEEKLY_LOG_FILE = "/tmp/okx_weekly_trades_log.json"
WEEKLY_LOG_BACKUP = "okx_weekly_trades_log.json"

DEFAULT_SL_PCT = 0.0030       # Výchozí Market Stop-Loss 0.30 % (Skupina 1 Macro & Setup 2)
S2_LIMIT_PCT = 0.0005         # Ponecháno pro zpětnou kompatibilitu konstant
POSITION_SIZE_USD = 2000.0    # Velikost pozice 2 000 USD (marže 200 USD při 10x)
PENDING_ORDER_TTL_SEC = 900   # Automatické zrušení nevyplněné VSTUPNÍ limitky po 15 minutách (900 s)
S1_MEMORY_TTL_SEC = 1200      # Paměť potvrzeného 5M Setupu 1 při čekání na 1M strukturu (20 min)

GROUP_RANK = {"MICRO": 1, "MEDIUM": 2, "MACRO": 3}

# --- ZABEZPEČENÉ NAČTENÍ OKX A GEMINI API KLÍČŮ ZE STREAMLIT SECRETS ---
try:
    OKX_SECRETS = {
        "API_KEY": st.secrets.get("OKX_API_KEY", ""),
        "SECRET_KEY": st.secrets.get("SECRET_KEY", "") or st.secrets.get("OKX_SECRET_KEY", ""),
        "PASSPHRASE": st.secrets.get("OKX_PASSPHRASE", ""),
        "INST_ID": st.secrets.get("OKX_INST_ID", "BTC-USD_UM_XPERP-310404"),
        "CONTRACT_BTC": float(st.secrets.get("OKX_CONTRACT_BTC", "0.0001")),
        "ENABLED": str(st.secrets.get("AI_TRADING_ENABLED", "false")).lower() == "true",
        "GEMINI_API_KEY": str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    }
except Exception:
    OKX_SECRETS = {"ENABLED": False, "GEMINI_API_KEY": ""}

@st.cache_resource
def get_realtime_engine_v14():
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
        "has_open_or_pending": False,
        "liq_cache": {
            "candle_ts": 0,
            "upper_p": 0.0,
            "upper_btc": 0.0,
            "lower_p": 0.0,
            "lower_btc": 0.0
        },
        "s1_memory": {
            "active": False,
            "v14_chrono_ok": True,
            "direction": "",
            "group_id": "",
            "setup_label": "",
            "header_text": "",
            "confirm_1m_ts": 0,
            "locked_at_sec": 0.0,
            "zone_extreme_p": 0.0,
            "box_mid": 0.0,
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

ENGINE = get_realtime_engine_v14()

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

def load_weekly_trade_logs():
    for path in [WEEKLY_LOG_FILE, WEEKLY_LOG_BACKUP]:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
        except Exception:
            continue
    return []

def log_weekly_trade_event(record_dict):
    try:
        with ENGINE["lock"]:
            logs = load_weekly_trade_logs()
            logs.append(record_dict)
            for path in [WEEKLY_LOG_FILE, WEEKLY_LOG_BACKUP]:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(logs, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
    except Exception:
        pass

def get_setup_cooldown_remaining(lock_key, lock_duration=3600):
    now_ts = time.time()
    with ENGINE["lock"]:
        history = _load_alert_history()
        last_trig = float(history.get(lock_key, 0.0))
        elapsed = now_ts - last_trig
        if elapsed < lock_duration:
            return int(lock_duration - elapsed)
    return 0

def get_s1_locked_rank():
    with ENGINE["lock"]:
        history = _load_alert_history()
        return int(history.get("S1_LAST_GROUP_RANK", 3))

def set_s1_locked_rank(rank_val):
    with ENGINE["lock"]:
        history = _load_alert_history()
        history["S1_LAST_GROUP_RANK"] = int(rank_val)
        _save_alert_history(history)

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

def has_okx_open_or_pending_trade():
    if not OKX_SECRETS.get("ENABLED") or not OKX_SECRETS.get("API_KEY"):
        return False
    inst_id = OKX_SECRETS["INST_ID"]
    try:
        pos = _okx_signed_request("GET", f"/api/v5/account/positions?instId={inst_id}")
        for p in (pos.get("data") or []):
            if abs(float(p.get("pos", "0") or 0.0)) > 0:
                return True
        pend = _okx_signed_request("GET", f"/api/v5/trade/orders-pending?instId={inst_id}")
        for ord_item in (pend.get("data") or []):
            if str(ord_item.get("reduceOnly", "false")).lower() != "true":
                return True
    except Exception:
        pass
    return False

# --- BEZPEČNÉ ODESÍLÁNÍ NA TELEGRAM (OCHRANA PROTI < A > V HTML + AUTOMATICKÝ FALLBACK) ---
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
        safe_detail = str(detail_zpravy).replace("<b>", "[[B_OPEN]]").replace("</b>", "[[B_CLOSE]]")
        safe_detail = safe_detail.replace("<", "≤").replace(">", "≥")
        safe_detail = safe_detail.replace("[[B_OPEN]]", "<b>").replace("[[B_CLOSE]]", "</b>")
        safe_title = str(setup_nazev).replace("<", "≤").replace(">", "≥")

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚨 <b>{safe_title}</b>\n\n{safe_detail}",
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            return True

        plain_text = re.sub(r"<[^>]+>", "", f"🚨 {safe_title}\n\n{safe_detail}")
        res_plain = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": plain_text}, timeout=5)
        return res_plain.status_code == 200
    except Exception as e:
        print(f"Telegram alert selhal: {e}")
        return False

# --- AKTIVNÍ SPRÁVA POZIC: 15M TTL VSTUPU + DYNAMICKÝ MAKER (POST-ONLY) TP + AUTO BREAK-EVEN (2000 USD) ---
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
                        "OKX EXEKUTOR: ZRUŠENA EXPIROVANÁ VSTUPNÍ LIMITKA (15 MIN)",
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

        with ENGINE["lock"]:
            ENGINE["has_open_or_pending"] = (active_pos is not None or len(entry_pend) > 0)

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
                        "OKX EXEKUTOR: MAKER TP VLOŽEN DO ORDERBOOKU",
                        tp_notif_txt,
                        lock_duration=60,
                        force=True
                    )

            # 2B. Auto Break-Even (platí pro režim SPLIT_50_50 po zasažení TP1 při pozici 2000 USD)
            if tp_mode == "SPLIT_50_50":
                expected_full_ct = int((POSITION_SIZE_USD / avg_px) / ct_val)
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
                                        "OKX EXEKUTOR: STOP-LOSS POSUNUT NA BREAK-EVEN",
                                        f"🛡️ TP1 (první 50 % pozice) byl zasažen!\nStop-Loss zbývající poloviny pozice byl automaticky posunut na vstupní cenu Break-Even: <b>{be_px_str}$</b>.",
                                        lock_duration=300,
                                        force=True
                                    )
    except Exception:
        pass
# === KONEC ČÁSTI 1 ===# === ZAČÁTEK ČÁSTI 2 ===

# --- GENERICKÝ VÝPOČET VOLUME PROFILU (VAH, POC, VAL) ---
def compute_vp_levels_from_df(df_slice, bins=40):
    if df_slice is None or len(df_slice) < 3:
        return {"vah": 0.0, "poc": 0.0, "val": 0.0}
    try:
        low_min = float(df_slice["low"].min())
        high_max = float(df_slice["high"].max())
        if high_max <= low_min:
            c_val = float(df_slice["close"].iloc[-1])
            return {"vah": c_val, "poc": c_val, "val": c_val}

        step = (high_max - low_min) / float(bins)
        vol_hist = [0.0] * bins
        centers = [low_min + (i + 0.5) * step for i in range(bins)]

        for _, row in df_slice.iterrows():
            c_px = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
            v_val = max(float(row.get("vol_btc", 0.0) or 0.0), 0.01)
            idx = int((c_px - low_min) / step)
            if idx < 0:
                idx = 0
            elif idx >= bins:
                idx = bins - 1
            vol_hist[idx] += v_val

        total_vol = sum(vol_hist)
        if total_vol <= 0:
            c_val = float(df_slice["close"].iloc[-1])
            return {"vah": c_val, "poc": c_val, "val": c_val}

        poc_idx = int( max(range(bins), key=lambda i: vol_hist[i]) )
        poc_price = centers[poc_idx]

        target_vol = total_vol * 0.70
        curr_vol = vol_hist[poc_idx]
        left_idx = poc_idx
        right_idx = poc_idx

        while curr_vol < target_vol and (left_idx > 0 or right_idx < bins - 1):
            left_v = vol_hist[left_idx - 1] if left_idx > 0 else -1.0
            right_v = vol_hist[right_idx + 1] if right_idx < bins - 1 else -1.0
            if right_v >= left_v and right_idx < bins - 1:
                right_idx += 1
                curr_vol += vol_hist[right_idx]
            elif left_idx > 0:
                left_idx -= 1
                curr_vol += vol_hist[left_idx]
            else:
                break

        vah_price = centers[right_idx] + (step * 0.5)
        val_price = centers[left_idx] - (step * 0.5)
        return {
            "vah": round(vah_price, 1),
            "poc": round(poc_price, 1),
            "val": round(val_price, 1)
        }
    except Exception:
        return {"vah": 0.0, "poc": 0.0, "val": 0.0}

# --- KAPITOLA 1: 1H, 3H A 6H VOLUME PROFILE + DETEKTOR KONFLUENCÍ (DO 0.10 %) ---
def compute_scalp_mtf_vp(df_1m, df_5m, current_price):
    vp_1h = compute_vp_levels_from_df(df_1m.tail(60) if df_1m is not None else None, bins=36)
    vp_3h = compute_vp_levels_from_df(df_5m.tail(36) if df_5m is not None else None, bins=40)
    vp_6h = compute_vp_levels_from_df(df_5m.tail(72) if df_5m is not None else None, bins=48)

    all_levels = []
    for tf_name, vp_dict in [("1H", vp_1h), ("3H", vp_3h), ("6H", vp_6h)]:
        for lvl_type in ["VAH", "POC", "VAL"]:
            px = float(vp_dict.get(lvl_type.lower(), 0.0) or 0.0)
            if px > 0:
                all_levels.append({
                    "tf": tf_name,
                    "type": lvl_type,
                    "label": f"{tf_name}_{lvl_type}",
                    "price": px
                })

    # Hledání konfluencí: alespoň 2 hladiny z RŮZNÝCH časových rámců do 0.10 % od sebe
    all_levels_sorted = sorted(all_levels, key=lambda x: x["price"])
    confluences = []
    used_indices = set()

    for i in range(len(all_levels_sorted)):
        if i in used_indices:
            continue
        base_lvl = all_levels_sorted[i]
        cluster = [base_lvl]
        for j in range(i + 1, len(all_levels_sorted)):
            cand = all_levels_sorted[j]
            if abs(cand["price"] - base_lvl["price"]) / max(base_lvl["price"], 1.0) <= 0.0010:
                cluster.append(cand)
                used_indices.add(j)
            else:
                break
        unique_tfs = set(item["tf"] for item in cluster)
        if len(unique_tfs) >= 2:
            used_indices.add(i)
            low_p = min(item["price"] for item in cluster)
            high_p = max(item["price"] for item in cluster)
            mid_p = round(sum(item["price"] for item in cluster) / len(cluster), 1)
            labels_str = "+".join(item["label"] for item in cluster)
            confluences.append({
                "mid": mid_p,
                "low": round(low_p, 1),
                "high": round(high_p, 1),
                "count": len(cluster),
                "tf_count": len(unique_tfs),
                "labels": labels_str
            })

    return {
        "1h": vp_1h,
        "3h": vp_3h,
        "6h": vp_6h,
        "all_levels": all_levels_sorted,
        "confluences": confluences
    }

# --- KAPITOLA 2: 3H DETEKTOR TREND VS. CHOP (PŘÍMKA VS. KLIKATICE NA 36 SVÍČKÁCH 5M) ---
def compute_3h_trend_chop_info(df_5m):
    default_res = {
        "state": "CHOP (RANGE)",
        "regime": "CHOP",
        "direction": "NEUTRAL",
        "efficiency_pct": 0.0,
        "net_move_usd": 0.0,
        "net_move_pct": 0.0,
        "total_path_usd": 0.0,
        "summary_txt": "CHOP (Efektivita 0.0 %)"
    }
    if df_5m is None or len(df_5m) < 12:
        return default_res

    try:
        # Použijeme posledních 36 uzavřených 5M svíček (3 hodiny)
        closed_5m = df_5m.iloc[:-1].tail(36).copy() if len(df_5m) > 36 else df_5m.tail(36).copy()
        if len(closed_5m) < 6:
            return default_res

        start_px = float(closed_5m["open"].iloc[0])
        end_px = float(closed_5m["close"].iloc[-1])
        net_diff = end_px - start_px
        net_move_usd = abs(net_diff)
        net_move_pct = (net_move_usd / max(start_px, 1.0)) * 100.0

        # Klikatice: součet ušlé dráhy mezi svíčkami + vnitřní rozpětí svíček (High - Low)
        total_path_usd = 0.0
        prev_close = start_px
        for _, row in closed_5m.iterrows():
            c_high = float(row["high"])
            c_low = float(row["low"])
            c_close = float(row["close"])
            candle_range = max(c_high - c_low, abs(c_close - prev_close))
            total_path_usd += candle_range
            prev_close = c_close

        efficiency_pct = (net_move_usd / max(total_path_usd, 1.0)) * 100.0
        dir_str = "BULL" if net_diff >= 0 else "BEAR"

        # Pravidla Kapitoly 2:
        # CHOP: Efektivita < 22 % NEBO Čistý posun < 0.35 %
        # MILD TREND: Efektivita 22–40 % A Čistý posun 0.35–0.75 %
        # STRONG TREND: Efektivita > 40 % A Čistý posun > 0.75 %
        if efficiency_pct < 22.0 or net_move_pct < 0.35:
            regime = "CHOP"
            state_label = f"CHOP_3H (Ef:{efficiency_pct:.1f}% | Δ:{net_move_pct:.2f}%)"
            dir_out = "NEUTRAL"
        elif efficiency_pct > 40.0 and net_move_pct > 0.75:
            regime = f"STRONG_{dir_str}"
            state_label = f"STRONG_{dir_str}_3H (Ef:{efficiency_pct:.1f}% | Δ:{net_move_pct:.2f}%)"
            dir_out = dir_str
        else:
            regime = f"MILD_{dir_str}"
            state_label = f"MILD_{dir_str}_3H (Ef:{efficiency_pct:.1f}% | Δ:{net_move_pct:.2f}%)"
            dir_out = dir_str

        return {
            "state": state_label,
            "regime": regime,
            "direction": dir_out,
            "efficiency_pct": round(efficiency_pct, 1),
            "net_move_usd": round(net_move_usd, 1),
            "net_move_pct": round(net_move_pct, 2),
            "total_path_usd": round(total_path_usd, 1),
            "summary_txt": f"{regime} (Přímka {net_move_usd:.0f}$ [{net_move_pct:.2f}%] / Klikatice {total_path_usd:.0f}$ = Efektivita {efficiency_pct:.1f}%)"
        }
    except Exception:
        return default_res

# --- KAPITOLA 3: RADAR NA SKUTEČNÉ NEVYBRANÉ LEVÉ SWINGY (ZA POSLEDNÍ 3 HODINY) ---
def detect_untested_left_swings(df_5m, current_price):
    res = {"swing_highs": [], "swing_lows": []}
    if df_5m is None or len(df_5m) < 10:
        return res

    try:
        # Analyzujeme uzavřené svíčky za poslední 3 hodiny (36 svíček + 3 pro pravé potvrzení)
        work_df = df_5m.iloc[:-1].tail(42).reset_index(drop=True)
        n = len(work_df)
        if n < 9:
            return res

        # 1. Hledání skutečných Swing Highs a Swing Lows:
        # - Lokální extrém (3 svíčky vlevo a 3 vpravo)
        # - Skutečný odjezd ceny opačným směrem alespoň o 0.15 %
        # - Panenská likvidita (žádná pozdější svíčka až do konce okna tento extrém neprorazila)
        for i in range(3, n - 3):
            cand_high = float(work_df["high"].iloc[i])
            cand_low = float(work_df["low"].iloc[i])
            cand_time = str(work_df["dt_str"].iloc[i]) if "dt_str" in work_df.columns else f"-{(n-i)*5}m"

            left_highs = [float(work_df["high"].iloc[k]) for k in range(i - 3, i)]
            right_highs = [float(work_df["high"].iloc[k]) for k in range(i + 1, i + 4)]
            if cand_high >= max(left_highs) and cand_high > max(right_highs):
                after_slice = work_df.iloc[i + 1:]
                max_after_high = float(after_slice["high"].max())
                min_after_low = float(after_slice["low"].min())
                reversal_drop_pct = (cand_high - min_after_low) / max(cand_high, 1.0)
                # Panenský (nevybraný) + skutečný odjezd opačným směrem >= 0.15 %
                if max_after_high <= cand_high and reversal_drop_pct >= 0.0015:
                    dist_pct = abs(cand_high - current_price) / max(current_price, 1.0)
                    if dist_pct <= 0.0080:
                        res["swing_highs"].append({
                            "price": round(cand_high, 1),
                            "time": cand_time,
                            "reversal_pct": round(reversal_drop_pct * 100.0, 2)
                        })

            left_lows = [float(work_df["low"].iloc[k]) for k in range(i - 3, i)]
            right_lows = [float(work_df["low"].iloc[k]) for k in range(i + 1, i + 4)]
            if cand_low <= min(left_lows) and cand_low < min(right_lows):
                after_slice = work_df.iloc[i + 1:]
                min_after_low2 = float(after_slice["low"].min())
                max_after_high2 = float(after_slice["high"].max())
                reversal_bounce_pct = (max_after_high2 - cand_low) / max(cand_low, 1.0)
                if min_after_low2 >= cand_low and reversal_bounce_pct >= 0.0015:
                    dist_pct = abs(current_price - cand_low) / max(current_price, 1.0)
                    if dist_pct <= 0.0080:
                        res["swing_lows"].append({
                            "price": round(cand_low, 1),
                            "time": cand_time,
                            "reversal_pct": round(reversal_bounce_pct * 100.0, 2)
                        })

        res["swing_highs"] = sorted(res["swing_highs"], key=lambda x: x["price"])
        res["swing_lows"] = sorted(res["swing_lows"], key=lambda x: x["price"], reverse=True)
        return res
    except Exception:
        return res

# --- CESTA B: KOMBINOVANÝ MOZEK ARGON 4 AI AGENTA (5 KAPITOL V PYTHONU + GOOGLE AI STUDIO) ---
def evaluate_argon4_ai_agent(
    setup_type,
    group_id,
    side,
    entry_px,
    tab_sl_px,
    tab_tp1_px,
    tab_tp2_px,
    tab_tp_mode,
    liq_btc,
    mtf_vp,
    trend_3h,
    left_swings,
    flow_data
):
    is_long = (str(side).lower() == "buy")
    dir_label = "LONG" if is_long else "SHORT"
    entry_px = float(entry_px)
    tab_sl_px = float(tab_sl_px)
    tab_tp1_px = float(tab_tp1_px)
    tab_tp2_px = float(tab_tp2_px)

    reasons = []
    warnings = []
    score = 80

    # --- 1. KAPITOLA 1 & 2: VYHODNOCENÍ VP (1H/3H/6H) + TREND VS. CHOP (3H) ---
    regime = trend_3h.get("regime", "CHOP")
    confluences = mtf_vp.get("confluences", [])
    all_vp_levels = mtf_vp.get("all_levels", [])

    # Zjistíme, zda Entry leží přímo NA některém VP levelu nebo konfluenci (do 0.08 %)
    entry_on_vp = False
    entry_vp_names = []
    for cf in confluences:
        if (cf["low"] - entry_px * 0.0008) <= entry_px <= (cf["high"] + entry_px * 0.0008):
            entry_on_vp = True
            entry_vp_names.append(f"KONFLUENCE({cf['labels']} @ {cf['mid']:.0f}$)")
    if not entry_on_vp:
        for lvl in all_vp_levels:
            if abs(lvl["price"] - entry_px) / max(entry_px, 1.0) <= 0.0008:
                entry_on_vp = True
                entry_vp_names.append(f"{lvl['label']}({lvl['price']:.0f}$)")

    if entry_on_vp:
        score += 8
        reasons.append(f"Vstup leží přímo na VP hladině ({', '.join(entry_vp_names[:2])}) -> OBA SMĚRY POVOLENY.")

    # Kontrola obchodu proti silnému trendu
    if (is_long and regime == "STRONG_BEAR") or (not is_long and regime == "STRONG_BULL"):
        if group_id == "MICRO" and not entry_on_vp and setup_type == "SETUP_1":
            score -= 30
            warnings.append(f"⛔ Malý MICRO {dir_label} přímo proti rozjetému {regime} bez opory VP.")
        else:
            score -= 12
            warnings.append(f"⚠️ Obchod {dir_label} jde proti {regime} -> nutný konzervativní TP.")
    elif (is_long and "BULL" in regime) or (not is_long and "BEAR" in regime):
        score += 6
        reasons.append(f"Obchod {dir_label} je v souladu s 3H režimem {regime}.")

    # --- 2. KAPITOLA 3: KONTROLA STOP-LOSSU PODLE SKUTEČNÝCH LEVÝCH SWINGŮ (+0.05 % POLŠTÁŘ) ---
    rec_sl_px = tab_sl_px
    swing_note = "Tabulkový SL je čistý (žádný ohrožující levý swing)."
    buffer_pct = 0.0005  # +0.05 % (~35 $) ochranný polštář za swingem

    if is_long:
        # Pro LONG hledáme nevybrané Swing Lows mezi Entry a (tab_sl_px - 0.08 %)
        relevant_lows = [
            s for s in left_swings.get("swing_lows", [])
            if (tab_sl_px * (1.0 - 0.0008)) <= s["price"] <= (entry_px * 0.9995)
        ]
        if relevant_lows:
            lowest_sw = min(relevant_lows, key=lambda x: x["price"])
            safe_sl = round(lowest_sw["price"] * (1.0 - buffer_pct), 0)
            if safe_sl < tab_sl_px:
                rec_sl_px = safe_sl
                swing_note = f"Posun SL z {tab_sl_px:.0f}$ na {rec_sl_px:.0f}$ (-0.05% pod levý Swing Low {lowest_sw['price']:.0f}$ z {lowest_sw['time']})."
                warnings.append(f"🛡️ SL v magnetu levého Swing Low ({lowest_sw['price']:.0f}$) -> doporučen posun SL na {rec_sl_px:.0f}$.")
    else:
        # Pro SHORT hledáme nevybrané Swing Highs mezi Entry a (tab_sl_px + 0.08 %)
        relevant_highs = [
            s for s in left_swings.get("swing_highs", [])
            if (entry_px * 1.0005) <= s["price"] <= (tab_sl_px * (1.0 + 0.0008))
        ]
        if relevant_highs:
            highest_sw = max(relevant_highs, key=lambda x: x["price"])
            safe_sl = round(highest_sw["price"] * (1.0 + buffer_pct), 0)
            if safe_sl > tab_sl_px:
                rec_sl_px = safe_sl
                swing_note = f"Posun SL z {tab_sl_px:.0f}$ na {rec_sl_px:.0f}$ (+0.05% nad levý Swing High {highest_sw['price']:.0f}$ z {highest_sw['time']})."
                warnings.append(f"🛡️ SL v magnetu levého Swing High ({highest_sw['price']:.0f}$) -> doporučen posun SL na {rec_sl_px:.0f}$.")

    # Kontrola maximálního natažení SL (aby nepřekročil 0.42 % od vstupu)
    sl_dist_pct = abs(entry_px - rec_sl_px) / max(entry_px, 1.0)
    if sl_dist_pct > 0.0042:
        score -= 20
        warnings.append(f"⚠️ Bezpečný SL za levým swingem je příliš daleko ({sl_dist_pct*100:.2f}% od vstupu).")

    # --- 3. KAPITOLA 4: POSOUZENÍ TAKE-PROFITU, PŘEKÁŽEK NA TRASE A REÁLNÉHO RRR ---
    rec_tp1_px = tab_tp1_px
    rec_tp2_px = tab_tp2_px
    rec_tp_mode = tab_tp_mode
    tp_note = f"Cesta k likvidačnímu magnetu ({tab_tp2_px:.0f}$) je volná."

    # Najdeme případné konfluenční zdi v cestě mezi Entry (s odstupem 0.08 %) a TP2
    obstacles_in_way = []
    for cf in confluences:
        if is_long and (entry_px * 1.0008) < cf["low"] < tab_tp2_px:
            obstacles_in_way.append(cf)
        elif not is_long and tab_tp2_px < cf["high"] < (entry_px * 0.9992):
            obstacles_in_way.append(cf)

    is_counter_trend = (is_long and "BEAR" in regime) or (not is_long and "BULL" in regime)

    if obstacles_in_way:
        if is_long:
            first_obs = min(obstacles_in_way, key=lambda x: x["low"])
            obs_front_px = round(first_obs["low"] - 8.0, 0)
        else:
            first_obs = max(obstacles_in_way, key=lambda x: x["high"])
            obs_front_px = round(first_obs["high"] + 8.0, 0)

        if regime == "CHOP" or is_counter_trend:
            # V CHOPu nebo proti trendu má konfluence VP 100% váhu jako zeď -> zkrátíme TP před zeď
            rec_tp2_px = obs_front_px
            if is_long and rec_tp1_px > rec_tp2_px:
                rec_tp1_px = rec_tp2_px
                rec_tp_mode = "HALF_LIQ"
            elif not is_long and rec_tp1_px < rec_tp2_px:
                rec_tp1_px = rec_tp2_px
                rec_tp_mode = "HALF_LIQ"
            tp_note = f"V {regime} leží v cestě zeď {first_obs['labels']} ({first_obs['mid']:.0f}$) -> TP zkrácen před zeď na {rec_tp2_px:.0f}$ ({rec_tp_mode})."
            warnings.append(f"🧱 Konfluence VP ({first_obs['labels']}) stojí v cestě -> doporučen TP před zdí @ {rec_tp2_px:.0f}$.")
        else:
            tp_note = f"Jdeme s trendem ({regime}), menší VP překážku ({first_obs['labels']}) ignorujeme a cílíme likvidace."

    # Pokud jsme v CHOPu nebo proti trendu a původní režim byl FULL_LIQ, přepneme na jistější SPLIT_50_50
    if (regime == "CHOP" or is_counter_trend) and rec_tp_mode == "FULL_LIQ":
        rec_tp_mode = "SPLIT_50_50"
        reasons.append(f"V režimu {regime} upraven exit z FULL_LIQ na bezpečnější SPLIT_50_50.")

    # Výpočet reálného RRR vůči upravenému SL a efektivnímu TP
    risk_usd = max(abs(entry_px - rec_sl_px), 1.0)
    if rec_tp_mode == "HALF_LIQ":
        eff_tp_px = rec_tp1_px
    elif rec_tp_mode == "FULL_LIQ":
        eff_tp_px = rec_tp2_px
    else:
        eff_tp_px = (rec_tp1_px + rec_tp2_px) / 2.0

    reward_usd = abs(eff_tp_px - entry_px)
    real_rrr = round(reward_usd / risk_usd, 2)

    if real_rrr < 1.50:
        score -= 28
        warnings.append(f"⛔ Reálné RRR po započtení swingů/zdí kleslo na {real_rrr:.2f} (minimum je 1.50).")
    elif real_rrr >= 2.20:
        score += 7
        reasons.append(f"Výborné reálné RRR {real_rrr:.2f} (SL {rec_sl_px:.0f}$ -> TP {eff_tp_px:.0f}$).")

    # --- 4. KAPITOLA 5: KONTROLA SPOT CVD A OPEN INTERESTU (OI) ---
    box_spot = float(flow_data.get("box_spot", 0.0) or 0.0)
    spot_25m = float(flow_data.get("spot_25m", 0.0) or 0.0)
    oi_25m = float(flow_data.get("oi_25m", 0.0) or 0.0)
    flow_note = "Spot CVD a OI jsou neutrální."

    if setup_type == "SETUP_1":
        # Soulad / divergence Spotu
        if (is_long and (box_spot >= 10.0 or spot_25m >= 15.0)) or (not is_long and (box_spot <= -10.0 or spot_25m <= -15.0)):
            score += 8
            flow_note = f"Skutečný Spot potvrzuje {dir_label} (Box Spot {box_spot:+.1f} BTC, 25M Spot {spot_25m:+.1f} BTC)."
            reasons.append(flow_note)
        elif (is_long and (box_spot <= -25.0 and spot_25m <= -25.0)) or (not is_long and (box_spot >= 25.0 and spot_25m >= 25.0)):
            score -= 18
            flow_note = f"⚠️ Silný Spot jde proti našemu {dir_label} (Box Spot {box_spot:+.1f} BTC, 25M Spot {spot_25m:+.1f} BTC)."
            warnings.append(flow_note)

        # Open Interest palivo v krabici
        if oi_25m >= 30.0:
            score += 6
            reasons.append(f"Rostoucí OI (+{oi_25m:.0f} BTC / 25m) = uvěznění obchodníci v krabici (palivo pro průraz).")
        elif oi_25m <= -35.0 and rec_tp_mode == "FULL_LIQ":
            rec_tp_mode = "SPLIT_50_50"
            warnings.append(f"OI za 25m klesá ({oi_25m:+.0f} BTC) -> snížen cíl z FULL_LIQ na SPLIT_50_50.")
    else:
        flow_note = f"Setup 2 SFP (OI 25M: {oi_25m:+.1f} BTC | Spot 25M: {spot_25m:+.1f} BTC)."

    score = max(0, min(100, int(round(score))))
    verdict = "SCHVÁLENO" if (score >= 62 and real_rrr >= 1.45) else "VAROVÁNÍ / ZAMÍTNUTO"

    # --- 5. CESTA B: DOTAZ DO GOOGLE AI STUDIA (GEMINI API) PRO KONTEXTOVÝ POSUDEK HRANIČNÍCH SITUACÍ ---
    ai_studio_comment = ""
    gemini_key = OKX_SECRETS.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            prompt_payload = {
                "setup": f"{setup_type} ({group_id}) {dir_label}",
                "entry_px": round(entry_px, 1),
                "tabular_sl": round(tab_sl_px, 1),
                "recommended_sl": round(rec_sl_px, 1),
                "tabular_tp1_tp2": [round(tab_tp1_px, 1), round(tab_tp2_px, 1)],
                "recommended_tp1_tp2": [round(rec_tp1_px, 1), round(rec_tp2_px, 1)],
                "recommended_tp_mode": rec_tp_mode,
                "real_rrr": real_rrr,
                "liq_cluster_btc": round(float(liq_btc), 1),
                "trend_3h": trend_3h.get("summary_txt", ""),
                "vp_1h_3h_6h_confluences": [c["labels"] + f"@{c['mid']}" for c in confluences[:4]],
                "entry_on_vp_level": entry_on_vp,
                "untested_left_swings": left_swings,
                "order_flow": flow_data,
                "python_score": score,
                "python_verdict": verdict
            }
            sys_prompt = (
                "Jsi Argon 4 AI Pit Boss pro intradenní scalping BTC na OKX. "
                "Dostáváš přesně spočítaná čísla z 5 kapitol (1H/3H/6H VP konfluence, 3H Trend vs Chop [Přímka vs Klikatice], "
                "nevybrané levé swingy s +0.05% polštářem pro SL, Likvidační magnety + překážky pro TP, reálné RRR a Spot/OI). "
                "Napiš stručný, jasný verdikt v češtině (max 2 krátké věty): posuď hraniční situace (např. zda silné Order Flow vyvažuje RRR těsně pod 1.50) "
                "a potvrď doporučený SL, TP a režim exitu."
            )
            for model_name in ["gemini-2.5-flash", "gemini-2.0-flash"]:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                req_json = {
                    "contents": [{"parts": [{"text": f"{sys_prompt}\n\nDATA OBCHODU:\n{json.dumps(prompt_payload, ensure_ascii=False)}"}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 180}
                }
                r_gem = requests.post(api_url, json=req_json, timeout=3.5)
                if r_gem.status_code == 200:
                    cand_list = r_gem.json().get("candidates", [])
                    if cand_list:
                        parts_list = cand_list[0].get("content", {}).get("parts", [])
                        if parts_list:
                            ai_studio_comment = str(parts_list[0].get("text", "")).strip().replace("\n", " ")
                            break
        except Exception:
            pass

    if not ai_studio_comment:
        if warnings:
            ai_studio_comment = " | ".join(warnings[:2])
        elif reasons:
            ai_studio_comment = " | ".join(reasons[:2])
        else:
            ai_studio_comment = "Setup splňuje parametry všech 5 kapitol Argon 4."

    verdict_icon = "🟢" if verdict == "SCHVÁLENO" else "🔴"
    telegram_block = (
        f"🧠 <b>ARGON 4 AI POSUDEK (Stínový poradce do 20. 11.):</b>\n"
        f"• Verdikt: {verdict_icon} <b>{verdict}</b> (Skóre: <b>{score}/100</b> | Reálné RRR: <b>{real_rrr:.2f}</b>)\n"
        f"• 3H Režim: <b>{trend_3h.get('summary_txt', '-')}</b>\n"
        f"• Posudek SL (Levé swingy): <b>{rec_sl_px:.0f}$</b> ({swing_note})\n"
        f"• Posudek TP & VP: <b>TP1 {rec_tp1_px:.0f}$ / TP2 {rec_tp2_px:.0f}$ [{rec_tp_mode}]</b> ({tp_note})\n"
        f"• Komentář AI: <i>{ai_studio_comment}</i>"
    )

    return {
        "verdict": verdict,
        "score": score,
        "real_rrr": real_rrr,
        "rec_sl_px": int(round(rec_sl_px)),
        "rec_tp1_px": int(round(rec_tp1_px)),
        "rec_tp2_px": int(round(rec_tp2_px)),
        "rec_tp_mode": rec_tp_mode,
        "swing_note": swing_note,
        "tp_note": tp_note,
        "flow_note": flow_note,
        "ai_comment": ai_studio_comment,
        "telegram_block": telegram_block
    }

# --- AUTOMATICKÝ EXEKUTOR PRO OKX (2000 USD POZICE, 10x ISOLATED, MAKER POST-ONLY VSTUP + TP PLÁN) ---
def execute_okx_maker_order(side, limit_price, tp1_price, tp2_price, sl_pct=DEFAULT_SL_PCT, tp_mode="SPLIT_50_50", setup_tag="SETUP"):
    if not OKX_SECRETS.get("ENABLED"):
        return "ℹ️ AI_TRADING_ENABLED je vypnuto (Pouze Telegram signál)."

    api_key = OKX_SECRETS.get("API_KEY", "")
    sec_key = OKX_SECRETS.get("SECRET_KEY", "")
    passphrase = OKX_SECRETS.get("PASSPHRASE", "")
    inst_id = OKX_SECRETS.get("INST_ID", "BTC-USD_UM_XPERP-310404")
    ct_val = OKX_SECRETS.get("CONTRACT_BTC", 0.0001)

    if not api_key or not sec_key or not passphrase:
        return "⚠️ Chybí OKX API klíče ve Streamlit Secrets."

    base_url = "https://eea.okx.com"

    try:
        # KROK 0: PŘÍSNÁ KONTROLA - MAXIMÁLNĚ 1 OTEVŘENÝ OBCHOD NEBO ČEKAJÍCÍ VSTUPNÍ LIMITKA NA BURZE
        if has_okx_open_or_pending_trade():
            with ENGINE["lock"]:
                ENGINE["has_open_or_pending"] = True
            return "🛡️ OKX EXEKUTOR: Na burze již běží aktivní obchod nebo čekající vstupní limitka – nový příkaz zablokován."

        # 1. Kontrola Best Bid / Best Ask, aby Post-Only Maker příkaz nebyl burzou zamítnut
        tk_res = requests.get(f"{base_url}/api/v5/market/ticker?instId={inst_id}", timeout=4).json()
        tk_data = tk_res.get("data", [])
        if tk_data:
            best_bid = float(tk_data[0].get("bidPx") or limit_price)
            best_ask = float(tk_data[0].get("askPx") or limit_price)
            if side == "buy" and limit_price >= best_ask:
                limit_price = best_bid - 1.0
            elif side == "sell" and limit_price <= best_bid:
                limit_price = best_ask + 1.0

        # 2. Nastavení páky 10x Isolated
        lev_body = json.dumps({
            "instId": inst_id,
            "lever": "10",
            "mgnMode": "isolated"
        })
        _okx_signed_request("POST", "/api/v5/account/set-leverage", lev_body)

        # 3. Výpočet celkového počtu kontraktů pro pozici 2 000 USD (marže 200 USD při 10x)
        btc_amount = POSITION_SIZE_USD / float(limit_price)
        total_contracts = max(2, int(round(btc_amount / ct_val)))

        px_str = str(int(round(limit_price)))
        tp1_int = int(round(tp1_price))
        tp2_int = int(round(tp2_price))

        if side == "buy":
            sl_px = int(round(limit_price * (1.0 - float(sl_pct))))
            close_side = "sell"
        else:
            sl_px = int(round(limit_price * (1.0 + float(sl_pct))))
            close_side = "buy"

        # 4. Odeslání 1x Post-Only Maker vstupu na celých 2 000 USD s připojeným Market SL
        order_payload = {
            "instId": inst_id,
            "tdMode": "isolated",
            "side": side,
            "ordType": "post_only",
            "px": px_str,
            "sz": str(total_contracts),
            "attachAlgoOrds": [{
                "slTriggerPx": str(sl_px),
                "slOrdPx": "-1",
                "slTriggerPxType": "last"
            }]
        }

        res_ord = _okx_signed_request("POST", "/api/v5/trade/order", json.dumps(order_payload))
        ok_ord = str(res_ord.get("code")) == "0"

        if ok_ord:
            ord_id = res_ord["data"][0].get("ordId", "")
            c1 = total_contracts // 2
            c2 = total_contracts - c1
            new_plan = {
                "active": True,
                "tp_mode": tp_mode,
                "close_side": close_side,
                "entry_px": float(px_str),
                "tp1_px": tp1_int,
                "tp2_px": tp2_int,
                "ct1": c1,
                "ct2": c2,
                "tp_placed": False
            }
            with ENGINE["lock"]:
                ENGINE["tp_plan"] = new_plan
                ENGINE["has_open_or_pending"] = True
                hist = _load_alert_history()
                hist["ACTIVE_TP_PLAN"] = dict(new_plan)
                _save_alert_history(hist)

            if tp_mode == "FULL_LIQ":
                tp_desc = f"100% Plný Liq ({tp2_int}$)"
            elif tp_mode == "HALF_LIQ":
                tp_desc = f"100% 1/2 Liq ({tp1_int}$)"
            else:
                tp_desc = f"50/50 Maker TP1: {tp1_int}$ & TP2: {tp2_int}$ + Auto BE"

            return f"🤖 <b>OKX EXEKUTOR: ZADAL MAKER VSTUP (2 000 USD | 10x)</b>\nID: {ord_id} ({total_contracts} ks @ {px_str}$ | SL {sl_pct*100:.2f}%: {sl_px}$ | Režim TP: {tp_desc} | Expirace vstupu: 15m)"
        else:
            err = res_ord.get("msg", "") or str(res_ord)
            return f"⚠️ <b>OKX EXEKUTOR CHYBA:</b> {err}"
    except Exception as e:
        return f"⚠️ <b>OKX EXEKUTOR VÝJIMKA:</b> {str(e)}"
# === KONEC ČÁSTI 2 ===# === ZAČÁTEK ČÁSTI 3 ===

# --- KONFIGURACE STRÁNKY A STYLŮ ---
st.set_page_config(page_title="OKX OrderFlow & Argon 4 AI Terminal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #e2e8f0; }
    .metric-box {
        background: #131822;
        border: 1px solid #262f40;
        border-radius: 8px;
        padding: 12px 15px;
        margin-bottom: 10px;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# --- STAHOVÁNÍ SVÍČEK, OBCHODŮ (CVD) A OPEN INTERESTU Z OKX ---
def fetch_okx_candles(inst_id, bar="5m", limit=300):
    base_url = "https://eea.okx.com"
    try:
        url = f"{base_url}/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
        r = requests.get(url, timeout=4).json()
        data = r.get("data", [])
        if not data:
            return pd.DataFrame()
        rows = []
        for item in data:
            ts_ms = int(item[0])
            dt_cet = datetime.fromtimestamp(ts_ms / 1000.0, tz=ZoneInfo("Europe/Prague"))
            vol_val = float(item[6]) if len(item) > 6 and float(item[6] or 0) > 0 else float(item[5] or 0.0)
            rows.append({
                "ts": ts_ms,
                "dt": dt_cet,
                "dt_str": dt_cet.strftime("%H:%M"),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "vol_btc": vol_val
            })
        df = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()

def update_realtime_orderflow(fut_inst="BTC-USDT-SWAP", spot_inst="BTC-USDT"):
    base_url = "https://eea.okx.com"
    ct_btc = 0.01  # BTC-USDT-SWAP = 0.01 BTC / kontrakt

    # 1. Futures Trades -> 5m a 1m CVD buckety
    try:
        r_fut = requests.get(f"{base_url}/api/v5/market/trades?instId={fut_inst}&limit=100", timeout=3.5).json()
        fut_trades = r_fut.get("data", [])
        if fut_trades:
            with ENGINE["lock"]:
                last_id = ENGINE["last_fut_trade_id"]
                new_trades = []
                for t in fut_trades:
                    tid = str(t.get("tradeId", ""))
                    if last_id is not None and tid <= str(last_id):
                        continue
                    new_trades.append(t)
                if fut_trades:
                    ENGINE["last_fut_trade_id"] = str(fut_trades[0].get("tradeId", ""))

                for t in new_trades:
                    ts_ms = int(t.get("ts", 0))
                    b5 = (ts_ms // 300000) * 300000
                    b1 = (ts_ms // 60000) * 60000
                    sz_btc = float(t.get("sz", 0.0)) * ct_btc
                    delta = sz_btc if str(t.get("side", "")).lower() == "buy" else -sz_btc
                    ENGINE["fut_buckets"][b5] = ENGINE["fut_buckets"].get(b5, 0.0) + delta
                    ENGINE["fut_1m_buckets"][b1] = ENGINE["fut_1m_buckets"].get(b1, 0.0) + delta
    except Exception:
        pass

    # 2. Spot Trades -> 5m a 1m Spot CVD buckety
    try:
        r_spot = requests.get(f"{base_url}/api/v5/market/trades?instId={spot_inst}&limit=100", timeout=3.5).json()
        spot_trades = r_spot.get("data", [])
        if spot_trades:
            with ENGINE["lock"]:
                last_sid = ENGINE["last_spot_trade_id"]
                new_strades = []
                for t in spot_trades:
                    tid = str(t.get("tradeId", ""))
                    if last_sid is not None and tid <= str(last_sid):
                        continue
                    new_strades.append(t)
                if spot_trades:
                    ENGINE["last_spot_trade_id"] = str(spot_trades[0].get("tradeId", ""))

                for t in new_strades:
                    ts_ms = int(t.get("ts", 0))
                    b5 = (ts_ms // 300000) * 300000
                    b1 = (ts_ms // 60000) * 60000
                    sz_btc = float(t.get("sz", 0.0))
                    delta = sz_btc if str(t.get("side", "")).lower() == "buy" else -sz_btc
                    ENGINE["spot_buckets"][b5] = ENGINE["spot_buckets"].get(b5, 0.0) + delta
                    ENGINE["spot_1m_buckets"][b1] = ENGINE["spot_1m_buckets"].get(b1, 0.0) + delta
    except Exception:
        pass

    # 3. Live Open Interest (v BTC)
    try:
        r_oi = requests.get(f"{base_url}/api/v5/public/open-interest?instType=SWAP&instId={fut_inst}", timeout=3.5).json()
        oi_data = r_oi.get("data", [])
        if oi_data:
            oi_btc = float(oi_data[0].get("oiCcy", 0.0) or 0.0)
            now_b5 = (int(time.time() * 1000) // 300000) * 300000
            if oi_btc > 0:
                with ENGINE["lock"]:
                    ENGINE["last_oi_btc"] = oi_btc
                    if now_b5 not in ENGINE["oi_start_map"]:
                        ENGINE["oi_start_map"][now_b5] = oi_btc
                    ENGINE["oi_live_delta"][now_b5] = oi_btc - ENGINE["oi_start_map"][now_b5]
    except Exception:
        pass

def enrich_candles_with_orderflow(df, is_1m=False):
    if df is None or df.empty:
        return df
    df = df.copy()
    fut_col = []
    spot_col = []
    oi_col = []

    with ENGINE["lock"]:
        f_map = dict(ENGINE["fut_1m_buckets"] if is_1m else ENGINE["fut_buckets"])
        s_map = dict(ENGINE["spot_1m_buckets"] if is_1m else ENGINE["spot_buckets"])
        oi_map = dict(ENGINE["oi_live_delta"])

    for _, row in df.iterrows():
        ts_val = int(row["ts"])
        body_diff = float(row["close"]) - float(row["open"])
        hl_range = max(float(row["high"]) - float(row["low"]), 0.5)
        vol_b = float(row.get("vol_btc", 0.0) or 0.0)
        est_cvd = (body_diff / hl_range) * vol_b * 0.55

        f_val = f_map.get(ts_val, est_cvd)
        s_val = s_map.get(ts_val, est_cvd * 0.35)
        o_val = oi_map.get(ts_val, 0.0)

        fut_col.append(round(float(f_val), 2))
        spot_col.append(round(float(s_val), 2))
        oi_col.append(round(float(o_val), 2))

    df["fut_cvd"] = fut_col
    df["spot_cvd"] = spot_col
    df["oi_delta"] = oi_col
    return df

# --- VÝPOČET LIKVIDAČNÍCH MAGNETŮ (HORNÍ A DOLNÍ LIKVIDAČNÍ ZÓNA V BTC) ---
def compute_liquidation_magnets(df_5m, current_price):
    if df_5m is None or len(df_5m) < 20:
        return {
            "upper_p": round(current_price * 1.006, 0),
            "upper_btc": 50.0,
            "lower_p": round(current_price * 0.994, 0),
            "lower_btc": 50.0
        }

    last_closed_ts = int(df_5m["ts"].iloc[-2]) if len(df_5m) >= 2 else int(df_5m["ts"].iloc[-1])
    with ENGINE["lock"]:
        cached = dict(ENGINE["liq_cache"])
    if cached.get("candle_ts") == last_closed_ts and cached.get("upper_p", 0) > 0:
        return cached

    recent = df_5m.tail(72)
    upper_candidates = []
    lower_candidates = []

    for _, row in recent.iterrows():
        h_px = float(row["high"])
        l_px = float(row["low"])
        v_btc = max(float(row.get("vol_btc", 10.0) or 10.0), 5.0)
        # Odhad pákových likvidací 25x–100x nad vrcholy a pod dny
        if h_px > current_price * 1.0015 and h_px <= current_price * 1.0150:
            upper_candidates.append((h_px * 1.0012, v_btc * 0.45))
        if l_px < current_price * 0.9985 and l_px >= current_price * 0.9850:
            lower_candidates.append((l_px * 0.9988, v_btc * 0.45))

    if upper_candidates:
        best_u = max(upper_candidates, key=lambda x: x[1])
        upper_p = round(best_u[0], 0)
        upper_btc = round(sum(x[1] for x in upper_candidates if abs(x[0] - best_u[0]) / current_price <= 0.0020), 1)
    else:
        upper_p = round(current_price * 1.0055, 0)
        upper_btc = 65.0

    if lower_candidates:
        best_l = min(lower_candidates, key=lambda x: abs(x[0] - current_price))
        lower_p = round(best_l[0], 0)
        lower_btc = round(sum(x[1] for x in lower_candidates if abs(x[0] - best_l[0]) / current_price <= 0.0020), 1)
    else:
        lower_p = round(current_price * 0.9945, 0)
        lower_btc = 65.0

    new_liq = {
        "candle_ts": last_closed_ts,
        "upper_p": upper_p,
        "upper_btc": upper_btc,
        "lower_p": lower_p,
        "lower_btc": lower_btc
    }
    with ENGINE["lock"]:
        ENGINE["liq_cache"] = dict(new_liq)
    return new_liq

# --- HLAVNÍ BĚH TERMINÁLU: NAČTENÍ DAT A AKTIVNÍ SPRÁVA POZIC ---
manage_active_okx_lifecycle()
update_realtime_orderflow()

df_5m_raw = fetch_okx_candles("BTC-USDT-SWAP", bar="5m", limit=300)
df_1m_raw = fetch_okx_candles("BTC-USDT-SWAP", bar="1m", limit=120)

df_5m = enrich_candles_with_orderflow(df_5m_raw, is_1m=False)
df_1m = enrich_candles_with_orderflow(df_1m_raw, is_1m=True)

if df_5m is None or df_5m.empty or len(df_5m) < 30:
    st.warning("⏳ Stahuji data z OKX... Prosím vyčkejte několik sekund.")
    st.stop()

current_price = float(df_5m["close"].iloc[-1])

# --- VÝPOČET VŠECH 5 KAPITOL PRO ARGON 4 AI AGENTA ---
mtf_vp = compute_scalp_mtf_vp(df_1m, df_5m, current_price)
trend_3h = compute_3h_trend_chop_info(df_5m)
left_swings = detect_untested_left_swings(df_5m, current_price)
liq_info = compute_liquidation_magnets(df_5m, current_price)

upper_liq_p = float(liq_info["upper_p"])
upper_liq_btc = float(liq_info["upper_btc"])
lower_liq_p = float(liq_info["lower_p"])
lower_liq_btc = float(liq_info["lower_btc"])

# --- MATICE ORDER FLOW 5M / 25M / 45M ---
fut_5m = float(df_5m["fut_cvd"].iloc[-1])
fut_25m = float(df_5m["fut_cvd"].tail(5).sum())
fut_45m = float(df_5m["fut_cvd"].tail(9).sum())

spot_5m = float(df_5m["spot_cvd"].iloc[-1])
spot_25m = float(df_5m["spot_cvd"].tail(5).sum())
spot_45m = float(df_5m["spot_cvd"].tail(9).sum())

oi_5m = float(df_5m["oi_delta"].iloc[-1])
oi_25m = float(df_5m["oi_delta"].tail(5).sum())
oi_45m = float(df_5m["oi_delta"].tail(9).sum())

flow_matrix_data = {
    "fut_5m": round(fut_5m, 1),
    "fut_25m": round(fut_25m, 1),
    "fut_45m": round(fut_45m, 1),
    "spot_5m": round(spot_5m, 1),
    "spot_25m": round(spot_25m, 1),
    "spot_45m": round(spot_45m, 1),
    "oi_5m": round(oi_5m, 1),
    "oi_25m": round(oi_25m, 1),
    "oi_45m": round(oi_45m, 1),
    "box_spot": 0.0
}

# ==============================================================================
# DETEKCE SETUPU 1: 5M KRABICE (MICRO / MEDIUM / MACRO) -> 1M CVD PRŮRAZ -> PULLBACK
# ==============================================================================
s1_status_text = "Skenuji 5M krabice (Micro / Medium / Macro)..."
s1_triggered_now = False

closed_5m = df_5m.iloc[:-1].copy()
closed_1m = df_1m.iloc[:-1].copy() if (df_1m is not None and len(df_1m) > 5) else pd.DataFrame()

# Definice 3 skupin Setupu 1
S1_GROUPS = [
    {"id": "MACRO",  "name": "SKUPINA 1 (MACRO)",  "candles": 9, "mins": 45, "max_spread": 0.0040, "min_cvd": 150.0, "pb_pct": 0.0012, "sl_pct": 0.0030, "tp_mode": "FULL_LIQ"},
    {"id": "MEDIUM", "name": "SKUPINA 2 (MEDIUM)", "candles": 6, "mins": 30, "max_spread": 0.0030, "min_cvd": 100.0, "pb_pct": 0.0010, "sl_pct": 0.0020, "tp_mode": "SPLIT_50_50"},
    {"id": "MICRO",  "name": "SKUPINA 3 (MICRO)",  "candles": 3, "mins": 15, "max_spread": 0.0020, "min_cvd": 50.0,  "pb_pct": 0.0005, "sl_pct": 0.0010, "tp_mode": "HALF_LIQ"}
]

with ENGINE["lock"]:
    s1_mem = dict(ENGINE["s1_memory"])

# Vypršení 20min paměti Setupu 1
if s1_mem.get("active") and (time.time() - float(s1_mem.get("locked_at_sec", 0.0))) > S1_MEMORY_TTL_SEC:
    with ENGINE["lock"]:
        ENGINE["s1_memory"]["active"] = False
    s1_mem["active"] = False

# KROK 1: Hledání uzavřené 5M krabice + NÁSLEDUJÍCÍ uzavřené 1M potvrzovací svíčky
if not s1_mem.get("active") and len(closed_5m) >= 12 and not closed_1m.empty:
    last_1m_row = closed_1m.iloc[-1]
    last_1m_ts = int(last_1m_row["ts"])
    last_1m_cvd = float(last_1m_row["fut_cvd"])
    last_1m_close = float(last_1m_row["close"])

    for grp in S1_GROUPS:
        n_c = grp["candles"]
        box_df = closed_5m.tail(n_c)
        box_end_ts = int(box_df["ts"].iloc[-1]) + 300000  # Čas uzavření poslední 5M svíčky krabice

        # Chronologie: 1M potvrzovací svíčka musí skončit až PO uzavření 5M krabice
        if (last_1m_ts + 60000) < box_end_ts:
            continue

        box_high = float(box_df["high"].max())
        box_low = float(box_df["low"].min())
        box_mid = (box_high + box_low) / 2.0
        box_spread = (box_high - box_low) / max(box_low, 1.0)
        box_cvd_sum = float(box_df["fut_cvd"].sum())
        box_spot_sum = float(box_df["spot_cvd"].sum())

        if box_spread <= grp["max_spread"] and abs(box_cvd_sum) >= grp["min_cvd"]:
            # Divergenční absorpce v krabici + 1M potvrzení (+/- 12 BTC)
            # Pokud v krabici nakupovali (CVD > 0), ale cena neprorazila nahoru a 1M svíčka prodává (<= -12 BTC) -> SHORT
            # Pokud v krabici prodávali (CVD < 0), ale cena nepropadla dolů a 1M svíčka nakupuje (>= +12 BTC) -> LONG
            direction = ""
            if box_cvd_sum >= grp["min_cvd"] and last_1m_cvd <= -12.0:
                direction = "SHORT"
                extreme_p = float(last_1m_row["low"])
            elif box_cvd_sum <= -grp["min_cvd"] and last_1m_cvd >= 12.0:
                direction = "LONG"
                extreme_p = float(last_1m_row["high"])

            if direction:
                new_mem = {
                    "active": True,
                    "v14_chrono_ok": True,
                    "direction": direction,
                    "group_id": grp["id"],
                    "setup_label": f"SETUP 1 ({grp['name']}) – {direction}",
                    "header_text": f"{grp['name']} ({grp['mins']}m box)",
                    "confirm_1m_ts": last_1m_ts,
                    "locked_at_sec": time.time(),
                    "zone_extreme_p": extreme_p,
                    "box_mid": box_mid,
                    "pb_pct": grp["pb_pct"],
                    "sl_pct": grp["sl_pct"],
                    "tp_mode": grp["tp_mode"],
                    "box_mins": grp["mins"],
                    "box_spread_pct": round(box_spread * 100.0, 2),
                    "box_cvd": round(box_cvd_sum, 1),
                    "box_spot": round(box_spot_sum, 1)
                }
                with ENGINE["lock"]:
                    ENGINE["s1_memory"] = dict(new_mem)
                s1_mem = dict(new_mem)
                break

# KROK 2: Pokud máme uzamčený Setup 1, hlídáme 1M strukturu a Pullback pro vstup
if s1_mem.get("active"):
    direction = s1_mem["direction"]
    grp_id = s1_mem["group_id"]
    pb_pct = float(s1_mem["pb_pct"])
    sl_pct = float(s1_mem["sl_pct"])
    tp_mode = s1_mem["tp_mode"]
    ext_p = float(s1_mem["zone_extreme_p"])

    if direction == "LONG":
        if current_price > ext_p:
            ext_p = current_price
            with ENGINE["lock"]:
                ENGINE["s1_memory"]["zone_extreme_p"] = ext_p
        target_entry_px = round(ext_p * (1.0 - pb_pct), 0)
        tab_sl_px = round(target_entry_px * (1.0 - sl_pct), 0)
        tab_tp1_px = round(target_entry_px + (upper_liq_p - target_entry_px) * 0.5, 0)
        tab_tp2_px = round(upper_liq_p, 0)
        liq_target_btc = upper_liq_btc
        side_str = "buy"
        pb_reached = (current_price <= target_entry_px * 1.0004)
    else:
        if current_price < ext_p:
            ext_p = current_price
            with ENGINE["lock"]:
                ENGINE["s1_memory"]["zone_extreme_p"] = ext_p
        target_entry_px = round(ext_p * (1.0 + pb_pct), 0)
        tab_sl_px = round(target_entry_px * (1.0 + sl_pct), 0)
        tab_tp1_px = round(target_entry_px - (target_entry_px - lower_liq_p) * 0.5, 0)
        tab_tp2_px = round(lower_liq_p, 0)
        liq_target_btc = lower_liq_btc
        side_str = "sell"
        pb_reached = (current_price >= target_entry_px * 0.9996)

    s1_status_text = (
        f"⏳ {s1_mem['setup_label']} | Čekám na Pullback @ {target_entry_px:.0f}$ "
        f"(Aktuálně: {current_price:.0f}$ | Box CVD: {s1_mem['box_cvd']:+.1f} BTC)"
    )

    cd_rem = get_setup_cooldown_remaining(f"S1_{grp_id}", lock_duration=1800)
    if pb_reached and cd_rem == 0 and not ENGINE.get("has_open_or_pending", False):
        flow_s1 = dict(flow_matrix_data)
        flow_s1["box_spot"] = float(s1_mem.get("box_spot", 0.0))

        # --- SPUŠTĚNÍ MOZKU ARGON 4 AI AGENTA (VŠECH 5 KAPITOL + GOOGLE AI STUDIO) ---
        ai_eval = evaluate_argon4_ai_agent(
            setup_type="SETUP_1",
            group_id=grp_id,
            side=side_str,
            entry_px=target_entry_px,
            tab_sl_px=tab_sl_px,
            tab_tp1_px=tab_tp1_px,
            tab_tp2_px=tab_tp2_px,
            tab_tp_mode=tp_mode,
            liq_btc=liq_target_btc,
            mtf_vp=mtf_vp,
            trend_3h=trend_3h,
            left_swings=left_swings,
            flow_data=flow_s1
        )

        # Varianta A (do pátku 20. 11.): OKX exekutor obchod normálně zadá podle tabulky,
        # ale do Telegramu i CSV zapíše kompletní stínový posudek Argon 4 AI Agenta!
        exec_msg = execute_okx_maker_order(
            side=side_str,
            limit_price=target_entry_px,
            tp1_price=tab_tp1_px,
            tp2_price=tab_tp2_px,
            sl_pct=sl_pct,
            tp_mode=tp_mode,
            setup_tag=f"S1_{grp_id}"
        )

        vp_1h = mtf_vp["1h"]
        vp_3h = mtf_vp["3h"]
        vp_6h = mtf_vp["6h"]
        conf_str = ", ".join(f"{c['labels']}@{c['mid']:.0f}$" for c in mtf_vp["confluences"][:3]) or "Žádná v okolí"

        msg_body = (
            f"📊 <b>{s1_mem['setup_label']}</b>\n"
            f"• Krabice ({s1_mem['box_mins']}m): Rozpětí <b>{s1_mem['box_spread_pct']:.2f}%</b> | "
            f"Box CVD: <b>{s1_mem['box_cvd']:+.1f} BTC</b> | Box Spot (bg): <b>{s1_mem['box_spot']:+.1f} BTC</b>\n"
            f"• Vstup (Maker): <b>{target_entry_px:.0f}$</b> | Tabulkový SL ({sl_pct*100:.2f}%): <b>{tab_sl_px:.0f}$</b>\n"
            f"• Cíle (Liq {liq_target_btc:.0f} BTC): TP1 <b>{tab_tp1_px:.0f}$</b> | TP2 <b>{tab_tp2_px:.0f}$</b> ({tp_mode})\n"
            f"• VP (1H/3H/6H): 1H POC <b>{vp_1h['poc']:.0f}$</b> | 3H POC <b>{vp_3h['poc']:.0f}$</b> | 6H POC <b>{vp_6h['poc']:.0f}$</b>\n"
            f"• Konfluence VP: <b>{conf_str}</b>\n\n"
            f"{ai_eval['telegram_block']}\n\n"
            f"{exec_msg}"
        )

        if odesli_upozorneni(f"S1_{grp_id}", s1_mem["setup_label"], msg_body, lock_duration=1800, force=True):
            s1_triggered_now = True
            with ENGINE["lock"]:
                ENGINE["s1_memory"]["active"] = False

            log_weekly_trade_event({
                "timestamp": datetime.now(ZoneInfo("Europe/Prague")).strftime("%Y-%m-%d %H:%M:%S"),
                "setup": f"S1_{grp_id}",
                "direction": direction,
                "entry_px": target_entry_px,
                "tab_sl_px": tab_sl_px,
                "tab_tp1_px": tab_tp1_px,
                "tab_tp2_px": tab_tp2_px,
                "tp_mode": tp_mode,
                "box_cvd": s1_mem["box_cvd"],
                "box_spot": s1_mem["box_spot"],
                "trend_3h": trend_3h.get("state", ""),
                "vp_confluences": conf_str,
                "ai_verdict": ai_eval["verdict"],
                "ai_score": ai_eval["score"],
                "ai_real_rrr": ai_eval["real_rrr"],
                "ai_rec_sl": ai_eval["rec_sl_px"],
                "ai_rec_tp1": ai_eval["rec_tp1_px"],
                "ai_rec_tp2": ai_eval["rec_tp2_px"],
                "ai_rec_tp_mode": ai_eval["rec_tp_mode"],
                "ai_comment": ai_eval["ai_comment"]
            })
# === KONEC ČÁSTI 3 ===# === ZAČÁTEK ČÁSTI 4 ===

# ==============================================================================
# DETEKCE SETUPU 2: SFP (SWEEP KLÍČOVÉ HLADINY + UZAVŘENÍ ZPĚT) + OI (C1/C2) + CVD (D)
# ==============================================================================
s2_status_text = "Skenuji 5M SFP na klíčových hladinách (6H/12H/24H High-Low & 3H/6H VP)..."
s2_triggered_now = False
s2_diag = {
    "level_name": "-",
    "level_px": 0.0,
    "sfp_dir": "NONE",
    "c1_oi_sum": 0.0,
    "c2_oi_diff": 0.0,
    "c_passed": False,
    "c_reason": "-",
    "d_cvd_diff": 0.0,
    "d_passed": False,
    "spot_bg": 0.0
}

if len(closed_5m) >= 30:
    last_c = closed_5m.iloc[-1]
    prev_c = closed_5m.iloc[-2]
    prior_slice = closed_5m.iloc[:-1]

    # Klíčové hladiny pro SFP (předchozích 6H, 12H, 24H High/Low + 3H/6H VAH a VAL)
    h_6h = float(prior_slice.tail(72)["high"].max())
    l_6h = float(prior_slice.tail(72)["low"].min())
    h_12h = float(prior_slice.tail(144)["high"].max())
    l_12h = float(prior_slice.tail(144)["low"].min())
    h_24h = float(prior_slice.tail(288)["high"].max())
    l_24h = float(prior_slice.tail(288)["low"].min())

    upper_sfp_levels = [
        ("24H_HIGH", h_24h),
        ("12H_HIGH", h_12h),
        ("6H_HIGH", h_6h),
        ("6H_VAH", float(mtf_vp["6h"]["vah"])),
        ("3H_VAH", float(mtf_vp["3h"]["vah"]))
    ]
    lower_sfp_levels = [
        ("24H_LOW", l_24h),
        ("12H_LOW", l_12h),
        ("6H_LOW", l_6h),
        ("6H_VAL", float(mtf_vp["6h"]["val"])),
        ("3H_VAL", float(mtf_vp["3h"]["val"]))
    ]

    c_high = float(last_c["high"])
    c_low = float(last_c["low"])
    c_close = float(last_c["close"])
    c_open = float(last_c["open"])

    p_high = float(prev_c["high"])
    p_low = float(prev_c["low"])
    p_close = float(prev_c["close"])

    # Bod C: Open Interest anomálie na posledních 2 uzavřených 5M svíčkách
    # C1: Součet OI změny <= -50 BTC (výplach / likvidace pozic)
    # C2: Rozdíl OI mezi svíčkami >= 30 BTC (absorpční skok)
    oi_curr = float(last_c["oi_delta"])
    oi_prev = float(prev_c["oi_delta"])
    c1_sum = round(oi_curr + oi_prev, 1)
    c2_diff = round(abs(oi_curr - oi_prev), 1)
    c_ok = (c1_sum <= -50.0) or (c2_diff >= 30.0)
    if c1_sum <= -50.0 and c2_diff >= 30.0:
        c_reason_str = f"C1 ({c1_sum:+.1f} BTC) + C2 (Δ {c2_diff:.1f} BTC)"
    elif c1_sum <= -50.0:
        c_reason_str = f"C1 Výplach OI ({c1_sum:+.1f} BTC <= -50)"
    elif c2_diff >= 30.0:
        c_reason_str = f"C2 Skok OI (Δ {c2_diff:.1f} BTC >= 30)"
    else:
        c_reason_str = f"C nesplněno (Součet {c1_sum:+.1f} | Δ {c2_diff:.1f} BTC)"

    # Bod D: Futures CVD anomálie / obratová divergence mezi svíčkami (>= 45 BTC změna nebo silná absorpce)
    cvd_curr = float(last_c["fut_cvd"])
    cvd_prev = float(prev_c["fut_cvd"])
    d_diff = round(abs(cvd_curr - cvd_prev), 1)
    d_ok = (d_diff >= 45.0) or (abs(cvd_curr) >= 45.0)

    spot_curr = float(last_c["spot_cvd"])

    # Kontrola SHORT SFP (knot nad klíčovou horní hladinu + close zpět pod hladinou)
    matched_s2_dir = ""
    matched_lvl_name = ""
    matched_lvl_px = 0.0
    sweep_extreme_px = 0.0

    for lname, lpx in upper_sfp_levels:
        if lpx <= 0:
            continue
        # Buď poslední svíčka vybrala hladinu knotem a zavřela pod ní, nebo 2-svíčkové SFP
        swept_now = (c_high > lpx * 1.0002) and (c_close < lpx)
        swept_2c = (p_high > lpx * 1.0002) and (c_close < lpx) and (c_close < c_open)
        if swept_now or swept_2c:
            matched_s2_dir = "SHORT"
            matched_lvl_name = lname
            matched_lvl_px = round(lpx, 1)
            sweep_extreme_px = max(c_high, p_high)
            break

    # Kontrola LONG SFP (knot pod klíčovou spodní hladinu + close zpět nad hladinou)
    if not matched_s2_dir:
        for lname, lpx in lower_sfp_levels:
            if lpx <= 0:
                continue
            swept_now = (c_low < lpx * 0.9998) and (c_close > lpx)
            swept_2c = (p_low < lpx * 0.9998) and (c_close > lpx) and (c_close > c_open)
            if swept_now or swept_2c:
                matched_s2_dir = "LONG"
                matched_lvl_name = lname
                matched_lvl_px = round(lpx, 1)
                sweep_extreme_px = min(c_low, p_low)
                break

    s2_diag = {
        "level_name": matched_lvl_name or "Žádný SFP sweep",
        "level_px": matched_lvl_px,
        "sfp_dir": matched_s2_dir or "NONE",
        "c1_oi_sum": c1_sum,
        "c2_oi_diff": c2_diff,
        "c_passed": c_ok,
        "c_reason": c_reason_str,
        "d_cvd_diff": d_diff,
        "d_passed": d_ok,
        "spot_bg": round(spot_curr, 1)
    }

    if matched_s2_dir:
        s2_status_text = (
            f"🔎 Detekován SFP {matched_s2_dir} na {matched_lvl_name} ({matched_lvl_px:.0f}$) | "
            f"Bod C (OI): {'✅' if c_ok else '❌'} ({c_reason_str}) | "
            f"Bod D (CVD Δ {d_diff:.1f} BTC): {'✅' if d_ok else '❌'}"
        )

        cd_s2 = get_setup_cooldown_remaining("S2_MAIN", lock_duration=1800)
        if c_ok and d_ok and cd_s2 == 0 and not ENGINE.get("has_open_or_pending", False):
            # Parametry pro Setup 2: SL 0.30 %, TP 50/50 (SPLIT_50_50), Spot CVD nikdy neblokuje
            s2_entry_px = round(current_price, 0)
            s2_sl_pct = DEFAULT_SL_PCT  # 0.30 %
            s2_tp_mode = "SPLIT_50_50"

            if matched_s2_dir == "LONG":
                s2_side = "buy"
                s2_sl_px = round(s2_entry_px * (1.0 - s2_sl_pct), 0)
                s2_tp1_px = round(s2_entry_px + (upper_liq_p - s2_entry_px) * 0.5, 0)
                s2_tp2_px = round(upper_liq_p, 0)
                s2_liq_btc = upper_liq_btc
            else:
                s2_side = "sell"
                s2_sl_px = round(s2_entry_px * (1.0 + s2_sl_pct), 0)
                s2_tp1_px = round(s2_entry_px - (s2_entry_px - lower_liq_p) * 0.5, 0)
                s2_tp2_px = round(lower_liq_p, 0)
                s2_liq_btc = lower_liq_btc

            flow_s2 = dict(flow_matrix_data)
            flow_s2["box_spot"] = round(spot_curr, 1)

            # --- SPUŠTĚNÍ MOZKU ARGON 4 AI AGENTA PRO SETUP 2 ---
            ai_eval_s2 = evaluate_argon4_ai_agent(
                setup_type="SETUP_2",
                group_id="SFP_MACRO",
                side=s2_side,
                entry_px=s2_entry_px,
                tab_sl_px=s2_sl_px,
                tab_tp1_px=s2_tp1_px,
                tab_tp2_px=s2_tp2_px,
                tab_tp_mode=s2_tp_mode,
                liq_btc=s2_liq_btc,
                mtf_vp=mtf_vp,
                trend_3h=trend_3h,
                left_swings=left_swings,
                flow_data=flow_s2
            )

            exec_msg_s2 = execute_okx_maker_order(
                side=s2_side,
                limit_price=s2_entry_px,
                tp1_price=s2_tp1_px,
                tp2_price=s2_tp2_px,
                sl_pct=s2_sl_pct,
                tp_mode=s2_tp_mode,
                setup_tag="S2_SFP"
            )

            vp_1h = mtf_vp["1h"]
            vp_3h = mtf_vp["3h"]
            vp_6h = mtf_vp["6h"]
            conf_str = ", ".join(f"{c['labels']}@{c['mid']:.0f}$" for c in mtf_vp["confluences"][:3]) or "Žádná v okolí"

            msg_s2 = (
                f"🔥 <b>SETUP 2 (SFP + OI/CVD ANOMÁLIE) – {matched_s2_dir}</b>\n"
                f"• Hladina SFP: <b>{matched_lvl_name} ({matched_lvl_px:.0f}$)</b> | Extrém knotu: <b>{sweep_extreme_px:.0f}$</b>\n"
                f"• Bod C (OI): <b>{c_reason_str}</b>\n"
                f"• Bod D (Futures CVD): <b>Δ {d_diff:.1f} BTC</b> (Aktuální svíčka: {cvd_curr:+.1f} BTC | Spot bg: {spot_curr:+.1f} BTC)\n"
                f"• Vstup (Maker): <b>{s2_entry_px:.0f}$</b> | Tabulkový SL (0.30%): <b>{s2_sl_px:.0f}$</b>\n"
                f"• Cíle (50/50 Liq {s2_liq_btc:.0f} BTC): TP1 <b>{s2_tp1_px:.0f}$</b> | TP2 <b>{s2_tp2_px:.0f}$</b>\n"
                f"• VP (1H/3H/6H): 1H POC <b>{vp_1h['poc']:.0f}$</b> | 3H POC <b>{vp_3h['poc']:.0f}$</b> | 6H POC <b>{vp_6h['poc']:.0f}$</b>\n"
                f"• Konfluence VP: <b>{conf_str}</b>\n\n"
                f"{ai_eval_s2['telegram_block']}\n\n"
                f"{exec_msg_s2}"
            )

            if odesli_upozorneni("S2_MAIN", f"SETUP 2 (SFP {matched_lvl_name}) – {matched_s2_dir}", msg_s2, lock_duration=1800, force=True):
                s2_triggered_now = True
                log_weekly_trade_event({
                    "timestamp": datetime.now(ZoneInfo("Europe/Prague")).strftime("%Y-%m-%d %H:%M:%S"),
                    "setup": f"S2_SFP_{matched_lvl_name}",
                    "direction": matched_s2_dir,
                    "entry_px": s2_entry_px,
                    "tab_sl_px": s2_sl_px,
                    "tab_tp1_px": s2_tp1_px,
                    "tab_tp2_px": s2_tp2_px,
                    "tp_mode": s2_tp_mode,
                    "box_cvd": cvd_curr,
                    "box_spot": spot_curr,
                    "trend_3h": trend_3h.get("state", ""),
                    "vp_confluences": conf_str,
                    "ai_verdict": ai_eval_s2["verdict"],
                    "ai_score": ai_eval_s2["score"],
                    "ai_real_rrr": ai_eval_s2["real_rrr"],
                    "ai_rec_sl": ai_eval_s2["rec_sl_px"],
                    "ai_rec_tp1": ai_eval_s2["rec_tp1_px"],
                    "ai_rec_tp2": ai_eval_s2["rec_tp2_px"],
                    "ai_rec_tp_mode": ai_eval_s2["rec_tp_mode"],
                    "ai_comment": ai_eval_s2["ai_comment"]
                })

# ==============================================================================
# ŽIVÁ DIAGNOSTIKA ARGON 4 AI AGENTA PRO OBRAZOVKU (SIMULACE LONG & SHORT NA AKTUÁLNÍ CENĚ)
# ==============================================================================
def build_live_ai_screen_preview():
    # Abychom neplýtvali voláním externího Gemini API každých pár sekund při běžném překreslení obrazovky,
    # živý náhled na obrazovce počítá okamžitou 5kapitolovou matematiku a volání Google AI Studia
    # se provádí při reálném signálu nebo po kliknutí na tlačítko "Otestovat Google AI Studio (Argon 4)".
    saved_key = OKX_SECRETS.get("GEMINI_API_KEY", "")
    OKX_SECRETS["GEMINI_API_KEY"] = ""
    try:
        long_prev = evaluate_argon4_ai_agent(
            setup_type="SETUP_1",
            group_id="MEDIUM",
            side="buy",
            entry_px=current_price,
            tab_sl_px=round(current_price * (1.0 - 0.0020), 0),
            tab_tp1_px=round(current_price + (upper_liq_p - current_price) * 0.5, 0),
            tab_tp2_px=round(upper_liq_p, 0),
            tab_tp_mode="SPLIT_50_50",
            liq_btc=upper_liq_btc,
            mtf_vp=mtf_vp,
            trend_3h=trend_3h,
            left_swings=left_swings,
            flow_data=flow_matrix_data
        )
        short_prev = evaluate_argon4_ai_agent(
            setup_type="SETUP_1",
            group_id="MEDIUM",
            side="sell",
            entry_px=current_price,
            tab_sl_px=round(current_price * (1.0 + 0.0020), 0),
            tab_tp1_px=round(current_price - (current_price - lower_liq_p) * 0.5, 0),
            tab_tp2_px=round(lower_liq_p, 0),
            tab_tp_mode="SPLIT_50_50",
            liq_btc=lower_liq_btc,
            mtf_vp=mtf_vp,
            trend_3h=trend_3h,
            left_swings=left_swings,
            flow_data=flow_matrix_data
        )
    finally:
        OKX_SECRETS["GEMINI_API_KEY"] = saved_key
    return long_prev, short_prev

live_ai_long, live_ai_short = build_live_ai_screen_preview()
# === KONEC ČÁSTI 4 ===# === ZAČÁTEK ČÁSTI 5 ===

# ==============================================================================
# HORNÍ HLAVIČKA TERMINÁLU A OVLÁDACÍ PANEL
# ==============================================================================
now_cet_str = datetime.now(ZoneInfo("Europe/Prague")).strftime("%d.%m.%Y %H:%M:%S")
okx_live_badge = "🟢 AKTIVNÍ (10x Isolated | 2 000 $)" if OKX_SECRETS.get("ENABLED") else "⚪ VYPNUTO (Pouze Telegram)"
gemini_badge = "🟢 PROPOJENO (Google AI Studio)" if OKX_SECRETS.get("GEMINI_API_KEY") else "🟡 LOKÁLNÍ PYTHON REŽIM"

st.markdown(f"""
<div class="metric-box" style="border-left: 4px solid #38bdf8;">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
        <div>
            <span style="font-size:22px; font-weight:800; color:#f8fafc;">⚡ OKX ORDERFLOW & ARGON 4 AI TERMINAL</span>
            <span style="margin-left:12px; font-size:13px; color:#94a3b8;">Čas (Praha): <b>{now_cet_str}</b></span>
        </div>
        <div style="font-size:13px; color:#cbd5e1;">
            OKX Exekutor: <b>{okx_live_badge}</b> &nbsp;|&nbsp; Mozek AI: <b>{gemini_badge}</b>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- HORNÍ METRIKY: CENA, 3H TREND/CHOP, LIKVIDAČNÍ MAGNETY, STAV POZICE ---
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

with col_m1:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:12px; color:#94a3b8;">AKTUÁLNÍ CENA BTC-USDT-SWAP</div>
        <div style="font-size:26px; font-weight:800; color:#38bdf8;">{current_price:,.1f} $</div>
        <div style="font-size:12px; color:#cbd5e1;">1H POC: <b>{mtf_vp['1h']['poc']:,.0f}$</b> | 3H POC: <b>{mtf_vp['3h']['poc']:,.0f}$</b></div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    reg_color = "#f59e0b" if trend_3h["regime"] == "CHOP" else ("#22c55e" if "BULL" in trend_3h["regime"] else "#ef4444")
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:12px; color:#94a3b8;">KAPITOLA 2: 3H TREND vs. CHOP (PŘÍMKA/KLIKATICE)</div>
        <div style="font-size:20px; font-weight:800; color:{reg_color};">{trend_3h['regime']} ({trend_3h['efficiency_pct']:.1f} %)</div>
        <div style="font-size:12px; color:#cbd5e1;">Přímka: <b>{trend_3h['net_move_usd']:.0f}$ ({trend_3h['net_move_pct']:.2f}%)</b> | Klikatice: <b>{trend_3h['total_path_usd']:.0f}$</b></div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:12px; color:#94a3b8;">KAPITOLA 4: LIKVIDAČNÍ MAGNETY</div>
        <div style="font-size:15px; font-weight:700; color:#22c55e;">⬆️ Horní Liq: {upper_liq_p:,.0f} $ ({upper_liq_btc:.0f} BTC)</div>
        <div style="font-size:15px; font-weight:700; color:#ef4444;">⬇️ Dolní Liq: {lower_liq_p:,.0f} $ ({lower_liq_btc:.0f} BTC)</div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    open_flag = ENGINE.get("has_open_or_pending", False)
    pos_txt = "🟠 BĚŽÍ OBCHOD / LIMITKA" if open_flag else "🟢 VOLNO (Čekám na signál)"
    pos_col = "#f97316" if open_flag else "#22c55e"
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:12px; color:#94a3b8;">STAV BURZY OKX & PAMĚTI S1</div>
        <div style="font-size:18px; font-weight:800; color:{pos_col};">{pos_txt}</div>
        <div style="font-size:12px; color:#cbd5e1;">S1 Paměť: <b>{'AKTIVNÍ (' + s1_mem.get('direction','') + ')' if s1_mem.get('active') else 'Klid'}</b></div>
    </div>
    """, unsafe_allow_html=True)

# --- OVLÁDACÍ TLAČÍTKA A DIAGNOSTICKÉ TESTY ---
btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)

with btn_c1:
    auto_refresh = st.checkbox("🔄 Automatický refresh (12 s)", value=True)

with btn_c2:
    if st.button("🧠 Otestovat Argon 4 AI + Telegram", use_container_width=True):
        test_eval = evaluate_argon4_ai_agent(
            setup_type="SETUP_1",
            group_id="MEDIUM",
            side="buy",
            entry_px=current_price,
            tab_sl_px=round(current_price * (1.0 - 0.0020), 0),
            tab_tp1_px=round(current_price + (upper_liq_p - current_price) * 0.5, 0),
            tab_tp2_px=round(upper_liq_p, 0),
            tab_tp_mode="SPLIT_50_50",
            liq_btc=upper_liq_btc,
            mtf_vp=mtf_vp,
            trend_3h=trend_3h,
            left_swings=left_swings,
            flow_data=flow_matrix_data
        )
        test_msg = (
            f"🧪 <b>TESTOVACÍ POSUDEK ARGON 4 AI AGENTA</b>\n"
            f"• Aktuální cena BTC: <b>{current_price:.0f}$</b>\n\n"
            f"{test_eval['telegram_block']}"
        )
        ok_tg = odesli_upozorneni("TEST_AI_BTN", "TEST ARGON 4 AI & TELEGRAM", test_msg, lock_duration=5, force=True)
        if ok_tg:
            st.success("✅ Testovací posudek Argon 4 AI byl úspěšně odeslán na tvůj Telegram!")
        else:
            st.error("⚠️ Odeslání na Telegram selhalo – zkontroluj připojení.")

with btn_c3:
    if st.button("🧹 Resetovat S1 paměť a Cooldowny", use_container_width=True):
        with ENGINE["lock"]:
            ENGINE["s1_memory"]["active"] = False
            _save_alert_history({})
        st.success("✅ Paměť Setupu 1 i všechny cooldowny byly vynulovány.")

with btn_c4:
    if st.button("🔄 Obnovit data hned", use_container_width=True):
        st.rerun()

# ==============================================================================
# SEKCE 1: ŽIVÝ ROZBOR VŠECH 5 KAPITOL ARGON 4 AI AGENTA
# ==============================================================================
st.markdown("### 🧠 Živý Mozek Argon 4 AI Agenta (Kontrola všech 5 kapitol v reálném čase)")

cap_col1, cap_col2, cap_col3 = st.columns(3)

with cap_col1:
    vp1 = mtf_vp["1h"]
    vp3 = mtf_vp["3h"]
    vp6 = mtf_vp["6h"]
    conf_items = mtf_vp.get("confluences", [])
    conf_html = ""
    if conf_items:
        for c in conf_items[:4]:
            conf_html += f"<div style='color:#facc15; font-size:13px;'>🔗 <b>{c['labels']}</b> @ <b>{c['mid']:,.0f} $</b> ({c['low']:,.0f}–{c['high']:,.0f}$)</div>"
    else:
        conf_html = "<div style='color:#94a3b8; font-size:13px;'>Žádná konfluence do 0.10 % v aktuálním okně.</div>"

    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:14px; font-weight:700; color:#38bdf8; margin-bottom:6px;">📂 KAPITOLA 1: 1H / 3H / 6H Volume Profile</div>
        <div style="font-size:13px; color:#e2e8f0; line-height:1.6;">
            • <b>1H VP (60x 1m):</b> VAH {vp1['vah']:,.0f}$ | <b>POC {vp1['poc']:,.0f}$</b> | VAL {vp1['val']:,.0f}$<br>
            • <b>3H VP (36x 5m):</b> VAH {vp3['vah']:,.0f}$ | <b>POC {vp3['poc']:,.0f}$</b> | VAL {vp3['val']:,.0f}$<br>
            • <b>6H VP (72x 5m):</b> VAH {vp6['vah']:,.0f}$ | <b>POC {vp6['poc']:,.0f}$</b> | VAL {vp6['val']:,.0f}$
        </div>
        <hr style="border-color:#262f40; margin:8px 0;">
        <div style="font-size:12px; color:#94a3b8; margin-bottom:4px;">Detekované konfluence (≤ 0.10 %):</div>
        {conf_html}
    </div>
    """, unsafe_allow_html=True)

with cap_col2:
    sh_list = left_swings.get("swing_highs", [])
    sl_list = left_swings.get("swing_lows", [])
    sh_txt = ", ".join(f"<b>{s['price']:,.0f}$</b> ({s['time']} | -{s['reversal_pct']}%)" for s in sh_list[:3]) or "Žádný nevybraný v dosahu"
    sl_txt = ", ".join(f"<b>{s['price']:,.0f}$</b> ({s['time']} | +{s['reversal_pct']}%)" for s in sl_list[:3]) or "Žádný nevybraný v dosahu"

    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:14px; font-weight:700; color:#a855f7; margin-bottom:6px;">📂 KAPITOLA 3: Skutečné nevybrané levé Swingy (3H)</div>
        <div style="font-size:12px; color:#94a3b8;">Podmínka: Lokální extrém + reálný odjezd opačným směrem ≥ 0.15 % + panenská likvidita</div>
        <div style="font-size:13px; color:#e2e8f0; margin-top:6px; line-height:1.6;">
            🔺 <b>Nevybrané Swing Highs (nad cenou):</b><br>{sh_txt}<br>
            🔻 <b>Nevybrané Swing Lows (pod cenou):</b><br>{sl_txt}
        </div>
        <hr style="border-color:#262f40; margin:8px 0;">
        <div style="font-size:12px; color:#cbd5e1;">
            🛡️ <b>Ochranný polštář SL (+0.05 % za swingem):</b><br>
            • Pro případný LONG: <b>{live_ai_long['rec_sl_px']:,.0f} $</b> ({live_ai_long['swing_note']})<br>
            • Pro případný SHORT: <b>{live_ai_short['rec_sl_px']:,.0f} $</b> ({live_ai_short['swing_note']})
        </div>
    </div>
    """, unsafe_allow_html=True)

with cap_col3:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:14px; font-weight:700; color:#22c55e; margin-bottom:6px;">📂 KAPITOLA 4 & 5: Posudek RRR, TP a Order Flow</div>
        <div style="font-size:13px; color:#e2e8f0; line-height:1.55;">
            🟢 <b>Simulace LONG (@ {current_price:,.0f}$):</b><br>
            • Verdikt: <b>{live_ai_long['verdict']}</b> (Skóre {live_ai_long['score']}/100 | RRR: <b>{live_ai_long['real_rrr']:.2f}</b>)<br>
            • Doporučený TP: <b>{live_ai_long['rec_tp1_px']:,.0f}$ / {live_ai_long['rec_tp2_px']:,.0f}$ [{live_ai_long['rec_tp_mode']}]</b><br>
            <span style="font-size:12px; color:#94a3b8;">{live_ai_long['ai_comment']}</span>
        </div>
        <hr style="border-color:#262f40; margin:8px 0;">
        <div style="font-size:13px; color:#e2e8f0; line-height:1.55;">
            🔴 <b>Simulace SHORT (@ {current_price:,.0f}$):</b><br>
            • Verdikt: <b>{live_ai_short['verdict']}</b> (Skóre {live_ai_short['score']}/100 | RRR: <b>{live_ai_short['real_rrr']:.2f}</b>)<br>
            • Doporučený TP: <b>{live_ai_short['rec_tp1_px']:,.0f}$ / {live_ai_short['rec_tp2_px']:,.0f}$ [{live_ai_short['rec_tp_mode']}]</b><br>
            <span style="font-size:12px; color:#94a3b8;">{live_ai_short['ai_comment']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- MATICE ORDER FLOW (5M / 25M / 45M) ---
st.markdown("#### 📊 Kapitola 5: Živá Matice Order Flow (Futures CVD, Spot CVD na pozadí & Open Interest)")
mf_col1, mf_col2, mf_col3 = st.columns(3)

with mf_col1:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:13px; font-weight:700; color:#38bdf8;">⚡ FUTURES CVD (Pákoví obchodníci)</div>
        <div style="font-size:14px; margin-top:4px;">
            • <b>5M:</b> {fut_5m:+.1f} BTC &nbsp;|&nbsp; <b>25M:</b> {fut_25m:+.1f} BTC &nbsp;|&nbsp; <b>45M:</b> {fut_45m:+.1f} BTC
        </div>
    </div>
    """, unsafe_allow_html=True)

with mf_col2:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:13px; font-weight:700; color:#facc15;">🏦 SPOT CVD (Skutečné nákupy/prodeje na pozadí)</div>
        <div style="font-size:14px; margin-top:4px;">
            • <b>5M:</b> {spot_5m:+.1f} BTC &nbsp;|&nbsp; <b>25M:</b> {spot_25m:+.1f} BTC &nbsp;|&nbsp; <b>45M:</b> {spot_45m:+.1f} BTC
        </div>
    </div>
    """, unsafe_allow_html=True)

with mf_col3:
    st.markdown(f"""
    <div class="metric-box">
        <div style="font-size:13px; font-weight:700; color:#a855f7;">🧲 OPEN INTEREST DELTA (Nové / Uzavřené pozice)</div>
        <div style="font-size:14px; margin-top:4px;">
            • <b>5M:</b> {oi_5m:+.1f} BTC &nbsp;|&nbsp; <b>25M:</b> {oi_25m:+.1f} BTC &nbsp;|&nbsp; <b>45M:</b> {oi_45m:+.1f} BTC
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# SEKCE 2: DETAILNÍ DIAGNOSTIKA SETUPU 1 A SETUPU 2
# ==============================================================================
st.markdown("### 🎯 Stav Detektorů Setupu 1 (Krabice) a Setupu 2 (SFP)")
st_col1, st_col2 = st.columns(2)

with st_col1:
    rows_s1_diag = []
    for grp in S1_GROUPS:
        n_c = grp["candles"]
        sub_b = closed_5m.tail(n_c)
        sp_pct = ((float(sub_b["high"].max()) - float(sub_b["low"].min())) / max(float(sub_b["low"].min()), 1.0)) * 100.0
        cvd_s = float(sub_b["fut_cvd"].sum())
        sp_s = float(sub_b["spot_cvd"].sum())
        sp_ok = sp_pct <= (grp["max_spread"] * 100.0)
        cvd_ok = abs(cvd_s) >= grp["min_cvd"]
        cd_s = get_setup_cooldown_remaining(f"S1_{grp['id']}", lock_duration=1800)
        rows_s1_diag.append({
            "Skupina": grp["name"],
            "Okno": f"{grp['mins']}m ({n_c} sv.)",
            "Rozpětí": f"{sp_pct:.2f}% / {grp['max_spread']*100:.2f}% {'✅' if sp_ok else '❌'}",
            "Box Futures CVD": f"{cvd_s:+.1f} / ±{grp['min_cvd']:.0f} BTC {'✅' if cvd_ok else '❌'}",
            "Box Spot (bg)": f"{sp_s:+.1f} BTC",
            "SL / Režim TP": f"{grp['sl_pct']*100:.2f}% / {grp['tp_mode']}",
            "Cooldown": f"{cd_s}s" if cd_s > 0 else "🟢 Ready"
        })
    st.markdown(f"**📦 SETUP 1 (5M Krabice -> 1M průraz ±12 BTC -> Pullback):** `{s1_status_text}`")
    st.dataframe(pd.DataFrame(rows_s1_diag), use_container_width=True, hide_index=True)

with st_col2:
    cd_s2_rem = get_setup_cooldown_remaining("S2_MAIN", lock_duration=1800)
    st.markdown(f"**🔥 SETUP 2 (5M SFP Sweep + Bod C OI + Bod D CVD):** `{s2_status_text}`")
    s2_table = pd.DataFrame([
        {"Parametr": "Testovaná SFP hladina", "Aktuální hodnota": f"{s2_diag['level_name']} ({s2_diag['level_px']:,.0f}$)", "Stav": "✅ Sweep" if s2_diag["sfp_dir"] != "NONE" else "⏳ Čeká na sweep"},
        {"Parametr": "Směr SFP obratu", "Aktuální hodnota": s2_diag["sfp_dir"], "Stav": "🟢 Aktivní" if s2_diag["sfp_dir"] != "NONE" else "-"},
        {"Parametr": "Bod C (OI: C1 ≤ -50 nebo C2 Δ ≥ 30 BTC)", "Aktuální hodnota": s2_diag["c_reason"], "Stav": "✅ Splněno" if s2_diag["c_passed"] else "❌ Nesplněno"},
        {"Parametr": "Bod D (Futures CVD změna ≥ 45 BTC)", "Aktuální hodnota": f"Δ {s2_diag['d_cvd_diff']:.1f} BTC", "Stav": "✅ Splněno" if s2_diag["d_passed"] else "❌ Nesplněno"},
        {"Parametr": "Spot CVD na pozadí (informativní)", "Aktuální hodnota": f"{s2_diag['spot_bg']:+.1f} BTC (neblokuje S2)", "Stav": f"Cooldown: {cd_s2_rem}s" if cd_s2_rem > 0 else "🟢 Ready"}
    ])
    st.dataframe(s2_table, use_container_width=True, hide_index=True)

# ==============================================================================
# SEKCE 3: INTERAKTIVNÍ PLOTLY GRAFY (5M HLAVNÍ GRAF + 1M DETAILNÍ GRAF)
# ==============================================================================
st.markdown("### 📈 Interaktivní Grafy s Hladinami Argon 4 (1H/3H/6H VP, Levé Swingy & Likvidace)")
g_col1, g_col2 = st.columns([3, 2])

with g_col1:
    plot_5m = df_5m.tail(72).copy()
    fig5 = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(
            "5M BTC-USDT-SWAP (Posledních 6 hodin) + 1H/3H/6H POC & Likvidační magnety",
            "5M Futures CVD (modrá) vs. Spot CVD na pozadí (žlutá)",
            "5M Open Interest Delta (BTC)"
        )
    )

    fig5.add_trace(go.Candlestick(
        x=plot_5m["dt_str"],
        open=plot_5m["open"],
        high=plot_5m["high"],
        low=plot_5m["low"],
        close=plot_5m["close"],
        name="5M Cena"
    ), row=1, col=1)

    # Zakreslení 1H, 3H a 6H POC hladin
    for tf_lbl, px_val, col_hex in [
        ("1H POC", mtf_vp["1h"]["poc"], "#38bdf8"),
        ("3H POC", mtf_vp["3h"]["poc"], "#facc15"),
        ("6H POC", mtf_vp["6h"]["poc"], "#a855f7"),
        ("Horní Liq", upper_liq_p, "#22c55e"),
        ("Dolní Liq", lower_liq_p, "#ef4444")
    ]:
        if px_val > 0:
            fig5.add_hline(
                y=px_val, line_dash="dot", line_color=col_hex,
                annotation_text=f"{tf_lbl}: {px_val:,.0f}$",
                annotation_position="top right", row=1, col=1
            )

    # Zakreslení Futures CVD a Spot CVD
    fig5.add_trace(go.Bar(
        x=plot_5m["dt_str"], y=plot_5m["fut_cvd"],
        name="Futures CVD", marker_color="#38bdf8"
    ), row=2, col=1)
    fig5.add_trace(go.Scatter(
        x=plot_5m["dt_str"], y=plot_5m["spot_cvd"],
        mode="lines+markers", name="Spot CVD (bg)",
        line=dict(color="#facc15", width=2)
    ), row=2, col=1)

    # Zakreslení OI Delta
    fig5.add_trace(go.Bar(
        x=plot_5m["dt_str"], y=plot_5m["oi_delta"],
        name="OI Delta", marker_color="#a855f7"
    ), row=3, col=1)

    fig5.update_layout(
        height=640, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(orientation="h", y=1.02, x=0)
    )
    st.plotly_chart(fig5, use_container_width=True)

with g_col2:
    plot_1m = df_1m.tail(60).copy() if (df_1m is not None and not df_1m.empty) else pd.DataFrame()
    if not plot_1m.empty:
        fig1 = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.65, 0.35],
            subplot_titles=(
                "1M Detail struktury a Pullbacku (Posledních 60 minut)",
                "1M Futures CVD (průrazový práh ±12 BTC)"
            )
        )
        fig1.add_trace(go.Candlestick(
            x=plot_1m["dt_str"],
            open=plot_1m["open"],
            high=plot_1m["high"],
            low=plot_1m["low"],
            close=plot_1m["close"],
            name="1M Cena"
        ), row=1, col=1)

        if mtf_vp["1h"]["poc"] > 0:
            fig1.add_hline(
                y=mtf_vp["1h"]["poc"], line_dash="dash", line_color="#38bdf8",
                annotation_text=f"1H POC {mtf_vp['1h']['poc']:,.0f}$", row=1, col=1
            )

        fig1.add_trace(go.Bar(
            x=plot_1m["dt_str"], y=plot_1m["fut_cvd"],
            name="1M Futures CVD", marker_color="#22c55e"
        ), row=2, col=1)
        fig1.add_hline(y=12.0, line_dash="dot", line_color="#22c55e", row=2, col=1)
        fig1.add_hline(y=-12.0, line_dash="dot", line_color="#ef4444", row=2, col=1)

        fig1.update_layout(
            height=640, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=35, b=10),
            legend=dict(orientation="h", y=1.02, x=0)
        )
        st.plotly_chart(fig1, use_container_width=True)

# ==============================================================================
# SEKCE 4: TÝDENNÍ DENÍK OBCHODŮ A STÍNOVÝCH POSUDKŮ ARGON 4 AI (CSV EXPORT DO 20. 11.)
# ==============================================================================
st.markdown("### 📓 Týdenní Deník Obchodů a Posudků Argon 4 AI Agenta (Porovnání do pátku 20. 11.)")
weekly_logs = load_weekly_trade_logs()

if weekly_logs:
    df_logs = pd.DataFrame(weekly_logs)
    st.dataframe(df_logs.iloc[::-1], use_container_width=True, hide_index=True)
    csv_bytes = df_logs.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 Stáhnout kompletní deník obchodů + AI posudků (CSV)",
        data=csv_bytes,
        file_name=f"okx_argon4_trades_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )
else:
    st.info("Zatím nebyl zaznamenán žádný obchod v novém logu. Jakmile přijde Setup 1 nebo Setup 2, zapíše se sem jak reálný obchod, tak posudek Argon 4 AI Agenta.")

# --- AUTOMATICKÝ REFRESH STRÁNKY KAŽDÝCH 12 SEKUND ---
if auto_refresh:
    components.html(
        """
        <script>
            setTimeout(function() {
                window.parent.location.reload();
            }, 12000);
        </script>
        """,
        height=0
    )
# === KONEC ČÁSTI 5 ===
