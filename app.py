# === ZAČÁTEK ČÁSTI 1 ===
import os
import csv
import hmac
import json
import time
import math
import base64
import hashlib
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st

# ==============================================================================
# KONFIGURACE TERMINÁLU: ARGON 4 BOSS MODE v19.1
# Strategie: Čistý Setup 1 (MEDIUM + MACRO) | Trend: CHOP + WITH_TREND
# Výstup: 100% pozice na pevný Maker TP = 2.3x SL (bez 50/50, bez Auto-BE)
# Provoz: 24/7 NONSTOP | Testovací období do neděle 6. 12. 2026
# ==============================================================================

APP_VERSION = "v19.1"
OKX_PRIVATE_BASE_URL = "https://eea.okx.com"
OKX_PUBLIC_BASE_URL = "https://www.okx.com"
OKX_INST_ID = "BTC-USD_UM_XPERP-310404"
OKX_CT_VAL = 0.0001          # 1 kontrakt = 0.0001 BTC
OKX_LEVERAGE = 10
OKX_MARGIN_MODE = "isolated"

POSITION_SIZE_USD = 500.0
FIXED_TP_SL_MULT = 2.30      # Pevný 100% cíl = 2.3x SL
MAKER_FEE_RATE = 0.0002      # 0.02 % Maker
TAKER_FEE_RATE = 0.0005      # 0.05 % Taker (Market SL)

S1_MEMORY_TTL_SEC = 1800     # 30 minut platnost uzamčené krabice
S1_COOLDOWN_SEC = 3600       # 1H zámek po exekuci Setupu 1
ENTRY_ORDER_TIMEOUT_SEC = 300          # 5 minut timeout na nevyplněnou vstupní limitku
MAX_MISSED_BREAKOUT_PCT = 0.0050       # Cena > 0.50 % mimo box = ujetý vlak (skip)
BOX_INVALIDATION_PCT = 0.0015          # Cena > 0.15 % proti nám = absorpce padla
SCAN_INTERVAL_SEC = 8        # Cyklus skeneru na pozadí (vteřiny)

GROUP_RANK = {
    "MEDIUM": 2,
    "MACRO": 3,
}

SL_BANDS = {
    "MEDIUM": (0.0025, 0.0030),  # 0.25 % – 0.30 %
    "MACRO":  (0.0035, 0.0045),  # 0.35 % – 0.45 %
}

CSV_LOG_PATH = "argon4_v19_1_trades.csv"
CSV_COLUMNS = [
    "timestamp", "version", "session_tag", "setup", "group", "direction",
    "position_usd", "entry", "sl", "sl_pct", "tp", "tp_pct",
    "raw_rrr", "real_net_rrr", "pb_pct",
    "box_mins", "box_body_spread_pct", "box_low", "box_high", "box_mid",
    "box_cvd", "box_spot_bg",
    "trend_regime", "trend_alignment", "trend_3h_6h_detail", "spot_3h_6h",
    "cvd_5m_25m_45m", "spot_5m_25m_45m", "oi_5m_25m_45m",
    "vp_3h_vah_poc_val", "vp_6h_vah_poc_val", "vp_confluences_3h_6h",
    "vp_obstacles_to_tp", "agent_status", "ai_verdict", "ai_score", "ai_comment",
    "entry_mode", "entry_1m_delta_state"
]


# ==============================================================================
# SECRETS & NASTAVENÍ (PODPORA ALIASŮ I VNOŘENÝCH SEKCÍ V STREAMLIT SECRETS)
# ==============================================================================
def get_secret_val(keys, default=""):
    from collections.abc import Mapping
    if isinstance(keys, str):
        keys = (keys,)
    try:
        for k in keys:
            if k in st.secrets:
                val = st.secrets[k]
                if val is not None and not isinstance(val, Mapping) and str(val).strip() != "":
                    return str(val).strip()
        for sec_key in st.secrets:
            sub = st.secrets[sec_key]
            if isinstance(sub, Mapping):
                for k in keys:
                    if k in sub and sub[k] is not None and str(sub[k]).strip() != "":
                        return str(sub[k]).strip()
    except Exception:
        pass
    for k in keys:
        env_val = os.environ.get(k, "")
        if env_val and env_val.strip() != "":
            return env_val.strip()
    return default


def get_bool_secret(keys, default=True):
    raw = str(get_secret_val(keys, str(default))).strip().lower()
    if raw in ("1", "true", "yes", "on", "ano"):
        return True
    if raw in ("0", "false", "no", "off", "ne"):
        return False
    return bool(default)


def load_runtime_config():
    return {
        "OKX_API_KEY": get_secret_val(("OKX_API_KEY", "API_KEY"), ""),
        "OKX_SECRET_KEY": get_secret_val(("OKX_SECRET_KEY", "SECRET_KEY"), ""),
        "OKX_PASSPHRASE": get_secret_val(("OKX_PASSPHRASE", "PASSPHRASE"), ""),
        "GEMINI_API_KEY": get_secret_val(("GEMINI_API_KEY", "GOOGLE_API_KEY"), ""),
        "TELEGRAM_BOT_TOKEN": get_secret_val(("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN", "TG_TOKEN"), ""),
        "TELEGRAM_CHAT_ID": get_secret_val(("TELEGRAM_CHAT_ID", "CHAT_ID", "TG_CHAT_ID"), ""),
        "AI_TRADING_ENABLED": get_bool_secret(("AI_TRADING_ENABLED",), True),
        "DRY_RUN": get_bool_secret(("DRY_RUN",), False),
        "ARGON_BOSS_MODE": get_bool_secret(("ARGON_BOSS_MODE",), True),
    }


# ==============================================================================
# ČAS A KLASIFIKACE ČASOVÝCH OKEN (PRO VYHODNOCENÍ 6. 12. 2026)
# ==============================================================================
def get_prague_now():
    try:
        return datetime.now(ZoneInfo("Europe/Prague"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=1)))


def classify_prague_session(dt=None):
    if dt is None:
        dt = get_prague_now()
    if dt.weekday() >= 5:
        return "WEEKEND"
    mins = dt.hour * 60 + dt.minute
    if 60 <= mins < 240:
        return "LIQ_ASIA_01_04"
    if 240 <= mins < 480:
        return "OFF_EARLY_04_08"
    if 480 <= mins < 630:
        return "LIQ_LONDON_08_1030"
    if 630 <= mins < 810:
        return "OFF_MIDDAY_1030_1330"
    if 810 <= mins < 1380:
        return "LIQ_NY_1330_2300"
    return "OFF_NIGHT_23_01"


# ==============================================================================
# GLOBÁLNÍ SINGLETON ENGINE (SDÍLENÝ MEZI POZADÍM A UI)
# ==============================================================================
@st.cache_resource
def get_engine():
    return {
        "lock": threading.RLock(),
        "thread_started": False,
        "last_heartbeat": 0.0,
        "last_cycle_error": "",
        "pos_mode_cache": None,  # "net_mode" nebo "long_short_mode"
        "has_open_or_pending": False,
        "active_trade": {
            "active": False,
            "direction": "",
            "group": "",
            "entry_ord_id": "",
            "entry_px": 0.0,
            "sl_px": 0.0,
            "tp_px": 0.0,
            "target_ct": 0,
            "tp_ord_id": "",
            "tp_placed_sz": 0,
            "created_at": 0.0,
            "tp_notified": False,
            "sl_guard_checked": False,
        },
        "s1_memory": {
            "active": False,
            "v19_clean": True,
            "last_eval_box_key": "",
            "direction": "",
            "group_id": "",
            "setup_label": "",
            "header_text": "",
            "confirm_1m_ts": 0,
            "locked_at_sec": 0.0,
            "zone_extreme_p": 0.0,
            "box_low_p": 0.0,
            "box_high_p": 0.0,
            "box_mid": 0.0,
            "pb_pct": 0.0012,
            "sl_pct": 0.0025,
            "box_mins": 0,
            "box_spread_pct": 0.0,
            "box_cvd": 0.0,
            "box_spot": 0.0,
        },
        "cooldowns": {},
        "s1_locked_rank": 0,
        "oi_live_delta": {},
        "oi_last_snapshot": {},
        "trade_flow_1m_fut": {},
        "trade_flow_1m_spot": {},
        "last_trade_id_fut": "",
        "last_trade_id_spot": "",
        "latest_snapshot": {
            "updated_str": "Čekám na první cyklus...",
            "btc_price": 0.0,
            "session_tag": "",
            "s1_status": "Inicializace Setupu 1 (MEDIUM + MACRO)...",
            "agent_status": "Čekám na stav OKX...",
            "vp_3h": {"vah": 0.0, "poc": 0.0, "val": 0.0},
            "vp_6h": {"vah": 0.0, "poc": 0.0, "val": 0.0},
            "trend_regime": "CHOP",
            "trend_detail": "",
            "spot_3h": 0.0,
            "spot_6h": 0.0,
            "flow_metrics": (0.0,) * 9,
            "open_position_info": "Žádná otevřená pozice",
            "pending_order_info": "Žádný čekající příkaz",
            "recent_events": [],
        },
    }


ENGINE = get_engine()


def add_ui_event(text):
    ts_str = get_prague_now().strftime("%H:%M:%S")
    with ENGINE["lock"]:
        ev = ENGINE["latest_snapshot"].get("recent_events", [])
        ev.insert(0, f"[{ts_str}] {text}")
        ENGINE["latest_snapshot"]["recent_events"] = ev[:25]


# ==============================================================================
# COOLDOWNY & ZÁMKY
# ==============================================================================
def get_setup_cooldown_remaining(lock_key, duration_sec):
    now_s = time.time()
    with ENGINE["lock"]:
        ts_last = float(ENGINE["cooldowns"].get(lock_key, 0.0))
    rem = int(duration_sec - (now_s - ts_last))
    return max(0, rem)


def set_setup_cooldown(lock_key):
    with ENGINE["lock"]:
        ENGINE["cooldowns"][lock_key] = time.time()


def get_s1_locked_rank():
    with ENGINE["lock"]:
        return int(ENGINE.get("s1_locked_rank", 0))


def set_s1_locked_rank(rank_val):
    with ENGINE["lock"]:
        ENGINE["s1_locked_rank"] = int(rank_val)
        ENGINE["cooldowns"]["S1_LOCK_1H"] = time.time()


# ==============================================================================
# CSV LOGOVÁNÍ OBCHODŮ (VČETNĚ SESSION TAGU A VP PŘEKÁŽEK)
# ==============================================================================
def count_csv_rows():
    if not os.path.exists(CSV_LOG_PATH):
        return 0
    try:
        with open(CSV_LOG_PATH, "r", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0


def log_weekly_trade_event(event_dict):
    try:
        file_exists = os.path.exists(CSV_LOG_PATH)
        with ENGINE["lock"]:
            with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
                if not file_exists:
                    writer.writeheader()
                clean_row = {}
                for col in CSV_COLUMNS:
                    v = event_dict.get(col, "")
                    if isinstance(v, (list, dict)):
                        clean_row[col] = json.dumps(v, ensure_ascii=False)
                    else:
                        clean_row[col] = v
                writer.writerow(clean_row)
    except Exception:
        pass


# ==============================================================================
# TELEGRAM NOTIFIKACE (BEZPEČNÉ HTML)
# ==============================================================================
def sanitize_tg_html(text):
    s = str(text or "")
    s = s.replace("->", "➔").replace("=>", "➔").replace("<=", "≤").replace(">=", "≥")
    return s


def odesli_upozorneni(lock_key, title, body, lock_duration=600, force=False):
    cfg = load_runtime_config()
    token = cfg["TELEGRAM_BOT_TOKEN"]
    chat_id = cfg["TELEGRAM_CHAT_ID"]

    if not force and lock_duration > 0:
        if get_setup_cooldown_remaining(f"TG_{lock_key}", lock_duration) > 0:
            return False

    if not token or not chat_id:
        return False

    full_msg = f"🚨 <b>{sanitize_tg_html(title)}</b>\n\n{sanitize_tg_html(body)}"
    if len(full_msg) > 4000:
        full_msg = full_msg[:3990] + "\n..."

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": full_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, json=payload, timeout=8)
        if resp.status_code != 200:
            payload_plain = {
                "chat_id": chat_id,
                "text": full_msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""),
                "disable_web_page_preview": True,
            }
            resp = requests.post(url, json=payload_plain, timeout=8)
        if resp.status_code == 200:
            if lock_duration > 0:
                set_setup_cooldown(f"TG_{lock_key}")
            return True
    except Exception:
        pass
    return False


# ==============================================================================
# OKX API KLIENT (PUBLIC + PRIVATE EEA)
# ==============================================================================
def okx_signed_request(method, request_path, body_dict=None, timeout=8):
    cfg = load_runtime_config()
    api_key = cfg["OKX_API_KEY"]
    secret_key = cfg["OKX_SECRET_KEY"]
    passphrase = cfg["OKX_PASSPHRASE"]
    if not (api_key and secret_key and passphrase):
        return {"code": "-1", "msg": "Chybí OKX API klíče v Secrets", "data": []}

    method_up = method.upper()
    body_str = json.dumps(body_dict, separators=(",", ":")) if body_dict else ""
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    prehash = f"{ts_iso}{method_up}{request_path}{body_str}"
    mac = hmac.new(secret_key.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256)
    sign = base64.b64encode(mac.digest()).decode("utf-8")

    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts_iso,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }

    url = f"{OKX_PRIVATE_BASE_URL}{request_path}"
    try:
        if method_up == "GET":
            r = requests.get(url, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, headers=headers, data=body_str, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"code": "-2", "msg": f"OKX síťová chyba: {e}", "data": []}


def get_okx_pos_mode():
    with ENGINE["lock"]:
        cached = ENGINE.get("pos_mode_cache")
    if cached:
        return cached
    res = okx_signed_request("GET", "/api/v5/account/config")
    if res.get("code") == "0" and res.get("data"):
        mode = str(res["data"][0].get("posMode", "net_mode"))
        with ENGINE["lock"]:
            ENGINE["pos_mode_cache"] = mode
        return mode
    return "net_mode"


def get_okx_live_bbo(inst_id=OKX_INST_ID):
    for base in (OKX_PRIVATE_BASE_URL, OKX_PUBLIC_BASE_URL):
        try:
            r = requests.get(
                f"{base}/api/v5/market/ticker?instId={inst_id}",
                timeout=4,
            ).json()
            if r.get("code") == "0" and r.get("data"):
                d = r["data"][0]
                last_p = float(d.get("last", 0.0) or 0.0)
                bid_p = float(d.get("bidPx", 0.0) or 0.0)
                ask_p = float(d.get("askPx", 0.0) or 0.0)
                if last_p > 0:
                    return last_p, (bid_p if bid_p > 0 else last_p), (ask_p if ask_p > 0 else last_p)
        except Exception:
            continue
    return 0.0, 0.0, 0.0


def get_live_xperp_price(fallback_price, ts_ms=0):
    last_p, _, _ = get_okx_live_bbo(OKX_INST_ID)
    if last_p > 0:
        return last_p
    last_swap, _, _ = get_okx_live_bbo("BTC-USDT-SWAP")
    if last_swap > 0:
        return last_swap
    return float(fallback_price)


def get_okx_candles(bar, limit, ts_ms, inst_candidates):
    for inst in inst_candidates:
        for base in (OKX_PUBLIC_BASE_URL, OKX_PRIVATE_BASE_URL):
            try:
                url = f"{base}/api/v5/market/candles?instId={inst}&bar={bar}&limit={limit}&t={ts_ms}"
                r = requests.get(url, timeout=5).json()
                data = r.get("data", [])
                if data and len(data) >= 5:
                    return data
            except Exception:
                continue
    return []
# === KONEC ČÁSTI 1 ===# === ZAČÁTEK ČÁSTI 2 ===

# ==============================================================================
# REALTIME ORDERFLOW POLLER & 1M ANCHORED DELTA
# ==============================================================================
def poll_realtime_okx_flow():
    # 1) Futures live trades delta po minutách
    try:
        r = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=100",
            timeout=4,
        ).json()
        rows = r.get("data", [])
        if rows:
            with ENGINE["lock"]:
                last_seen = ENGINE.get("last_trade_id_fut", "")
                new_rows = []
                for tr in rows:
                    tid = str(tr.get("tradeId", ""))
                    if tid == last_seen:
                        break
                    new_rows.append(tr)
                ENGINE["last_trade_id_fut"] = str(rows[0].get("tradeId", ""))
                f_map = ENGINE["trade_flow_1m_fut"]
                for tr in new_rows:
                    t_ms = int(tr.get("ts", 0))
                    m_ts = (t_ms // 60000) * 60000
                    sz_btc = float(tr.get("sz", 0.0)) * 0.01  # BTC-USDT-SWAP ctVal = 0.01 BTC
                    signed = sz_btc if tr.get("side") == "buy" else -sz_btc
                    f_map[m_ts] = f_map.get(m_ts, 0.0) + signed
                if len(f_map) > 180:
                    cutoff = sorted(f_map.keys())[-150]
                    ENGINE["trade_flow_1m_fut"] = {k: v for k, v in f_map.items() if k >= cutoff}
    except Exception:
        pass

    # 2) Spot live trades delta po minutách
    try:
        r = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/market/trades?instId=BTC-USDT&limit=100",
            timeout=4,
        ).json()
        rows = r.get("data", [])
        if rows:
            with ENGINE["lock"]:
                last_seen = ENGINE.get("last_trade_id_spot", "")
                new_rows = []
                for tr in rows:
                    tid = str(tr.get("tradeId", ""))
                    if tid == last_seen:
                        break
                    new_rows.append(tr)
                ENGINE["last_trade_id_spot"] = str(rows[0].get("tradeId", ""))
                s_map = ENGINE["trade_flow_1m_spot"]
                for tr in new_rows:
                    t_ms = int(tr.get("ts", 0))
                    m_ts = (t_ms // 60000) * 60000
                    sz_btc = float(tr.get("sz", 0.0))
                    signed = sz_btc if tr.get("side") == "buy" else -sz_btc
                    s_map[m_ts] = s_map.get(m_ts, 0.0) + signed
                if len(s_map) > 180:
                    cutoff = sorted(s_map.keys())[-150]
                    ENGINE["trade_flow_1m_spot"] = {k: v for k, v in s_map.items() if k >= cutoff}
    except Exception:
        pass

    # 3) Live Open Interest delta pro aktuální 5M svíčku
    try:
        r = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP",
            timeout=4,
        ).json()
        d = r.get("data", [])
        if d:
            oi_ccy = float(d[0].get("oiCcy", 0.0) or 0.0)
            now_5m = (int(time.time() * 1000) // 300000) * 300000
            if oi_ccy > 0:
                with ENGINE["lock"]:
                    snap = ENGINE["oi_last_snapshot"]
                    if now_5m not in snap:
                        snap[now_5m] = oi_ccy
                    ENGINE["oi_live_delta"][now_5m] = oi_ccy - snap[now_5m]
                    if len(snap) > 40:
                        cut = sorted(snap.keys())[-30]
                        ENGINE["oi_last_snapshot"] = {k: v for k, v in snap.items() if k >= cut}
                        ENGINE["oi_live_delta"] = {k: v for k, v in ENGINE["oi_live_delta"].items() if k >= cut}
    except Exception:
        pass


def estimate_candle_delta(c, is_spot=False):
    try:
        o, h, l, cl = float(c[1]), float(c[2]), float(c[3]), float(c[4])
        vol = float(c[6]) if len(c) > 6 and float(c[6]) > 0 else float(c[5])
        if is_spot and len(c) > 5:
            vol = float(c[5])
        rng = max(h - l, 1e-6)
        body_ratio = (cl - o) / rng
        return vol * body_ratio * 0.55
    except Exception:
        return 0.0


def get_1m_real_or_calibrated_delta(candles_1m, open_5m_ts, is_spot=False):
    with ENGINE["lock"]:
        live_map = dict(ENGINE["trade_flow_1m_spot"] if is_spot else ENGINE["trade_flow_1m_fut"])

    total = 0.0
    end_5m_ts = open_5m_ts + 300000
    for c in candles_1m:
        try:
            t_ms = int(c[0])
            if open_5m_ts <= t_ms < end_5m_ts:
                if t_ms in live_map and abs(live_map[t_ms]) > 0.01:
                    total += live_map[t_ms]
                else:
                    total += estimate_candle_delta(c, is_spot=is_spot)
        except Exception:
            continue
    return total


def compute_anchored_1m_map(mf_asc, map_5m, is_spot=False):
    anchored = {}
    if not mf_asc:
        return anchored

    with ENGINE["lock"]:
        live_map = dict(ENGINE["trade_flow_1m_spot"] if is_spot else ENGINE["trade_flow_1m_fut"])

    buckets = {}
    for c in mf_asc:
        t_ms = int(c[0])
        b5 = (t_ms // 300000) * 300000
        buckets.setdefault(b5, []).append(c)

    for b5, c_list in buckets.items():
        raw_vals = {}
        for c in c_list:
            t_ms = int(c[0])
            if t_ms in live_map and abs(live_map[t_ms]) > 0.01:
                raw_vals[t_ms] = live_map[t_ms]
            else:
                raw_vals[t_ms] = estimate_candle_delta(c, is_spot=is_spot)

        if map_5m and b5 in map_5m and len(c_list) == 5:
            target_5m = float(map_5m[b5])
            est_sum = sum(raw_vals.values())
            diff = target_5m - est_sum
            abs_weights = {t: max(abs(v), 0.5) for t, v in raw_vals.items()}
            w_sum = sum(abs_weights.values()) or 1.0
            for t, v in raw_vals.items():
                anchored[t] = v + diff * (abs_weights[t] / w_sum)
        else:
            for t, v in raw_vals.items():
                anchored[t] = v

    return anchored


def compute_single_1m_delta(candle_1m, is_spot=False, anchored_map=None):
    t_ms = int(candle_1m[0])
    if anchored_map and t_ms in anchored_map:
        return float(anchored_map[t_ms])
    return estimate_candle_delta(candle_1m, is_spot=is_spot)


# ==============================================================================
# VOLUME PROFILE (3H & 6H), SWINGY (3L+3R) A TREND ENGINE
# ==============================================================================
def compute_vp_from_candles(candles_desc, num_candles, num_bins=36):
    src = candles_desc[:num_candles] if len(candles_desc) >= num_candles else candles_desc
    if not src:
        return {"vah": 0.0, "poc": 0.0, "val": 0.0}

    highs = [float(c[2]) for c in src]
    lows = [float(c[3]) for c in src]
    min_p, max_p = min(lows), max(highs)
    if max_p <= min_p:
        return {"vah": max_p, "poc": min_p, "val": min_p}

    bin_size = (max_p - min_p) / num_bins
    bins = [0.0] * num_bins
    centers = [min_p + (i + 0.5) * bin_size for i in range(num_bins)]

    for c in src:
        h, l = float(c[2]), float(c[3])
        vol = float(c[6]) if len(c) > 6 and float(c[6]) > 0 else float(c[5])
        if vol <= 0:
            vol = 1.0
        b_start = max(0, min(num_bins - 1, int((l - min_p) / bin_size)))
        b_end = max(0, min(num_bins - 1, int((h - min_p) / bin_size)))
        span = (b_end - b_start) + 1
        share = vol / span
        for bi in range(b_start, b_end + 1):
            bins[bi] += share

    total_v = sum(bins)
    if total_v <= 0:
        mid = (max_p + min_p) / 2.0
        return {"vah": max_p, "poc": mid, "val": min_p}

    poc_idx = max(range(num_bins), key=lambda i: bins[i])
    poc = centers[poc_idx]

    target_v = total_v * 0.70
    acc_v = bins[poc_idx]
    lo_i, hi_i = poc_idx, poc_idx
    while acc_v < target_v and (lo_i > 0 or hi_i < num_bins - 1):
        up_v = bins[hi_i + 1] if hi_i < num_bins - 1 else -1.0
        dn_v = bins[lo_i - 1] if lo_i > 0 else -1.0
        if up_v >= dn_v:
            hi_i += 1
            acc_v += bins[hi_i]
        else:
            lo_i -= 1
            acc_v += bins[lo_i]

    vah = centers[hi_i] + bin_size * 0.5
    val = centers[lo_i] - bin_size * 0.5
    return {"vah": round(vah, 1), "poc": round(poc, 1), "val": round(val, 1)}


def find_3l3r_swings(candles_300_desc, lookback=72):
    closed_desc = candles_300_desc[1:lookback + 1] if len(candles_300_desc) > 8 else candles_300_desc
    asc = closed_desc[::-1]
    n = len(asc)
    swings_high, swings_low = [], []
    if n < 7:
        return swings_high, swings_low

    tz = get_prague_now().tzinfo
    for i in range(3, n - 3):
        hi = float(asc[i][2])
        lo = float(asc[i][3])
        ts_lbl = datetime.fromtimestamp(int(asc[i][0]) / 1000.0, tz).strftime("%H:%M")

        if all(hi >= float(asc[j][2]) for j in range(i - 3, i + 4) if j != i):
            swings_high.append((hi, ts_lbl))
        if all(lo <= float(asc[j][3]) for j in range(i - 3, i + 4) if j != i):
            swings_low.append((lo, ts_lbl))

    return swings_high, swings_low


def compute_3h_6h_trend(candles_300_desc, btc_price):
    if len(candles_300_desc) < 72:
        return "CHOP", "Nedostatek 6H dat (CHOP)", 50.0, 0.0, 0.0

    c_6h = candles_300_desc[:72]
    c_3h = candles_300_desc[:36]
    c_1h = candles_300_desc[:12]

    hi_6h = max(float(c[2]) for c in c_6h)
    lo_6h = min(float(c[3]) for c in c_6h)
    rng_6h = max(hi_6h - lo_6h, 1.0)
    pos_6h_pct = max(0.0, min(100.0, ((btc_price - lo_6h) / rng_6h) * 100.0))

    open_3h = float(c_3h[-1][1])
    swing_3h_usd = btc_price - open_3h
    swing_3h_pct = (swing_3h_usd / max(open_3h, 1.0)) * 100.0

    open_1h = float(c_1h[-1][1])
    imp_1h_usd = btc_price - open_1h
    imp_1h_pct = (imp_1h_usd / max(open_1h, 1.0)) * 100.0

    if (swing_3h_pct >= 1.35 and pos_6h_pct >= 62.0) or (imp_1h_pct >= 0.90 and swing_3h_pct >= 0.80):
        regime = "STRONG_BULL"
    elif (swing_3h_pct <= -1.35 and pos_6h_pct <= 38.0) or (imp_1h_pct <= -0.90 and swing_3h_pct <= -0.80):
        regime = "STRONG_BEAR"
    elif (swing_3h_pct >= 0.65 and pos_6h_pct >= 52.0) or (swing_3h_pct >= 0.45 and imp_1h_pct >= 0.35):
        regime = "MILD_BULL"
    elif (swing_3h_pct <= -0.65 and pos_6h_pct <= 48.0) or (swing_3h_pct <= -0.45 and imp_1h_pct <= -0.35):
        regime = "MILD_BEAR"
    else:
        regime = "CHOP"

    detail = (
        f"{regime} (Swing {abs(swing_3h_usd):.0f}$ [{abs(swing_3h_pct):.2f}%] | "
        f"Pozice v 6H pásmu: {pos_6h_pct:.0f}% | 1H Impuls: {imp_1h_usd:+.0f}$ [{abs(imp_1h_pct):.2f}%])"
    )
    return regime, detail, pos_6h_pct, swing_3h_pct, imp_1h_pct


def compute_vp_confluences(vp3, vp6, btc_price):
    tol = btc_price * 0.0010
    lvl3 = [("3H_VAH", vp3["vah"]), ("3H_POC", vp3["poc"]), ("3H_VAL", vp3["val"])]
    lvl6 = [("6H_VAH", vp6["vah"]), ("6H_POC", vp6["poc"]), ("6H_VAL", vp6["val"])]
    found = []
    for n3, p3 in lvl3:
        for n6, p6 in lvl6:
            if p3 > 0 and p6 > 0 and abs(p3 - p6) <= tol:
                avg_p = (p3 + p6) / 2.0
                found.append(f"{n3}+{n6}@{avg_p:.0f}$")
    return ", ".join(found) if found else "Žádná 3H+6H konfluence v okolí"


# ==============================================================================
# BUILD TRADE PLAN (PEVNÝ 100% MAKER TP = 2.3x SL)
# ==============================================================================
def build_trade_plan(direction, entry_px, setup_label, group_id="MEDIUM", sl_px=None, sl_pct=None):
    entry_px = round(float(entry_px), 1)
    min_sl, max_sl = SL_BANDS.get(group_id, (0.0025, 0.0030))

    if sl_px is None:
        use_sl_pct = float(sl_pct) if sl_pct is not None else min_sl
        use_sl_pct = max(min_sl, min(max_sl, use_sl_pct))
        if direction == "LONG":
            sl_px = round(entry_px * (1.0 - use_sl_pct), 1)
        else:
            sl_px = round(entry_px * (1.0 + use_sl_pct), 1)
    else:
        sl_px = round(float(sl_px), 1)

    sl_dist = abs(entry_px - sl_px)
    actual_sl_pct = sl_dist / max(entry_px, 1.0)
    tp_dist = sl_dist * FIXED_TP_SL_MULT
    tp_px = round(entry_px + tp_dist, 1) if direction == "LONG" else round(entry_px - tp_dist, 1)
    actual_tp_pct = tp_dist / max(entry_px, 1.0)

    net_win_pct = max(actual_tp_pct - (2.0 * MAKER_FEE_RATE), 0.0001)
    net_loss_pct = actual_sl_pct + (MAKER_FEE_RATE + TAKER_FEE_RATE)
    real_net_rrr = round(net_win_pct / max(net_loss_pct, 1e-6), 2)

    return {
        "direction": direction,
        "group": group_id,
        "setup_label": setup_label,
        "entry": entry_px,
        "sl_market": sl_px,
        "sl_pct": actual_sl_pct,
        "tp_limit": tp_px,
        "tp_pct": actual_tp_pct,
        "raw_rrr": round(FIXED_TP_SL_MULT, 2),
        "real_net_rrr": real_net_rrr,
        "position_usd": POSITION_SIZE_USD,
        "trigger_ready": False,
    }


# ==============================================================================
# VOLITELNÝ KOMENTÁŘ Z GOOGLE AI STUDIA (GEMINI) – NEBLOKUJE EXEKUCI
# ==============================================================================
def fetch_gemini_comment(prompt_text, fallback_text):
    cfg = load_runtime_config()
    api_key = cfg["GEMINI_API_KEY"]
    if not api_key:
        return fallback_text

    models = ("gemini-2.5-flash", "gemini-2.0-flash")
    for model_name in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 120},
            }
            r = requests.post(url, json=payload, timeout=4.0)
            if r.status_code == 200:
                j = r.json()
                cands = j.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    if parts and parts[0].get("text"):
                        txt = str(parts[0]["text"]).strip().replace("\n", " ")
                        if len(txt) > 10:
                            return txt[:320]
        except Exception:
            continue
    return fallback_text


# ==============================================================================
# ARGON 4 BOSS AI ENGINE v19 (VP ZÁKONY + CHOP/WITH_TREND + SL PÁSMA + 2.3x TP)
# ==============================================================================
def evaluate_argon4_background(
    group_id,
    direction,
    t_payload,
    candles_300,
    flow_metrics,
    box_spot,
    spot_map,
    box_low_p,
    box_high_p,
):
    entry = float(t_payload["entry"])
    is_long = (direction == "LONG")
    min_sl_pct, max_sl_pct = SL_BANDS.get(group_id, (0.0025, 0.0030))

    vp3 = compute_vp_from_candles(candles_300, 36)
    vp6 = compute_vp_from_candles(candles_300, 72)
    confluences = compute_vp_confluences(vp3, vp6, entry)
    swings_h, swings_l = find_3l3r_swings(candles_300, lookback=72)

    c_3h_ts = [int(c[0]) for c in candles_300[:36]] if candles_300 else []
    c_6h_ts = [int(c[0]) for c in candles_300[:72]] if candles_300 else []
    spot_3h = sum(spot_map.get(t, 0.0) for t in c_3h_ts)
    spot_6h = sum(spot_map.get(t, 0.0) for t in c_6h_ts)
    spot_3h_6h_str = f"3H Spot: {spot_3h:+.1f} BTC | 6H Spot: {spot_6h:+.1f} BTC"

    # ZÁKON 2 v19: POUZE CHOP + WITH_TREND (ZÁKAZ PROTI MILD I STRONG TRENDU)
    trend_regime, trend_detail, pos_6h_pct, swing_3h_pct, imp_1h_pct = compute_3h_6h_trend(candles_300, entry)
    if trend_regime == "CHOP":
        trend_alignment = "CHOP"
        trend_ok = True
        trend_note = "✅ Boční trh (CHOP) – ideální pro Setup 1"
    elif (is_long and trend_regime in ("MILD_BULL", "STRONG_BULL")) or (
        (not is_long) and trend_regime in ("MILD_BEAR", "STRONG_BEAR")
    ):
        trend_alignment = "WITH_TREND"
        trend_ok = True
        trend_note = f"✅ Ve směru trendu ({trend_regime})"
    else:
        trend_alignment = "COUNTER_TREND"
        trend_ok = False
        trend_note = f"🛑 ZÁKAZ PROTITRENDU {APP_VERSION}: {direction} proti {trend_regime} (povoleno jen CHOP + WITH_TREND)"

    # ZÁKON 1: 3H/6H Volume Profile pravidla
    b_lo = min(float(box_low_p), entry)
    b_hi = max(float(box_high_p), entry)
    edge_tol = entry * 0.0012

    vp_levels = [
        ("3H_VAH", vp3["vah"]), ("3H_POC", vp3["poc"]), ("3H_VAL", vp3["val"]),
        ("6H_VAH", vp6["vah"]), ("6H_POC", vp6["poc"]), ("6H_VAL", vp6["val"]),
    ]

    touched_edges = []
    for lbl, lvl in vp_levels:
        if lvl > 0 and (b_lo - edge_tol) <= lvl <= (b_hi + edge_tol):
            touched_edges.append(f"{lbl}({lvl:.0f}$)")

    valid_vals = [v for v in (vp3["val"], vp6["val"]) if v > 0]
    min_val = min(valid_vals) if valid_vals else 0.0
    max_vah = max(vp3["vah"], vp6["vah"])

    below_all_val = (min_val > 0 and b_hi < (min_val - edge_tol))
    above_all_vah = (max_vah > 0 and b_lo > (max_vah + edge_tol))

    if is_long and below_all_val:
        vp_ok = False
        vp_reason = f"🛑 Zákaz LONG pod VAL ({b_lo:.0f}$–{b_hi:.0f}$ pod VAL {min_val:.0f}$)"
    elif (not is_long) and above_all_vah:
        vp_ok = False
        vp_reason = f"🛑 Zákaz SHORT nad VAH ({b_lo:.0f}$–{b_hi:.0f}$ nad VAH {max_vah:.0f}$)"
    elif is_long and above_all_vah:
        vp_ok = True
        vp_reason = f"✅ Průraz LONG nad VAH ({b_lo:.0f}$–{b_hi:.0f}$ nad {max_vah:.0f}$)"
    elif (not is_long) and below_all_val:
        vp_ok = True
        vp_reason = f"✅ Průraz SHORT pod VAL ({b_lo:.0f}$–{b_hi:.0f}$ pod {min_val:.0f}$)"
    elif touched_edges:
        vp_ok = True
        vp_reason = f"✅ Krabice ({b_lo:.0f}$–{b_hi:.0f}$) uzavírá na hraně {', '.join(touched_edges)} ➔ obchod platný"
    else:
        vp_ok = False
        vp_reason = f"🛑 Uvnitř VP bez dotyku VAH/VAL/POC ({b_lo:.0f}$–{b_hi:.0f}$ v prázdném prostoru)"

    # ZÁKON 3: Argon SL v pásmu MEDIUM (0.25–0.30%) nebo MACRO (0.35–0.45%)
    buf_usd = max(15.0, entry * 0.0003)
    base_sl_px = round(entry * (1.0 - min_sl_pct), 1) if is_long else round(entry * (1.0 + min_sl_pct), 1)
    max_sl_px = round(entry * (1.0 - max_sl_pct), 1) if is_long else round(entry * (1.0 + max_sl_pct), 1)

    rec_sl_px = base_sl_px
    sl_reason = f"Základní SL {base_sl_px:.0f}$ ({min_sl_pct*100:.2f}% v pásmu {group_id} {min_sl_pct*100:.2f}%–{max_sl_pct*100:.2f}%)"

    sl_candidates = []
    if is_long:
        sl_candidates.append(("Box Low", box_low_p))
        for lbl, lvl in vp_levels:
            if lvl > 0:
                sl_candidates.append((lbl, lvl))
        for sp, ts_l in swings_l[-6:]:
            sl_candidates.append((f"3L+3R Swing Low ({ts_l})", sp))

        best_sl = base_sl_px
        best_lbl = ""
        for lbl, lvl in sl_candidates:
            if (max_sl_px + buf_usd) <= lvl < entry:
                cand_sl = round(lvl - buf_usd, 1)
                if max_sl_px <= cand_sl < best_sl:
                    best_sl = cand_sl
                    best_lbl = f"{lbl}({lvl:.0f}$)"
        if best_lbl:
            rec_sl_px = best_sl
            pct_now = abs(entry - rec_sl_px) / max(entry, 1.0) * 100.0
            sl_reason = f"Argon SL {rec_sl_px:.0f}$ ({pct_now:.2f}% v pásmu {group_id} {min_sl_pct*100:.2f}%–{max_sl_pct*100:.2f}%) krytý pod {best_lbl}"
    else:
        sl_candidates.append(("Box High", box_high_p))
        for lbl, lvl in vp_levels:
            if lvl > 0:
                sl_candidates.append((lbl, lvl))
        for sp, ts_l in swings_h[-6:]:
            sl_candidates.append((f"3L+3R Swing High ({ts_l})", sp))

        best_sl = base_sl_px
        best_lbl = ""
        for lbl, lvl in sl_candidates:
            if entry < lvl <= (max_sl_px - buf_usd):
                cand_sl = round(lvl + buf_usd, 1)
                if best_sl < cand_sl <= max_sl_px:
                    best_sl = cand_sl
                    best_lbl = f"{lbl}({lvl:.0f}$)"
        if best_lbl:
            rec_sl_px = best_sl
            pct_now = abs(entry - rec_sl_px) / max(entry, 1.0) * 100.0
            sl_reason = f"Argon SL {rec_sl_px:.0f}$ ({pct_now:.2f}% v pásmu {group_id} {min_sl_pct*100:.2f}%–{max_sl_pct*100:.2f}%) krytý nad {best_lbl}"

    # ZÁKON 4: Pevný 100% Maker TP = 2.3x SL + informativní seznam VP překážek v cestě
    plan_final = build_trade_plan(
        direction=direction,
        entry_px=entry,
        setup_label=t_payload.get("setup_label", f"SETUP 1 ({group_id})"),
        group_id=group_id,
        sl_px=rec_sl_px,
    )
    rec_tp_px = plan_final["tp_limit"]
    rec_sl_pct = plan_final["sl_pct"]
    rec_tp_pct = plan_final["tp_pct"]
    real_net_rrr = plan_final["real_net_rrr"]

    min_obs_dist = entry * 0.0015
    obstacles = []
    for lbl, lvl in vp_levels:
        if lvl <= 0:
            continue
        if is_long and (entry + min_obs_dist) <= lvl < rec_tp_px:
            r_mult = (lvl - entry) / max(abs(entry - rec_sl_px), 1.0)
            obstacles.append((lvl, f"{lbl}@{lvl:.0f}$ ({r_mult:.1f}R)"))
        elif (not is_long) and rec_tp_px < lvl <= (entry - min_obs_dist):
            r_mult = (entry - lvl) / max(abs(entry - rec_sl_px), 1.0)
            obstacles.append((lvl, f"{lbl}@{lvl:.0f}$ ({r_mult:.1f}R)"))

    obstacles.sort(key=lambda x: x[0], reverse=(not is_long))
    obstacles_str = ", ".join(x[1] for x in obstacles) if obstacles else "Volná cesta bez VP překážek"

    approved = bool(vp_ok and trend_ok)
    if approved:
        score = 88
        if trend_alignment == "CHOP":
            score += 6
        if confluences != "Žádná 3H+6H konfluence v okolí":
            score += 4
        if group_id == "MACRO":
            score += 2
        score = min(100, score)
        verdict = "🟢 SCHVÁLENO"
    else:
        score = 25
        verdict = "🛑 ZAMÍTNUTO"

    fallback_comment = f"{vp_reason} | {trend_note} | {sl_reason} | Fixní 100% TP: {rec_tp_px:.0f}$ (2.3x SL)."
    if approved:
        ai_prompt = (
            f"Jsi Argon 4 Boss (trading AI pro BTC). Stručně ve 2 českých větách okomentuj schválený obchod: "
            f"S1 {group_id} {direction} @ {entry:.0f}$, SL {rec_sl_px:.0f}$ ({rec_sl_pct*100:.2f}%), "
            f"pevný 100% TP {rec_tp_px:.0f}$ (2.3x SL, čisté RRR {real_net_rrr}). "
            f"Trend: {trend_regime} ({trend_alignment}). VP: {vp_reason}. Překážky v cestě: {obstacles_str}."
        )
        ai_comment = fetch_gemini_comment(ai_prompt, fallback_comment)
    else:
        ai_comment = fallback_comment

    telegram_block = (
        f"\n🧠 <b>ARGON 4 AI ROZHODNUTÍ ({APP_VERSION} – PLNÁ PRAVOMOC):</b>\n"
        f"• Verdikt: {verdict} (Skóre: {score}/100 | Fix RRR: 2.30 | Čisté RRR po fees: {real_net_rrr})\n"
        f"• Kap. 1 (3H/6H VP): {vp_reason}\n"
        f"• 3H/6H Konfluence: {confluences}\n"
        f"• Kap. 2 (Trend 3H+6H): {trend_note} | {trend_detail}\n"
        f"• Kap. 3 (Argon SL [{group_id}]): {sl_reason}\n"
        f"• Kap. 4 (Fixní 100% Maker TP): {rec_tp_px:.0f}$ ({rec_tp_pct*100:.2f}% = 2.3x SL)\n"
        f"• 🚧 VP překážky v cestě k TP (info pro 6.12.): {obstacles_str}\n"
        f"• Kap. 5 (3H & 6H Spot CVD): {spot_3h_6h_str}\n"
        f"• Zdůvodnění AI: {ai_comment}"
    )

    return {
        "approved": approved,
        "verdict": verdict,
        "score": score,
        "vp_3h": vp3,
        "vp_6h": vp6,
        "vp_confluences": confluences,
        "vp_obstacles": obstacles_str,
        "trend_regime": trend_regime,
        "trend_alignment": trend_alignment,
        "trend_3h": trend_detail,
        "spot_3h": spot_3h,
        "spot_6h": spot_6h,
        "spot_3h_6h": spot_3h_6h_str,
        "rec_sl_px": rec_sl_px,
        "rec_sl_pct": rec_sl_pct,
        "rec_tp_px": rec_tp_px,
        "rec_tp_pct": rec_tp_pct,
        "raw_rrr": 2.30,
        "real_net_rrr": real_net_rrr,
        "ai_comment": ai_comment,
        "telegram_block": telegram_block,
    }
# === KONEC ČÁSTI 2 ===# === ZAČÁTEK ČÁSTI 3 ===

# ==============================================================================
# OKX AGENT: 1 ČISTÝ BBO MAKER VSTUP + 1 PEVNÝ 100% MAKER TP (BEZ 50/50, BEZ AUTO-BE)
# ==============================================================================
def get_open_position_okx():
    res = okx_signed_request("GET", f"/api/v5/account/positions?instId={OKX_INST_ID}")
    if res.get("code") != "0":
        return 0, "", 0.0, 0.0
    for p in res.get("data", []):
        pos_f = float(p.get("pos", 0.0) or 0.0)
        if abs(pos_f) >= 0.5:
            sz_int = int(round(abs(pos_f)))
            p_side = str(p.get("posSide", "")).lower()
            if p_side in ("long", "short"):
                direction = "LONG" if p_side == "long" else "SHORT"
            else:
                direction = "LONG" if pos_f > 0 else "SHORT"
            avg_px = float(p.get("avgPx", 0.0) or 0.0)
            upl = float(p.get("upl", 0.0) or 0.0)
            return sz_int, direction, avg_px, upl
    return 0, "", 0.0, 0.0


def get_pending_orders_okx():
    res = okx_signed_request("GET", f"/api/v5/trade/orders-pending?instId={OKX_INST_ID}")
    if res.get("code") != "0":
        return []
    return res.get("data", []) or []


def get_pending_algo_orders_okx():
    res = okx_signed_request(
        "GET", f"/api/v5/trade/orders-algo-pending?instId={OKX_INST_ID}&ordType=conditional"
    )
    if res.get("code") != "0":
        return []
    return res.get("data", []) or []


def cancel_okx_order(ord_id):
    if not ord_id:
        return False
    res = okx_signed_request(
        "POST",
        "/api/v5/trade/cancel-order",
        {"instId": OKX_INST_ID, "ordId": str(ord_id)},
    )
    return res.get("code") == "0"


def cancel_okx_algo_order(algo_id):
    if not algo_id:
        return False
    res = okx_signed_request(
        "POST",
        "/api/v5/trade/cancel-algos",
        [{"instId": OKX_INST_ID, "algoId": str(algo_id)}],
    )
    return res.get("code") == "0"


def ensure_okx_leverage(direction):
    pos_mode = get_okx_pos_mode()
    body = {
        "instId": OKX_INST_ID,
        "lever": str(OKX_LEVERAGE),
        "mgnMode": OKX_MARGIN_MODE,
    }
    if pos_mode == "long_short_mode":
        body["posSide"] = "long" if direction == "LONG" else "short"
    okx_signed_request("POST", "/api/v5/account/set-leverage", body)


def place_single_maker_tp(direction, pos_sz, tp_px):
    pos_mode = get_okx_pos_mode()
    close_side = "sell" if direction == "LONG" else "buy"
    _, bid_p, ask_p = get_okx_live_bbo(OKX_INST_ID)

    ord_type = "post_only"
    if direction == "LONG" and bid_p > 0 and tp_px <= bid_p:
        ord_type = "limit"
    elif direction == "SHORT" and ask_p > 0 and tp_px >= ask_p:
        ord_type = "limit"

    body = {
        "instId": OKX_INST_ID,
        "tdMode": OKX_MARGIN_MODE,
        "side": close_side,
        "ordType": ord_type,
        "sz": str(int(pos_sz)),
        "px": str(round(float(tp_px), 1)),
        "reduceOnly": True,
    }
    if pos_mode == "long_short_mode":
        body["posSide"] = "long" if direction == "LONG" else "short"

    res = okx_signed_request("POST", "/api/v5/trade/order", body)
    if res.get("code") == "0" and res.get("data"):
        d0 = res["data"][0]
        if d0.get("sCode") == "0":
            return True, str(d0.get("ordId", "")), ord_type
    return False, str(res.get("msg", res)), ord_type


def place_emergency_sl_algo(direction, pos_sz, sl_px):
    pos_mode = get_okx_pos_mode()
    close_side = "sell" if direction == "LONG" else "buy"
    body = {
        "instId": OKX_INST_ID,
        "tdMode": OKX_MARGIN_MODE,
        "side": close_side,
        "ordType": "conditional",
        "sz": str(int(pos_sz)),
        "slTriggerPx": str(round(float(sl_px), 1)),
        "slOrdPx": "-1",
        "slTriggerPxType": "last",
        "reduceOnly": True,
    }
    if pos_mode == "long_short_mode":
        body["posSide"] = "long" if direction == "LONG" else "short"
    res = okx_signed_request("POST", "/api/v5/trade/order-algo", body)
    return res.get("code") == "0"


def execute_okx_agent_trade(t_payload):
    cfg = load_runtime_config()
    direction = t_payload["direction"]
    group_id = t_payload.get("group", "MEDIUM")
    entry_px = round(float(t_payload["entry"]), 1)
    sl_px = round(float(t_payload["sl_market"]), 1)
    tp_px = round(float(t_payload["tp_limit"]), 1)
    box_low_p = float(t_payload.get("box_low_p", 0.0) or 0.0)
    box_high_p = float(t_payload.get("box_high_p", 0.0) or 0.0)
    entry_mode = str(t_payload.get("entry_mode", "BBO_IN_BOX"))

    if not cfg["AI_TRADING_ENABLED"]:
        return True, f"🟡 AI AGENT: Exekuce vypnuta (Signál {direction} [{entry_mode}] @ {entry_px:.0f}$ | SL {sl_px:.0f}$ | 100% TP {tp_px:.0f}$)"

    if cfg["DRY_RUN"]:
        return True, f"🧪 AI AGENT (Dry-Run {APP_VERSION}): {direction} [{entry_mode}] (500$) @ {entry_px:.0f}$ | SL {sl_px:.0f}$ | 100% Maker TP {tp_px:.0f}$"

    if not (cfg["OKX_API_KEY"] and cfg["OKX_SECRET_KEY"] and cfg["OKX_PASSPHRASE"]):
        return False, "⚠️ AI AGENT: Chybí OKX API klíče v Secrets."

    pos_sz, pos_dir, _, _ = get_open_position_okx()
    pending_ords = get_pending_orders_okx()
    if pos_sz > 0 or len(pending_ords) > 0:
        with ENGINE["lock"]:
            ENGINE["has_open_or_pending"] = True
        return False, f"⏸️ AI AGENT: Na OKX už běží pozice ({pos_sz} ct {pos_dir}) nebo čekající příkaz ({len(pending_ords)})."

    ensure_okx_leverage(direction)

    # Čerstvé BBO těsně před odesláním + tvrdá podlaha/strop na hraně krabice (nikdy nehoníme cenu mimo box!)
    _, bid_p, ask_p = get_okx_live_bbo(OKX_INST_ID)
    limit_px = entry_px
    if direction == "SHORT":
        if ask_p > 0:
            floor_p = box_low_p if box_low_p > 0 else entry_px
            limit_px = round(max(ask_p, floor_p), 1)
            entry_mode = "BBO_IN_BOX" if ask_p >= floor_p else "RETEST_BOX_EDGE"
    else:
        if bid_p > 0:
            ceil_p = box_high_p if box_high_p > 0 else entry_px
            limit_px = round(min(bid_p, ceil_p), 1)
            entry_mode = "BBO_IN_BOX" if bid_p <= ceil_p else "RETEST_BOX_EDGE"

    min_sl_pct, max_sl_pct = SL_BANDS.get(group_id, (0.0025, 0.0030))
    orig_sl_pct = max(min_sl_pct, min(max_sl_pct, abs(entry_px - sl_px) / max(entry_px, 1.0)))
    sl_px = round(limit_px * (1.0 - orig_sl_pct), 1) if direction == "LONG" else round(limit_px * (1.0 + orig_sl_pct), 1)
    sl_dist = abs(limit_px - sl_px)
    tp_px = round(limit_px + FIXED_TP_SL_MULT * sl_dist, 1) if direction == "LONG" else round(limit_px - FIXED_TP_SL_MULT * sl_dist, 1)

    t_payload["entry"] = limit_px
    t_payload["entry_mode"] = entry_mode
    t_payload["sl_market"] = sl_px
    t_payload["sl_pct"] = sl_dist / max(limit_px, 1.0)
    t_payload["tp_limit"] = tp_px
    t_payload["tp_pct"] = abs(tp_px - limit_px) / max(limit_px, 1.0)

    total_ct = max(1, int(round(POSITION_SIZE_USD / (limit_px * OKX_CT_VAL))))
    pos_mode = get_okx_pos_mode()
    open_side = "buy" if direction == "LONG" else "sell"

    # Odeslání post_only s jedním bezpečným pokusem navíc (+1 tick), kdyby cena cukla během přenosu
    last_err_msg = ""
    for attempt in range(2):
        send_px = limit_px
        if attempt == 1:
            _, bid2, ask2 = get_okx_live_bbo(OKX_INST_ID)
            if direction == "SHORT" and ask2 > 0:
                floor_p = box_low_p if box_low_p > 0 else limit_px
                send_px = round(max(ask2 + 1.0, floor_p), 1)
            elif direction == "LONG" and bid2 > 0:
                ceil_p = box_high_p if box_high_p > 0 else limit_px
                send_px = round(min(bid2 - 1.0, ceil_p), 1)

            sl_px = round(send_px * (1.0 - orig_sl_pct), 1) if direction == "LONG" else round(send_px * (1.0 + orig_sl_pct), 1)
            sl_dist = abs(send_px - sl_px)
            tp_px = round(send_px + FIXED_TP_SL_MULT * sl_dist, 1) if direction == "LONG" else round(send_px - FIXED_TP_SL_MULT * sl_dist, 1)
            t_payload["entry"] = send_px
            t_payload["sl_market"] = sl_px
            t_payload["tp_limit"] = tp_px

        order_body = {
            "instId": OKX_INST_ID,
            "tdMode": OKX_MARGIN_MODE,
            "side": open_side,
            "ordType": "post_only",
            "sz": str(total_ct),
            "px": str(send_px),
            "attachAlgoOrds": [
                {
                    "slTriggerPx": str(sl_px),
                    "slOrdPx": "-1",
                    "slTriggerPxType": "last",
                }
            ],
        }
        if pos_mode == "long_short_mode":
            order_body["posSide"] = "long" if direction == "LONG" else "short"

        res = okx_signed_request("POST", "/api/v5/trade/order", order_body)
        if res.get("code") == "0" and res.get("data"):
            d0 = res["data"][0]
            if d0.get("sCode") == "0":
                ord_id = str(d0.get("ordId", ""))
                with ENGINE["lock"]:
                    ENGINE["has_open_or_pending"] = True
                    ENGINE["active_trade"] = {
                        "active": True,
                        "direction": direction,
                        "group": group_id,
                        "entry_ord_id": ord_id,
                        "entry_px": send_px,
                        "sl_px": sl_px,
                        "tp_px": tp_px,
                        "target_ct": total_ct,
                        "tp_ord_id": "",
                        "tp_placed_sz": 0,
                        "created_at": time.time(),
                        "tp_notified": False,
                        "sl_guard_checked": False,
                    }
                add_ui_event(f"ZADÁN 1x MAKER [{entry_mode}] {direction} ({total_ct} ct @ {send_px:.0f}$ | SL {sl_px:.0f}$ | TP {tp_px:.0f}$)")
                return True, (
                    f"🤖 AI AGENT (ARGON 4 BOSS {APP_VERSION}): ZADAL 1x MAKER [{entry_mode}] ({POSITION_SIZE_USD:.0f}$ / {total_ct} ct) "
                    f"VSTUP @ {send_px:.0f}$ (SL {t_payload['sl_pct']*100:.2f}%: {sl_px:.0f}$ | "
                    f"100% Maker TP (2.3x SL): {tp_px:.0f}$ | Timeout 5 min)"
                )
            last_err_msg = str(d0.get("sMsg", d0))
        else:
            last_err_msg = str(res.get("msg", res))

    return False, f"❌ AI AGENT OKX zamítnutí: {last_err_msg}"


def manage_active_okx_lifecycle():
    cfg = load_runtime_config()
    if not (cfg["AI_TRADING_ENABLED"] and not cfg["DRY_RUN"] and cfg["OKX_API_KEY"]):
        return "Dry-Run / Vypnuto"

    pos_sz, pos_dir, avg_px, upl = get_open_position_okx()
    pending_ords = get_pending_orders_okx()
    algo_ords = get_pending_algo_orders_okx()

    entry_ords = [o for o in pending_ords if str(o.get("reduceOnly", "false")).lower() != "true"]
    tp_ords = [o for o in pending_ords if str(o.get("reduceOnly", "false")).lower() == "true"]

    with ENGINE["lock"]:
        at = dict(ENGINE["active_trade"])
        ENGINE["has_open_or_pending"] = bool(pos_sz > 0 or len(entry_ords) > 0)
        ENGINE["latest_snapshot"]["open_position_info"] = (
            f"{pos_dir} {pos_sz} ct @ {avg_px:.1f}$ (uPnL: {upl:+.2f}$)" if pos_sz > 0 else "Žádná otevřená pozice"
        )
        ENGINE["latest_snapshot"]["pending_order_info"] = (
            f"Vstupní: {len(entry_ords)} | TP: {len(tp_ords)} | SL Algo: {len(algo_ords)}"
        )

    # Kontrola 5minutového timeoutu pro jakoukoliv nevyplněnou vstupní limitku (včetně zbytků po částečném plnění)
    now_s = time.time()
    if len(entry_ords) > 0:
        for eo in entry_ords:
            c_time_ms = float(eo.get("cTime", 0) or 0)
            age_sec = (now_s - (c_time_ms / 1000.0)) if c_time_ms > 0 else (now_s - at.get("created_at", now_s))
            if age_sec > ENTRY_ORDER_TIMEOUT_SEC:
                if cancel_okx_order(eo.get("ordId")):
                    add_ui_event(f"Zrušena nevyplněná vstupní limitka po {int(age_sec // 60)} min")
                    if pos_sz == 0:
                        with ENGINE["lock"]:
                            ENGINE["active_trade"]["active"] = False
                            ENGINE["has_open_or_pending"] = False
                        odesli_upozorneni(
                            "OKX_ENTRY_TIMEOUT",
                            f"⏱️ AI AGENT {APP_VERSION}: VSTUPNÍ LIMITKA ZRUŠENA (5 MIN TIMEOUT)",
                            (
                                f"Vstupní Maker příkaz ({at.get('direction', '')} @ {at.get('entry_px', 0.0):.0f}$) "
                                f"se nevyplnil do 5 minut a byl automaticky zrušen. Systém čeká na další čistou krabici."
                            ),
                            lock_duration=30,
                            force=True,
                        )
        if pos_sz == 0:
            return f"Čekám na vyplnění BBO/Retest limitky ({len(entry_ords)}x | max 5 min)"

    # SCÉNÁŘ 2: Otevřená pozice ➔ drž 1 čistý 100% Maker TP a SL pojistku (ŽÁDNÉ Auto-BE!)
    if pos_sz > 0:
        direction = pos_dir
        if not at.get("active") or at.get("tp_px", 0.0) <= 0:
            fallback_sl_pct = 0.0030
            sl_p = round(avg_px * (1.0 - fallback_sl_pct), 1) if direction == "LONG" else round(avg_px * (1.0 + fallback_sl_pct), 1)
            sl_d = abs(avg_px - sl_p)
            tp_p = round(avg_px + FIXED_TP_SL_MULT * sl_d, 1) if direction == "LONG" else round(avg_px - FIXED_TP_SL_MULT * sl_d, 1)
            at["active"] = True
            at["direction"] = direction
            at["entry_px"] = avg_px
            at["sl_px"] = sl_p
            at["tp_px"] = tp_p
            at["tp_placed_sz"] = 0
            at["tp_notified"] = False
            with ENGINE["lock"]:
                ENGINE["active_trade"].update(at)

        tp_px = float(at["tp_px"])
        sl_px = float(at["sl_px"])
        existing_tp_sz = sum(int(round(float(o.get("sz", 0) or 0))) for o in tp_ords)

        if existing_tp_sz != pos_sz:
            for old_tp in tp_ords:
                cancel_okx_order(old_tp.get("ordId"))
            ok_tp, tp_id_or_msg, used_type = place_single_maker_tp(direction, pos_sz, tp_px)
            if ok_tp:
                with ENGINE["lock"]:
                    ENGINE["active_trade"]["tp_ord_id"] = tp_id_or_msg
                    ENGINE["active_trade"]["tp_placed_sz"] = pos_sz
                    already_notified = bool(ENGINE["active_trade"].get("tp_notified", False))
                    ENGINE["active_trade"]["tp_notified"] = True
                add_ui_event(f"Vložen 100% TP ({pos_sz} ct @ {tp_px:.0f}$, {used_type})")
                if not already_notified:
                    odesli_upozorneni(
                        "OKX_TP_PLACED",
                        f"AI AGENT {APP_VERSION}: 100% MAKER TP VLOŽEN DO ORDERBOOKU",
                        (
                            f"🎯 Pozice {direction} ({pos_sz} ct) otevřena @ {avg_px:.1f}$.\n"
                            f"• 100 % Maker TP (2.3x SL): <b>{tp_px:.0f}$</b>\n"
                            f"• Ochranný SL (Market): <b>{sl_px:.0f}$</b>\n"
                            f"• Režim: 100 % čistý cíl (bez 50/50, bez Auto-BE)"
                        ),
                        lock_duration=30,
                        force=True,
                    )
            else:
                add_ui_event(f"Chyba vložení TP: {tp_id_or_msg}")

        if len(algo_ords) == 0 and sl_px > 0 and not at.get("sl_guard_checked", False):
            ok_sl = place_emergency_sl_algo(direction, pos_sz, sl_px)
            with ENGINE["lock"]:
                ENGINE["active_trade"]["sl_guard_checked"] = True
            if ok_sl:
                add_ui_event(f"SL pojistka doplněna @ {sl_px:.0f}$")

        return f"Aktivní pozice {direction} {pos_sz} ct @ {avg_px:.0f}$ | TP {tp_px:.0f}$ | SL {sl_px:.0f}$"

    # SCÉNÁŘ 3: Pozice uzavřena ➔ ukliď případné sirotčí příkazy
    if pos_sz == 0 and len(entry_ords) == 0:
        for orphan_tp in tp_ords:
            cancel_okx_order(orphan_tp.get("ordId"))
        for orphan_algo in algo_ords:
            cancel_okx_algo_order(orphan_algo.get("algoId"))
        if at.get("active"):
            with ENGINE["lock"]:
                ENGINE["active_trade"]["active"] = False
                ENGINE["active_trade"]["tp_placed_sz"] = 0
                ENGINE["active_trade"]["tp_notified"] = False
                ENGINE["active_trade"]["sl_guard_checked"] = False
            add_ui_event("Pozice na OKX uzavřena – systém připraven na další signál")
        return "Připraven (žádná aktivní pozice)"

    return "OK"


# ==============================================================================
# INFORMATIVNÍ MĚŘENÍ 1M DELTY PŘI VSTUPU (PRO AUDIT 6. 12. 2026 – NEBLOKUJE VSTUP)
# ==============================================================================
def analyze_1m_delta_snapshot(direction, confirm_1m_ts, c1f, fut_map=None):
    try:
        mf = c1f[:20][::-1] if len(c1f) >= 20 else c1f[::-1]
        if len(mf) < 3:
            return "NO_1M_DATA"

        anch_f = compute_anchored_1m_map(mf, fut_map, is_spot=False)
        deltas = [compute_single_1m_delta(c, is_spot=False, anchored_map=anch_f) for c in mf]
        ts_list = [int(c[0]) for c in mf]

        d_live = deltas[-1]
        d_prev1 = deltas[-2]
        post_box_deltas = [deltas[i] for i in range(len(mf)) if ts_list[i] > confirm_1m_ts]
        d_post = sum(post_box_deltas) if post_box_deltas else d_live

        if direction == "SHORT":
            weakening = (d_prev1 < 0.0) or (d_live < -1.0) or (d_post < -2.0)
        else:
            weakening = (d_prev1 > 0.0) or (d_live > 1.0) or (d_post > 2.0)

        tag = "WEAKENING_OK" if weakening else "STILL_PUSHING"
        return f"{tag} (1M uzavř.: {d_prev1:+.1f} | live: {d_live:+.1f} | po boxu: {d_post:+.1f} BTC)"
    except Exception:
        return "NO_1M_DATA"


# ==============================================================================
# STAHOVÁNÍ TRŽNÍCH DAT Z OKX (5M, 1M, CVD, SPOT, OI)
# ==============================================================================
def fetch_okx_data():
    poll_realtime_okx_flow()
    ts = int(time.time() * 1000)
    try:
        candles_300 = get_okx_candles("5m", 300, ts, [OKX_INST_ID, "BTC-USDT-SWAP"])
        fallback_p = float(candles_300[0][4]) if candles_300 else 60000.0
        btc_price = get_live_xperp_price(fallback_p, ts)

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

        vol_res = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&limit=100&t={ts}",
            timeout=5,
        ).json().get("data", [])
        fut_map = {}
        for row in vol_res:
            try:
                open_ts = int(row[0]) - 300000
                sell_usd, buy_usd = float(row[1]), float(row[2])
                ref_p = candle_close_map.get(open_ts, btc_price)
                fut_map[open_ts] = (buy_usd - sell_usd) / ref_p if ref_p > 0 else 0.0
            except Exception:
                continue

        spot_res = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SPOT&period=5m&limit=100&t={ts}",
            timeout=5,
        ).json().get("data", [])
        spot_map = {}
        for row in spot_res:
            try:
                open_ts = int(row[0]) - 300000
                spot_map[open_ts] = float(row[2]) - float(row[1])
            except Exception:
                continue

        candles_1m_fut = get_okx_candles("1m", 120, ts, ["BTC-USDT-SWAP", OKX_INST_ID])
        candles_1m_spot = get_okx_candles("1m", 120, ts, ["BTC-USDT"])

        live_open_ts = int(c_12_asc[-1][0]) if c_12_asc else 0
        if live_open_ts > 0:
            fut_map[live_open_ts] = get_1m_real_or_calibrated_delta(candles_1m_fut, live_open_ts, is_spot=False)
            spot_map[live_open_ts] = get_1m_real_or_calibrated_delta(candles_1m_spot, live_open_ts, is_spot=True)

        cvd_12 = [fut_map.get(int(c[0]), 0.0) for c in c_12_asc]
        scvd_12 = [spot_map.get(int(c[0]), 0.0) for c in c_12_asc]

        oi_res = requests.get(
            f"{OKX_PUBLIC_BASE_URL}/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&limit=100&t={ts}",
            timeout=5,
        ).json().get("data", [])
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

        cvd_1 = sum(cvd_12[-1:]) if len(cvd_12) >= 1 else 0.0
        cvd_5 = sum(cvd_12[-5:]) if len(cvd_12) >= 5 else 0.0
        cvd_9 = sum(cvd_12[-9:]) if len(cvd_12) >= 9 else 0.0

        scvd_1 = sum(scvd_12[-1:]) if len(scvd_12) >= 1 else 0.0
        scvd_5 = sum(scvd_12[-5:]) if len(scvd_12) >= 5 else 0.0
        scvd_9 = sum(scvd_12[-9:]) if len(scvd_12) >= 9 else 0.0

        oi_1 = sum(oi_12[-1:]) if len(oi_12) >= 1 else 0.0
        oi_5 = sum(oi_12[-5:]) if len(oi_12) >= 5 else 0.0
        oi_9 = sum(oi_12[-9:]) if len(oi_12) >= 9 else 0.0

        flow_metrics = (cvd_1, cvd_5, cvd_9, scvd_1, scvd_5, scvd_9, oi_1, oi_5, oi_9)
        return flow_metrics, candles_300, fut_map, spot_map, btc_price, candles_1m_fut
    except Exception:
        return (0.0,) * 9, [], {}, {}, 0.0, []
# === KONEC ČÁSTI 3 ===# === ZAČÁTEK ČÁSTI 4 ===

# ==============================================================================
# SETUP 1 SKENER v19.1: OKAMŽITÝ BBO MAKER VSTUP PO UZAVŘENÍ MEDIUM / MACRO BOXU
# ==============================================================================
def scan_setup_1(candles_300, candles_1m_fut, btc_price, fut_map, spot_map, flow_metrics):
    try:
        cfg = load_runtime_config()
        argon_boss_mode = cfg["ARGON_BOSS_MODE"]

        rem_s1 = get_setup_cooldown_remaining("S1_LOCK_1H", S1_COOLDOWN_SEC)
        locked_rank = get_s1_locked_rank() if rem_s1 > 0 else 0
        rank_name_map = {2: "MEDIUM", 3: "MACRO"}

        with ENGINE["lock"]:
            is_trade_busy = bool(ENGINE.get("has_open_or_pending", False))

        if is_trade_busy:
            return "🔒 Aktivní pozice nebo čekající limitka na OKX – čekám na dokončení obchodu.", False

        if rem_s1 > 0 and locked_rank >= 3:
            return f"🔒 Setup 1 [MACRO] uzamčen na 1H (zbývá {rem_s1 // 60 + 1} min).", False

        if len(candles_300) < 44 or btc_price <= 0:
            return "Načítám Top-Down 30M–180M strukturu svíček...", False

        c_42_desc = [list(c) for c in candles_300[1:43]]
        c_42_asc = c_42_desc[::-1]
        c_36_asc = c_42_asc[-36:]

        opens_36 = [float(c[1]) for c in c_36_asc]
        highs_36 = [float(c[2]) for c in c_36_asc]
        lows_36 = [float(c[3]) for c in c_36_asc]
        closes_36 = [float(c[4]) for c in c_36_asc]
        body_highs_36 = [max(opens_36[i], closes_36[i]) for i in range(36)]
        body_lows_36 = [min(opens_36[i], closes_36[i]) for i in range(36)]
        ts_36 = [int(c[0]) for c in c_36_asc]

        all_highs_42 = [float(c[2]) for c in c_42_asc]
        all_lows_42 = [float(c[3]) for c in c_42_asc]

        # POUZE 2 VARIANTY SETUPU 1: MACRO & MEDIUM (MICRO a Setup 2 odstraněny)
        groups_cfg = [
            # (name, min_bars, max_bars, max_spread%, req_touches, req_cvd, base_sl_pct)
            ("MACRO",  12, 36, 0.45, 3, 250.0, 0.0035),
            ("MEDIUM",  6, 18, 0.30, 2, 100.0, 0.0025),
        ]

        detected_dir = None
        detected_group = ""
        detected_label = ""
        detected_header = ""
        detected_confirm_ts = 0
        detected_last_5m_ts = 0
        detected_box_low = 0.0
        detected_box_high = 0.0
        detected_box_mid = 0.0
        detected_sl = 0.0025
        detected_mins = 0
        detected_spread = 0.0
        detected_cvd = 0.0
        detected_spot = 0.0

        status_summaries = []

        for g_name, min_b, max_b, max_spr, req_touches, req_cvd, g_sl in groups_cfg:
            g_rank = GROUP_RANK.get(g_name, 2)

            if rem_s1 > 0 and g_rank <= locked_rank:
                locked_lbl = rank_name_map.get(locked_rank, "S1")
                status_summaries.append(f"🔒 {g_name} (1H zámek po {locked_lbl} – povolen jen upgrade na MACRO)")
                continue

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
                status_summaries.append(f"{g_name}: {min_b*5}M uzavř. těla {base_spr:.2f}% nad {max_spr:.2f}%")
                continue

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

                half_k = max(1, k_test // 2)
                mean_first = sum(sub_c[:half_k]) / half_k
                mean_second = sum(sub_c[half_k:]) / max(1, k_test - half_k)
                slope_diff_pct = (abs(mean_second - mean_first) / box_min_b) * 100.0 if box_min_b > 0 else 0.0

                third_k = max(1, k_test // 3)
                m_t1 = sum(sub_c[:third_k]) / third_k
                m_t2 = sum(sub_c[third_k:2 * third_k]) / max(1, third_k)
                m_t3 = sum(sub_c[2 * third_k:]) / max(1, k_test - 2 * third_k)
                third_diff_pct = ((max(m_t1, m_t2, m_t3) - min(m_t1, m_t2, m_t3)) / box_min_b) * 100.0 if box_min_b > 0 else 0.0

                is_flat_box = (slope_diff_pct <= (max_spr * 0.35)) and (third_diff_pct <= (max_spr * 0.45))

                box_start_42 = 42 - k_test
                pre_start_42 = max(0, box_start_42 - 6)
                if box_start_42 > pre_start_42:
                    pre_min_p = min(all_lows_42[pre_start_42:box_start_42])
                    pre_max_p = max(all_highs_42[pre_start_42:box_start_42])
                else:
                    pre_min_p, pre_max_p = box_min_b, box_max_b

                pump_into_box_pct = ((box_max_b - pre_min_p) / pre_min_p) * 100.0 if pre_min_p > 0 else 0.0
                dump_into_box_pct = ((pre_max_p - box_min_b) / box_min_b) * 100.0 if box_min_b > 0 else 0.0
                impulse_limit_pct = max(0.42, max_spr * 1.35)

                block_long_after_pump = (pump_into_box_pct > impulse_limit_pct) and (box_min_b > (pre_min_p + (box_max_b - pre_min_p) * 0.45))
                block_short_after_dump = (dump_into_box_pct > impulse_limit_pct) and (box_max_b < (pre_max_p - (pre_max_p - box_min_b) * 0.45))

                cvd_all = sum(fut_map.get(t_o, 0.0) for t_o in sub_ts)
                cvd_no_first = sum(fut_map.get(t_o, 0.0) for t_o in sub_ts[1:]) if k_test > 3 else cvd_all
                box_cvd_short = max(cvd_all, cvd_no_first)
                box_cvd_long = min(cvd_all, cvd_no_first)
                box_spot_val = sum(spot_map.get(t_o, 0.0) for t_o in sub_ts)

                top_floor = box_max_b - (box_height * 0.25)
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
                    elif sub_l[idx_b] <= box_mid or sub_c[idx_b] <= box_mid:
                        if in_top_touch:
                            upper_touches.append(best_top_idx)
                            in_top_touch = False
                if in_top_touch:
                    upper_touches.append(best_top_idx)

                bot_ceil = box_min_b + (box_height * 0.25)
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
                    elif sub_h[idx_b] >= box_mid or sub_c[idx_b] >= box_mid:
                        if in_bot_touch:
                            lower_touches.append(best_bot_idx)
                            in_bot_touch = False
                if in_bot_touch:
                    lower_touches.append(best_bot_idx)

                both_boundaries_defined = (len(upper_touches) >= 1 and len(lower_touches) >= 1)
                end_in_upper = (sub_c[-1] >= box_mid or sub_h[-1] >= top_floor)
                end_in_lower = (sub_c[-1] <= box_mid or sub_l[-1] <= bot_ceil)

                if k_test == max_valid_k:
                    best_abs_cvd = box_cvd_short if abs(box_cvd_short) >= abs(box_cvd_long) else box_cvd_long
                    status_summaries.append(
                        f"{g_name} ({k_test*5}M uzavř. | {box_spr_pct:.2f}%≤{max_spr:.2f}% | T:{len(upper_touches)}↑/{len(lower_touches)}↓ | CVD {best_abs_cvd:+.0f}/{req_cvd:.0f})"
                    )

                box_lock_1m_ts = sub_ts[-1] + 240000

                if (
                    is_flat_box and both_boundaries_defined and not block_short_after_dump
                    and len(upper_touches) >= req_touches and end_in_upper and box_cvd_short > req_cvd
                ):
                    detected_dir = "SHORT"
                    detected_group = g_name
                    detected_label = f"SETUP 1 ({g_name}): BEARISH BOX"
                    detected_header = (
                        f"🔥 S1 [{g_name}] BEARISH BOX ({k_test*5}M uzavř. | Body {box_spr_pct:.2f}% ≤ {max_spr:.2f}% | "
                        f"{len(upper_touches)}x horní otest | CVD {box_cvd_short:+.1f} ≥ +{req_cvd:.0f} BTC [Spot bg: {box_spot_val:+.1f}])"
                    )
                    detected_confirm_ts = box_lock_1m_ts
                    detected_last_5m_ts = sub_ts[-1]
                    detected_box_low = min(sub_l)
                    detected_box_high = max(sub_h)
                    detected_box_mid = box_mid
                    detected_sl = g_sl
                    detected_mins = k_test * 5
                    detected_spread = box_spr_pct
                    detected_cvd = box_cvd_short
                    detected_spot = box_spot_val
                    break

                elif (
                    is_flat_box and both_boundaries_defined and not block_long_after_pump
                    and len(lower_touches) >= req_touches and end_in_lower and box_cvd_long < -req_cvd
                ):
                    detected_dir = "LONG"
                    detected_group = g_name
                    detected_label = f"SETUP 1 ({g_name}): BULLISH BOX"
                    detected_header = (
                        f"🔥 S1 [{g_name}] BULLISH BOX ({k_test*5}M uzavř. | Body {box_spr_pct:.2f}% ≤ {max_spr:.2f}% | "
                        f"{len(lower_touches)}x spodní otest | CVD {box_cvd_long:+.1f} ≤ -{req_cvd:.0f} BTC [Spot bg: {box_spot_val:+.1f}])"
                    )
                    detected_confirm_ts = box_lock_1m_ts
                    detected_last_5m_ts = sub_ts[-1]
                    detected_box_low = min(sub_l)
                    detected_box_high = max(sub_h)
                    detected_box_mid = box_mid
                    detected_sl = g_sl
                    detected_mins = k_test * 5
                    detected_spread = box_spr_pct
                    detected_cvd = box_cvd_long
                    detected_spot = box_spot_val
                    break

            if detected_dir is not None:
                break

        if detected_dir is None:
            return " 📦 ".join(status_summaries), False

        # Zabraň opakovanému vyhodnocování úplně stejné uzavřené 5M krabice během stejného 5M bloku
        box_key = f"{detected_last_5m_ts}_{detected_group}_{detected_dir}"
        with ENGINE["lock"]:
            if ENGINE["s1_memory"].get("last_eval_box_key", "") == box_key:
                return f"{detected_header}\n⏳ Tato krabice už byla v aktuálním 5M okně vyhodnocena.", False

        # Kontrola živého BBO a pozice ceny vůči krabici (ŽÁDNÉ čekání na Bod B/C, ŽÁDNÉ honění dna!)
        last_bbo, bid_p, ask_p = get_okx_live_bbo(OKX_INST_ID)
        live_ref = last_bbo if last_bbo > 0 else btc_price
        bid_use = bid_p if bid_p > 0 else live_ref
        ask_use = ask_p if ask_p > 0 else live_ref

        if detected_dir == "SHORT":
            if live_ref > detected_box_high * (1.0 + BOX_INVALIDATION_PCT):
                with ENGINE["lock"]:
                    ENGINE["s1_memory"]["last_eval_box_key"] = box_key
                return f"{detected_header}\n❌ Invalidace: cena ({live_ref:.0f}$) už prorazila nad strop krabice ({detected_box_high:.0f}$).", False
            if live_ref < detected_box_low * (1.0 - MAX_MISSED_BREAKOUT_PCT):
                with ENGINE["lock"]:
                    ENGINE["s1_memory"]["last_eval_box_key"] = box_key
                return f"{detected_header}\n⏭️ Ujetý vlak: cena ({live_ref:.0f}$) už spadla >0.50 % pod dno krabice ({detected_box_low:.0f}$).", False

            if ask_use >= detected_box_low:
                target_entry = round(ask_use, 1)
                entry_mode = "BBO_IN_BOX"
            else:
                target_entry = round(detected_box_low, 1)
                entry_mode = "RETEST_BOX_EDGE"
        else:
            if live_ref < detected_box_low * (1.0 - BOX_INVALIDATION_PCT):
                with ENGINE["lock"]:
                    ENGINE["s1_memory"]["last_eval_box_key"] = box_key
                return f"{detected_header}\n❌ Invalidace: cena ({live_ref:.0f}$) už prorazila pod dno krabice ({detected_box_low:.0f}$).", False
            if live_ref > detected_box_high * (1.0 + MAX_MISSED_BREAKOUT_PCT):
                with ENGINE["lock"]:
                    ENGINE["s1_memory"]["last_eval_box_key"] = box_key
                return f"{detected_header}\n⏭️ Ujetý vlak: cena ({live_ref:.0f}$) už utekla >0.50 % nad strop krabice ({detected_box_high:.0f}$).", False

            if bid_use <= detected_box_high:
                target_entry = round(bid_use, 1)
                entry_mode = "BBO_IN_BOX"
            else:
                target_entry = round(detected_box_high, 1)
                entry_mode = "RETEST_BOX_EDGE"

        # Informativní stav 1M delty v okamžiku vstupu (pro audit 6. 12.)
        delta_1m_state = analyze_1m_delta_snapshot(detected_dir, detected_confirm_ts, candles_1m_fut, fut_map)

        t_payload = build_trade_plan(
            direction=detected_dir,
            entry_px=target_entry,
            setup_label=detected_label,
            group_id=detected_group,
            sl_pct=detected_sl,
        )
        t_payload["trigger_ready"] = True
        t_payload["box_low_p"] = detected_box_low
        t_payload["box_high_p"] = detected_box_high
        t_payload["entry_mode"] = entry_mode

        ai_eval = evaluate_argon4_background(
            group_id=detected_group,
            direction=detected_dir,
            t_payload=t_payload,
            candles_300=candles_300,
            flow_metrics=flow_metrics,
            box_spot=detected_spot,
            spot_map=spot_map,
            box_low_p=detected_box_low,
            box_high_p=detected_box_high,
        )

        vp3 = ai_eval["vp_3h"]
        vp6 = ai_eval["vp_6h"]
        cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9 = flow_metrics
        now_dt = get_prague_now()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        sess_tag = classify_prague_session(now_dt)

        mode_txt = "BBO uvnitř krabice" if entry_mode == "BBO_IN_BOX" else "Retest hrany krabice (5 min)"
        entry_txt = (
            f"✅ OKAMŽITÝ MAKER {detected_dir} [{mode_txt}] | Vstup: {target_entry:.0f}$ ({POSITION_SIZE_USD:.0f}$) | "
            f"Argon SL ({ai_eval['rec_sl_pct']*100:.2f}%): {ai_eval['rec_sl_px']:.0f}$ | 100% TP (2.3x): {ai_eval['rec_tp_px']:.0f}$"
        )
        msg = f"{detected_header}\n{entry_txt}"

        with ENGINE["lock"]:
            ENGINE["s1_memory"]["last_eval_box_key"] = box_key

        if argon_boss_mode and not ai_eval["approved"]:
            agent_msg = f"🛑 ARGON 4 BOSS {APP_VERSION}: OBCHOD ZAMÍTNUT (Důvod: {ai_eval['ai_comment']})"
            log_block = (
                f"\n📊 <b>DATA PRO ANALÝZU (ZAMÍTNUTO {APP_VERSION}):</b>\n"
                f"• Čas: {now_str} | Okno: {sess_tag} | Skupina: {detected_group} | Směr: {detected_dir} | Režim vstupu: {entry_mode}\n"
                f"• 📉 1M Delta při vstupu (info pro 6.12.): {delta_1m_state}\n"
                f"• Krabice: {detected_mins}M uzavř. ({detected_box_low:.0f}$–{detected_box_high:.0f}$) | Box CVD: {detected_cvd:+.1f}\n"
                f"• Trend: {ai_eval['trend_3h']} ({ai_eval['trend_alignment']})\n"
                f"• 3H VP: VAH {vp3['vah']:.0f}$ / POC {vp3['poc']:.0f}$ / VAL {vp3['val']:.0f}$\n"
                f"• 6H VP: VAH {vp6['vah']:.0f}$ / POC {vp6['poc']:.0f}$ / VAL {vp6['val']:.0f}$"
            )
            msg += f"\n{agent_msg}{log_block}"
            tg_msg = msg + ai_eval["telegram_block"]

            sent_veto = odesli_upozorneni(
                f"S1_VETO_{detected_group}_{detected_dir}",
                f"🛑 ZAMÍTNUTO ARGONEM 4 {APP_VERSION}: S1 [{detected_group}] {detected_dir}",
                tg_msg,
                lock_duration=900,
                force=False,
            )
            if sent_veto:
                add_ui_event(f"VETO S1 [{detected_group}] {detected_dir} ({ai_eval['trend_alignment']})")
                log_weekly_trade_event({
                    "timestamp": now_str,
                    "version": APP_VERSION,
                    "session_tag": sess_tag,
                    "setup": f"SETUP_1_{detected_group}_VETO",
                    "group": detected_group,
                    "direction": detected_dir,
                    "position_usd": 0.0,
                    "entry": t_payload["entry"],
                    "sl": ai_eval["rec_sl_px"],
                    "sl_pct": round(ai_eval["rec_sl_pct"] * 100.0, 2),
                    "tp": ai_eval["rec_tp_px"],
                    "tp_pct": round(ai_eval["rec_tp_pct"] * 100.0, 2),
                    "raw_rrr": ai_eval["raw_rrr"],
                    "real_net_rrr": ai_eval["real_net_rrr"],
                    "pb_pct": 0.0,
                    "box_mins": detected_mins,
                    "box_body_spread_pct": round(detected_spread, 2),
                    "box_low": round(detected_box_low, 1),
                    "box_high": round(detected_box_high, 1),
                    "box_mid": round(detected_box_mid, 1),
                    "box_cvd": round(detected_cvd, 1),
                    "box_spot_bg": round(detected_spot, 1),
                    "trend_regime": ai_eval["trend_regime"],
                    "trend_alignment": ai_eval["trend_alignment"],
                    "trend_3h_6h_detail": ai_eval["trend_3h"],
                    "spot_3h_6h": ai_eval["spot_3h_6h"],
                    "cvd_5m_25m_45m": [round(cvd1, 1), round(cvd5, 1), round(cvd9, 1)],
                    "spot_5m_25m_45m": [round(scvd1, 1), round(scvd5, 1), round(scvd9, 1)],
                    "oi_5m_25m_45m": [round(oi1, 1), round(oi5, 1), round(oi9, 1)],
                    "vp_3h_vah_poc_val": [round(vp3["vah"], 0), round(vp3["poc"], 0), round(vp3["val"], 0)],
                    "vp_6h_vah_poc_val": [round(vp6["vah"], 0), round(vp6["poc"], 0), round(vp6["val"], 0)],
                    "vp_confluences_3h_6h": ai_eval["vp_confluences"],
                    "vp_obstacles_to_tp": ai_eval["vp_obstacles"],
                    "agent_status": agent_msg,
                    "ai_verdict": ai_eval["verdict"],
                    "ai_score": ai_eval["score"],
                    "ai_comment": ai_eval["ai_comment"],
                    "entry_mode": entry_mode,
                    "entry_1m_delta_state": delta_1m_state,
                })
            return msg, False

        t_payload["sl_market"] = float(ai_eval["rec_sl_px"])
        t_payload["sl_pct"] = float(ai_eval["rec_sl_pct"])
        t_payload["tp_limit"] = float(ai_eval["rec_tp_px"])
        t_payload["tp_pct"] = float(ai_eval["rec_tp_pct"])
        t_payload["real_net_rrr"] = float(ai_eval["real_net_rrr"])

        exec_ok, agent_msg = execute_okx_agent_trade(t_payload)
        final_entry_mode = t_payload.get("entry_mode", entry_mode)

        log_block = (
            f"\n📊 <b>DATA PRO ANALÝZU ({APP_VERSION} – 6.12. AUDIT):</b>\n"
            f"• Čas: {now_str} | Okno: <b>{sess_tag}</b> | Skupina: {detected_group} | Směr: {detected_dir} | Pozice: {POSITION_SIZE_USD:.0f}$\n"
            f"• Režim vstupu: <b>{final_entry_mode}</b> | Argon SL ({t_payload['sl_pct']*100:.2f}%): <b>{t_payload['sl_market']:.0f}$</b> | 100% TP (2.3x SL): <b>{t_payload['tp_limit']:.0f}$</b>\n"
            f"• 📉 1M Delta při vstupu (info pro 6.12.): <b>{delta_1m_state}</b>\n"
            f"• Krabice: {detected_mins}M uzavř. ({detected_box_low:.0f}$–{detected_box_high:.0f}$) | Střed: {detected_box_mid:.0f}$ | Box CVD: {detected_cvd:+.1f} | Box Spot: {detected_spot:+.1f}\n"
            f"• Matrix 5M/25M/45M: CVD ({cvd1:+.1f}/{cvd5:+.1f}/{cvd9:+.1f}) | Spot ({scvd1:+.1f}/{scvd5:+.1f}/{scvd9:+.1f}) | OI ({oi1:+.1f}/{oi5:+.1f}/{oi9:+.1f})\n"
            f"• Spot Trend: {ai_eval['spot_3h_6h']} | Trend: {ai_eval['trend_3h']}\n"
            f"• 3H VP: VAH {vp3['vah']:.0f}$ / POC {vp3['poc']:.0f}$ / VAL {vp3['val']:.0f}$\n"
            f"• 6H VP: VAH {vp6['vah']:.0f}$ / POC {vp6['poc']:.0f}$ / VAL {vp6['val']:.0f}$"
        )
        msg += f"\n{agent_msg}{log_block}"
        tg_msg = msg + ai_eval["telegram_block"]

        if exec_ok:
            log_weekly_trade_event({
                "timestamp": now_str,
                "version": APP_VERSION,
                "session_tag": sess_tag,
                "setup": f"SETUP_1_{detected_group}",
                "group": detected_group,
                "direction": detected_dir,
                "position_usd": POSITION_SIZE_USD,
                "entry": t_payload["entry"],
                "sl": t_payload["sl_market"],
                "sl_pct": round(t_payload["sl_pct"] * 100.0, 2),
                "tp": t_payload["tp_limit"],
                "tp_pct": round(t_payload["tp_pct"] * 100.0, 2),
                "raw_rrr": 2.30,
                "real_net_rrr": t_payload["real_net_rrr"],
                "pb_pct": 0.0,
                "box_mins": detected_mins,
                "box_body_spread_pct": round(detected_spread, 2),
                "box_low": round(detected_box_low, 1),
                "box_high": round(detected_box_high, 1),
                "box_mid": round(detected_box_mid, 1),
                "box_cvd": round(detected_cvd, 1),
                "box_spot_bg": round(detected_spot, 1),
                "trend_regime": ai_eval["trend_regime"],
                "trend_alignment": ai_eval["trend_alignment"],
                "trend_3h_6h_detail": ai_eval["trend_3h"],
                "spot_3h_6h": ai_eval["spot_3h_6h"],
                "cvd_5m_25m_45m": [round(cvd1, 1), round(cvd5, 1), round(cvd9, 1)],
                "spot_5m_25m_45m": [round(scvd1, 1), round(scvd5, 1), round(scvd9, 1)],
                "oi_5m_25m_45m": [round(oi1, 1), round(oi5, 1), round(oi9, 1)],
                "vp_3h_vah_poc_val": [round(vp3["vah"], 0), round(vp3["poc"], 0), round(vp3["val"], 0)],
                "vp_6h_vah_poc_val": [round(vp6["vah"], 0), round(vp6["poc"], 0), round(vp6["val"], 0)],
                "vp_confluences_3h_6h": ai_eval["vp_confluences"],
                "vp_obstacles_to_tp": ai_eval["vp_obstacles"],
                "agent_status": agent_msg,
                "ai_verdict": ai_eval["verdict"],
                "ai_score": ai_eval["score"],
                "ai_comment": ai_eval["ai_comment"],
                "entry_mode": final_entry_mode,
                "entry_1m_delta_state": delta_1m_state,
            })
            set_s1_locked_rank(GROUP_RANK.get(detected_group, 3))
            odesli_upozorneni(
                "S1_LOCK_1H",
                f"SETUP 1 [{detected_group}]: {detected_dir} SCHVÁLENO ARGONEM 4 {APP_VERSION}",
                tg_msg,
                lock_duration=S1_COOLDOWN_SEC,
                force=True,
            )
        return msg, bool(exec_ok)
    except Exception as e:
        return f"Načítám data Setupu 1 ({e})...", False


# ==============================================================================
# POZADÍ 24/7 NONSTOP SMYČKA
# ==============================================================================
def run_single_scan_cycle():
    agent_state = manage_active_okx_lifecycle()
    flow_metrics, candles_300, fut_map, spot_map, btc_price, candles_1m_fut = fetch_okx_data()

    if btc_price > 0 and len(candles_300) >= 36:
        vp3 = compute_vp_from_candles(candles_300, 36)
        vp6 = compute_vp_from_candles(candles_300, 72)
        trend_regime, trend_detail, _, _, _ = compute_3h_6h_trend(candles_300, btc_price)
        c_3h_ts = [int(c[0]) for c in candles_300[:36]]
        c_6h_ts = [int(c[0]) for c in candles_300[:72]]
        spot_3h = sum(spot_map.get(t, 0.0) for t in c_3h_ts)
        spot_6h = sum(spot_map.get(t, 0.0) for t in c_6h_ts)
        s1_msg, _ = scan_setup_1(candles_300, candles_1m_fut, btc_price, fut_map, spot_map, flow_metrics)
    else:
        vp3 = {"vah": 0.0, "poc": 0.0, "val": 0.0}
        vp6 = {"vah": 0.0, "poc": 0.0, "val": 0.0}
        trend_regime, trend_detail = "CHOP", "Čekám na data svíček..."
        spot_3h, spot_6h = 0.0, 0.0
        s1_msg = "Čekám na data z OKX..."

    now_dt = get_prague_now()
    with ENGINE["lock"]:
        ENGINE["last_heartbeat"] = time.time()
        ENGINE["last_cycle_error"] = ""
        ENGINE["latest_snapshot"].update({
            "updated_str": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "btc_price": btc_price,
            "session_tag": classify_prague_session(now_dt),
            "s1_status": s1_msg,
            "agent_status": agent_state,
            "vp_3h": vp3,
            "vp_6h": vp6,
            "trend_regime": trend_regime,
            "trend_detail": trend_detail,
            "spot_3h": spot_3h,
            "spot_6h": spot_6h,
            "flow_metrics": flow_metrics,
        })


def _background_scanner_loop():
    while True:
        try:
            run_single_scan_cycle()
        except Exception as e:
            with ENGINE["lock"]:
                ENGINE["last_cycle_error"] = str(e)
        time.sleep(SCAN_INTERVAL_SEC)


def start_background_engine():
    with ENGINE["lock"]:
        if ENGINE["thread_started"]:
            return
        t = threading.Thread(target=_background_scanner_loop, daemon=True, name="argon4_v19_loop")
        t.start()
        ENGINE["thread_started"] = True
        add_ui_event(f"Spuštěn 24/7 NONSTOP motor ARGON 4 BOSS {APP_VERSION}")


# ==============================================================================
# DIAGNOSTICKÝ TEST SPOJENÍ (TELEGRAM + OKX + GEMINI + SIMULACE)
# ==============================================================================
def run_connection_test():
    cfg = load_runtime_config()
    flow_metrics, candles_300, fut_map, spot_map, btc_price, _ = fetch_okx_data()
    if btc_price <= 0:
        btc_price = 60000.0

    okx_cfg = okx_signed_request("GET", "/api/v5/account/config")
    if okx_cfg.get("code") == "0":
        pos_mode = get_okx_pos_mode()
        okx_status = f"🟢 OKX API připojeno ({pos_mode} | Pozice {POSITION_SIZE_USD:.0f}$ | 1x čistý vstup)"
    elif cfg["OKX_API_KEY"]:
        okx_status = f"🟠 OKX API klíče načteny, ale chyba spojení: {okx_cfg.get('msg', 'neznámá')}"
    else:
        okx_status = "🔴 OKX API klíče chybí"

    ai_status = "🟢 Google AI Studio (Argon 4) propojeno" if cfg["GEMINI_API_KEY"] else "🟠 Chybí GEMINI_API_KEY (běží lokální jádro)"
    boss_status = "🟢 PLNÁ PRAVOMOC (BOSS MODE ZAPNUTÝ)" if cfg["ARGON_BOSS_MODE"] else "🟡 PASIVNÍ REŽIM"
    exec_mode = "🧪 DRY-RUN" if cfg["DRY_RUN"] else ("🟢 LIVE EXEKUCE" if cfg["AI_TRADING_ENABLED"] else "⏸️ EXEKUCE VYPNUTA")

    test_dir = "SHORT"
    test_plan = build_trade_plan(test_dir, btc_price, "TEST S1 (MEDIUM)", group_id="MEDIUM", sl_pct=0.0025)
    test_eval = evaluate_argon4_background(
        group_id="MEDIUM",
        direction=test_dir,
        t_payload=test_plan,
        candles_300=candles_300,
        flow_metrics=flow_metrics,
        box_spot=0.0,
        spot_map=spot_map,
        box_low_p=btc_price * 0.9990,
        box_high_p=btc_price * 1.0010,
    )
    vp3 = test_eval["vp_3h"]
    vp6 = test_eval["vp_6h"]
    sess_tag = classify_prague_session()

    body = (
        f"✅ <b>Režim 24/7 NONSTOP s ARGON 4 BOSS MODE {APP_VERSION} běží!</b>\n"
        f"• Aktivní strategie: <b>Pouze Setup 1 (MEDIUM + MACRO)</b> | Okamžitý BBO Maker vstup\n"
        f"• Trendový filtr: <b>Pouze CHOP + WITH_TREND</b> (tvrdý zákaz proti MILD i STRONG trendu)\n"
        f"• Argon SL pásma: <b>MEDIUM 0.25–0.30 %</b> | <b>MACRO 0.35–0.45 %</b> (kryté za VP/Swingy)\n"
        f"• Výstup: <b>100 % pozice na pevný Maker TP = 2.3x SL</b> (1 vstup, bez 50/50, bez Auto-BE)\n"
        f"• Velikost pozice: <b>{POSITION_SIZE_USD:.0f} USD</b> | Aktuální okno: <b>{sess_tag}</b>\n"
        f"• 3H VP: VAH {vp3['vah']:.0f}$ / POC {vp3['poc']:.0f}$ / VAL {vp3['val']:.0f}$\n"
        f"• 6H VP: VAH {vp6['vah']:.0f}$ / POC {vp6['poc']:.0f}$ / VAL {vp6['val']:.0f}$\n"
        f"• Zapsané obchody v CSV: <b>{count_csv_rows()}</b>\n"
        f"• Stav OKX: {okx_status} | {exec_mode}\n"
        f"• Stav Mozku: {ai_status} | {boss_status}\n"
        f"• Live BTC: <b>{btc_price:.1f}$</b>"
        f"{test_eval['telegram_block']}"
    )
    sent = odesli_upozorneni("TEST_CONN", f"TEST SPOJENÍ TERMINÁL (ARGON 4 BOSS MODE {APP_VERSION})", body, lock_duration=0, force=True)
    return sent, okx_status


# ==============================================================================
# STREAMLIT TERMINÁL UI (S AUTOMATICKÝM REFRESHEM KAŽDÝCH 20 VTEŘIN)
# ==============================================================================
UI_AUTO_REFRESH_SEC = 20

st.set_page_config(
    page_title=f"ARGON 4 BOSS {APP_VERSION} | BTC Orderflow",
    page_icon="⚡",
    layout="wide",
)

start_background_engine()

st.markdown(
    """
    <style>
    .stApp { background-color: #0b0f17; color: #e2e8f0; }
    .metric-box {
        background-color: #111827; border: 1px solid #1f2937;
        border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
    }
    .accent { color: #f7931a; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(f"⚡ ARGON 4 BOSS MODE {APP_VERSION}")
st.caption("Čistý Setup 1 (MEDIUM 0.25–0.30% | MACRO 0.35–0.45%) • BBO Maker vstup • Trend: CHOP + WITH_TREND • 100% Fixní Maker TP = 2.3x SL • 24/7 NONSTOP")

c_btn1, c_btn2, c_btn3, c_btn4 = st.columns(4)
with c_btn1:
    if st.button("📲 OTESTOVAT SPOJENÍ", use_container_width=True):
        with st.spinner(f"Testuji OKX, Telegram a Argon 4 {APP_VERSION}..."):
            ok_tg, okx_st = run_connection_test()
        if ok_tg:
            st.success(f"Telegram test odeslán! {okx_st}")
        else:
            st.error("Nepodařilo se odeslat Telegram zprávu – zkontroluj Secrets.")
with c_btn2:
    if st.button("🔄 Obnovit data hned", use_container_width=True):
        run_single_scan_cycle()
        st.rerun()
with c_btn3:
    if st.button("🔓 Resetovat 1H zámek S1", use_container_width=True):
        with ENGINE["lock"]:
            ENGINE["cooldowns"]["S1_LOCK_1H"] = 0.0
            ENGINE["s1_locked_rank"] = 0
            ENGINE["s1_memory"]["active"] = False
            ENGINE["s1_memory"]["last_eval_box_key"] = ""
        add_ui_event("Ruční reset 1H zámku S1")
        st.success("Zámek S1 a paměť krabice resetovány.")
with c_btn4:
    if os.path.exists(CSV_LOG_PATH):
        with open(CSV_LOG_PATH, "rb") as f_csv:
            st.download_button(
                label=f"📥 Stáhnout CSV ({count_csv_rows()})",
                data=f_csv.read(),
                file_name=CSV_LOG_PATH,
                mime="text/csv",
                use_container_width=True,
            )
    else:
        st.button("📥 CSV zatím prázdné (0)", disabled=True, use_container_width=True)

auto_refresh_on = st.toggle(f"🔄 Automatický refresh displeje každých {UI_AUTO_REFRESH_SEC} s", value=True)


def _render_live_dashboard_body():
    with ENGINE["lock"]:
        snap = dict(ENGINE["latest_snapshot"])
        hb_age = int(time.time() - ENGINE["last_heartbeat"]) if ENGINE["last_heartbeat"] > 0 else -1
        last_err = ENGINE["last_cycle_error"]

    cfg_now = load_runtime_config()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Live BTC (XPERP)", f"{snap['btc_price']:.1f} $")
    m2.metric("Trend (3H+6H)", snap["trend_regime"])
    m3.metric("Aktuální okno (CET)", snap["session_tag"] or classify_prague_session())
    hb_txt = f"OK ({hb_age}s)" if hb_age >= 0 else "Startuji..."
    m4.metric("24/7 Heartbeat", hb_txt)

    if last_err:
        st.warning(f"Poslední chyba cyklu: {last_err}")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📦 Setup 1 Skener (MEDIUM + MACRO)")
        st.info(snap["s1_status"])
        vp3 = snap["vp_3h"]
        vp6 = snap["vp_6h"]
        st.markdown(
            f"""
            <div class="metric-box">
            <b>3H Volume Profile:</b> VAH <code>{vp3['vah']:.0f}$</code> | POC <code>{vp3['poc']:.0f}$</code> | VAL <code>{vp3['val']:.0f}$</code><br>
            <b>6H Volume Profile:</b> VAH <code>{vp6['vah']:.0f}$</code> | POC <code>{vp6['poc']:.0f}$</code> | VAL <code>{vp6['val']:.0f}$</code><br>
            <b>Trend detail:</b> {snap['trend_detail']}<br>
            <b>Spot 3H / 6H:</b> {snap['spot_3h']:+.1f} BTC / {snap['spot_6h']:+.1f} BTC
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        st.subheader("🤖 OKX AI Agent & Flow Matrix")
        st.success(snap["agent_status"])
        cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9 = snap["flow_metrics"]
        exec_lbl = "🧪 DRY-RUN" if cfg_now["DRY_RUN"] else ("🟢 LIVE (500 $)" if cfg_now["AI_TRADING_ENABLED"] else "⏸️ VYPNUTO")
        st.markdown(
            f"""
            <div class="metric-box">
            <b>Režim exekuce:</b> {exec_lbl} | <b>Boss Mode:</b> {'ZAP' if cfg_now['ARGON_BOSS_MODE'] else 'VYP'}<br>
            <b>Pozice OKX:</b> {snap['open_position_info']}<br>
            <b>Čekající příkazy:</b> {snap['pending_order_info']}<br>
            <b>CVD (5M/25M/45M):</b> {cvd1:+.1f} / {cvd5:+.1f} / {cvd9:+.1f} BTC<br>
            <b>Spot (5M/25M/45M):</b> {scvd1:+.1f} / {scvd5:+.1f} / {scvd9:+.1f} BTC<br>
            <b>OI (5M/25M/45M):</b> {oi1:+.1f} / {oi5:+.1f} / {oi9:+.1f} BTC
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("📜 Poslední události terminálu")
    events = snap.get("recent_events", [])
    if events:
        st.code("\n".join(events), language="text")
    else:
        st.caption("Zatím žádné události.")

    st.caption(f"Poslední aktualizace dat: {snap['updated_str']} (CET) | Zapsané obchody v CSV: {count_csv_rows()}")


if hasattr(st, "fragment"):
    @st.fragment(run_every=UI_AUTO_REFRESH_SEC if auto_refresh_on else None)
    def render_live_dashboard():
        _render_live_dashboard_body()

    render_live_dashboard()
else:
    _render_live_dashboard_body()
# === KONEC ČÁSTI 4 ===



