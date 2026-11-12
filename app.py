import os
import sys
import json
import time
import uuid
import threading
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- NASTAVENÍ TELEGRAM NOTIFIKACÍ ---
TELEGRAM_BOT_TOKEN = "9068673685:AAEwXgVLOdO-kZ3Pvm3ATu87vZ6eZ-zP-cY"
TELEGRAM_CHAT_ID = "9209356727"

# --- PŘÍPRAVA PRO NAPOJENÍ NA GOOGLE SHEET OKX AI AGENTA (WEBHOOK) ---
GOOGLE_SHEET_WEBHOOK_URL = ""

# --- SOUBOROVÝ BUFFER NA DISKU SERVERU (PŘEŽIJE KAŽDÝ RELOAD I VLÁKNA) ---
ALERT_STATE_FILE = "/tmp/okx_telegram_buffer_v3.json"

@st.cache_resource
def get_realtime_engine():
    # Globální zámek v sys.__dict__, aby ho sdílela naprosto všechna vlákna v procesu
    if "OKX_GLOBAL_LOCK" not in sys.__dict__:
        sys.__dict__["OKX_GLOBAL_LOCK"] = threading.Lock()
    return {
        "lock": sys.__dict__["OKX_GLOBAL_LOCK"],
        "fut_buckets": {},
        "spot_buckets": {},
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
        }
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

def odesli_do_google_sheet_agenta(payload_data):
    if not GOOGLE_SHEET_WEBHOOK_URL:
        return False
    try:
        res = requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload_data, timeout=5)
        return res.status_code == 200
    except Exception:
        return False

def odesli_upozorneni(setup_id_key, setup_nazev, detail_zpravy, cooldown_sec=3600, category_key="GLOBAL_SETUP1", category_cooldown=1800, force=False, trade_payload=None):
    now_ts = time.time()
    with ENGINE["lock"]:
        history = _load_alert_history()
        if not force:
            # 1. Globální protispamový buffer (min. 60 vteřin mezi jakýmikoliv zprávami)
            last_any = float(history.get("ANY_ALERT_TS", 0.0))
            if (now_ts - last_any) < 60.0:
                return False

            # 2. Buffer pro celou kategorii (např. celý SETUP 1 má 30 minut = 1800s stopku po 1. zprávě)
            if category_key:
                last_cat = float(history.get(category_key, 0.0))
                if (now_ts - last_cat) < category_cooldown:
                    return False

            # 3. Buffer pro konkrétní směr/zónu (výchozí 60 minut = 3600s)
            last_specific = float(history.get(setup_id_key, 0.0))
            if (now_ts - last_specific) < cooldown_sec:
                return False

        # Zápis okamžitě na disk ještě před odesláním, aby žádné paralelní vlákno neposlalo duplikát
        history["ANY_ALERT_TS"] = now_ts
        history[setup_id_key] = now_ts
        if category_key:
            history[category_key] = now_ts
        _save_alert_history(history)

    if trade_payload is not None:
        odesli_do_google_sheet_agenta(trade_payload)

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
    if now_p.weekday() >= 5:
        return False, f"⏸️ VÍKENDOVÝ REŽIM ({now_p.strftime('%H:%M')}) – Alarmy vypnuty"
    
    mins = now_p.hour * 60 + now_p.minute
    in_asia = (2 * 60) <= mins < (5 * 60)
    in_london = (9 * 60) <= mins <= (10 * 60 + 30)
    in_ny = (14 * 60) <= mins < (19 * 60)
    
    if in_asia or in_london or in_ny:
        return True, f"🟢 LIKVIDNÍ OKNO AKTIVNÍ ({now_p.strftime('%H:%M')}) | 24/7 Cloud Hlídač + 30m Buffer zapnutý"
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

@st.cache_data(ttl=3600)
def get_contract_spec(inst_id):
    for inst_type in ["SWAP", "FUTURES"]:
        for host in ["https://eea.okx.com", "https://www.okx.com"]:
            try:
                url = f"{host}/api/v5/public/instruments?instType={inst_type}&instId={inst_id}"
                data = requests.get(url, timeout=3).json().get("data", [])
                if data:
                    ct_val = float(data[0].get("ctVal", 0.0001))
                    ct_ccy = data[0].get("ctValCcy", "BTC")
                    return ct_val, ct_ccy
            except Exception:
                continue
    if "UM_XPERP" in inst_id or "USDC" in inst_id:
        return 0.0001, "BTC"
    elif "USDT" in inst_id:
        return 0.01, "BTC"
    return 100.0, "USD"

def to_btc_vol(raw_contracts, price, ct_val, ct_ccy):
    if ct_ccy == "BTC":
        return raw_contracts * ct_val
    return (raw_contracts * ct_val) / price if price > 0 else 0.0

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
                    bucket = (t_ts // 300000) * 300000
                    vol_btc = float(tr["sz"]) * 0.01
                    delta = vol_btc if tr.get("side") == "buy" else -vol_btc
                    ENGINE["fut_buckets"][bucket] = ENGINE["fut_buckets"].get(bucket, 0.0) + delta
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
                    bucket = (t_ts // 300000) * 300000
                    vol_btc = float(tr["sz"])
                    delta = vol_btc if tr.get("side") == "buy" else -vol_btc
                    ENGINE["spot_buckets"][bucket] = ENGINE["spot_buckets"].get(bucket, 0.0) + delta
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

def get_1m_real_or_calibrated_delta(candles_1m, candle_open_ts, is_spot=False, scale_factor=0.18):
    with ENGINE["lock"]:
        bucket_map = ENGINE["spot_buckets"] if is_spot else ENGINE["fut_buckets"]
        real_collected = bucket_map.get(candle_open_ts, 0.0)

    sub_delta = 0.0
    for m in candles_1m:
        try:
            m_ts = int(m[0])
            if candle_open_ts <= m_ts < candle_open_ts + 300000:
                o, h, l, cl = float(m[1]), float(m[2]), float(m[3]), float(m[4])
                if h <= l:
                    continue
                vol_btc = float(m[5]) if is_spot else float(m[6])
                body_pressure = (cl - o) / (h - l)
                wick_pressure = (2.0 * cl - h - l) / (h - l)
                combined_ratio = 0.60 * body_pressure + 0.40 * wick_pressure
                sub_delta += vol_btc * combined_ratio * scale_factor
        except Exception:
            continue

    if abs(real_collected) > abs(sub_delta) * 0.65:
        return real_collected
    if abs(real_collected) > 0.0:
        return 0.6 * real_collected + 0.4 * sub_delta
    return sub_delta

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
            o, h, l, cl = float(c[1]), float(c[2]), float(c[3]), float(c[4])
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
        
        c_12_desc = [list(c) for c in candles_300[0:12]] if len(candles_300) >= 12 else [list(c) for c in candles_300]
        if c_12_desc:
            c_12_desc[0][4] = str(btc_price)
            if btc_price > float(c_12_desc[0][2]):
                c_12_desc[0][2] = str(btc_price)
            if btc_price < float(c_12_desc[0][3]):
                c_12_desc[0][3] = str(btc_price)

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

        candles_1m_fut = get_okx_candles("1m", 65, ts, ["BTC-USDT-SWAP", "BTC-USD_UM_XPERP-310404"])
        candles_1m_spot = get_okx_candles("1m", 30, ts, ["BTC-USDT"])

        cvd_12, scvd_12 = [], []
        live_open_ts = int(c_12_asc[-1][0]) if c_12_asc else 0

        for idx, c in enumerate(c_12_asc):
            open_ts = int(c[0])
            is_live_candle = (open_ts == live_open_ts)

            if not is_live_candle and open_ts in fut_map:
                cvd_12.append(fut_map[open_ts])
            else:
                val_f = get_1m_real_or_calibrated_delta(candles_1m_fut, open_ts, is_spot=False, scale_factor=0.18)
                fut_map[open_ts] = val_f
                cvd_12.append(val_f)

            if not is_live_candle and open_ts in spot_map:
                scvd_12.append(spot_map[open_ts])
            else:
                val_s = get_1m_real_or_calibrated_delta(candles_1m_spot, open_ts, is_spot=True, scale_factor=0.16)
                spot_map[open_ts] = val_s
                scvd_12.append(val_s)

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
                cvd_12, scvd_12, c_12_asc, candles_300, candles_1h, fut_map, spot_map, oi_change_map, btc_price, vp_data, liq_data)
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                [], [], [], [], [], {}, {}, {}, 75000.0, (0.0, 0.0, 0.0), (74500.0, 95.0, 72500.0, 95.0))

def scan_setup_1(c_12_asc, cvd_12, scvd_12, liquid_ok):
    try:
        if len(c_12_asc) < 12 or len(cvd_12) < 12 or len(scvd_12) < 12:
            return "Načítám strukturu svíček...", False

        opens = [float(c[1]) for c in c_12_asc]
        highs = [float(c[2]) for c in c_12_asc]
        lows = [float(c[3]) for c in c_12_asc]
        closes = [float(c[4]) for c in c_12_asc]
        
        max_all_h = max(highs)
        min_all_l = min(lows)

        cum_c, cum_s = [], []
        cc, cs = 0.0, 0.0
        for i in range(12):
            cc += cvd_12[i]
            cs += scvd_12[i]
            cum_c.append(cc)
            cum_s.append(cs)

        prefix = "" if liquid_ok else "⏸️ [Mimo likvidní čas] "
        
        for j in range(11, 1, -1):
            for i in range(j - 2, -1, -1):
                
                # --- 1. BEARISH EQUAL HIGHS ---
                wick_diff_h = abs(highs[j] - highs[i])
                if wick_diff_h <= 50.0 and max(highs[i], highs[j]) >= max_all_h - 25.0:
                    between_lows = lows[i + 1:j]
                    if not between_lows:
                        continue
                    min_pullback_h = min(between_lows)
                    pullback_rel_idx = between_lows.index(min_pullback_h)
                    pullback_idx = (i + 1) + pullback_rel_idx

                    has_red_pullback = any(closes[k] < opens[k] for k in range(i + 1, pullback_idx + 1))
                    has_green_return = any(closes[k] > opens[k] for k in range(pullback_idx, j + 1))

                    max_between_h = max(highs[i + 1:j])
                    if (has_red_pullback and has_green_return and
                        max_between_h <= max(highs[i], highs[j]) + 15.0 and
                        (max(highs[i], highs[j]) - min_pullback_h) >= 120.0):

                        c_diff = cum_c[j] - cum_c[i]
                        s_diff = cum_s[j] - cum_s[i]

                        valid_bear_abs = (c_diff >= 15.0 and s_diff >= -2.0) or (s_diff >= 3.0 and c_diff >= -5.0)
                        if valid_bear_abs:
                            src_name = "CVD+SPOT" if (c_diff >= 15.0 and s_diff >= 3.0) else ("CVD" if c_diff >= 15.0 else "SPOT")
                            msg = f"{prefix}🔥 BEARISH ABSORPCE (Equal Highs Δ {wick_diff_h:.0f}$ | Pullback ≥ 120$): {src_name} anomálie na vrcholu (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                            # Klíč nezávislý na indexu svíčky i -> 60 min stopka na Bearish Setup 1 + 30 min globální stopka na celý Setup 1
                            zone_bucket = int(round(max_all_h / 300.0) * 300)
                            setup_key = f"S1_BEAR_{zone_bucket}"
                            if liquid_ok:
                                odesli_upozorneni(setup_key, "SETUP 1: BEARISH EQUAL HIGHS", msg, cooldown_sec=3600, category_key="GLOBAL_SETUP1", category_cooldown=1800)
                            return msg, bool(liquid_ok)

                # --- 2. BULLISH EQUAL LOWS ---
                wick_diff_l = abs(lows[j] - lows[i])
                if wick_diff_l <= 50.0 and min(lows[i], lows[j]) <= min_all_l + 25.0:
                    between_highs = highs[i + 1:j]
                    if not between_highs:
                        continue
                    max_bounce_l = max(between_highs)
                    bounce_rel_idx = between_highs.index(max_bounce_l)
                    bounce_idx = (i + 1) + bounce_rel_idx

                    has_green_bounce = any(closes[k] > opens[k] for k in range(i + 1, bounce_idx + 1))
                    has_red_return = any(closes[k] < opens[k] for k in range(bounce_idx, j + 1))

                    min_between_l = min(lows[i + 1:j])
                    if (has_green_bounce and has_red_return and
                        min_between_l >= min(lows[i], lows[j]) - 15.0 and
                        (max_bounce_l - min(lows[i], lows[j])) >= 120.0):

                        c_diff = cum_c[j] - cum_c[i]
                        s_diff = cum_s[j] - cum_s[i]

                        valid_bull_abs = (c_diff <= -15.0 and s_diff <= 2.0) or (s_diff <= -3.0 and c_diff <= 5.0)
                        if valid_bull_abs:
                            src_name = "CVD+SPOT" if (c_diff <= -15.0 and s_diff <= -3.0) else ("CVD" if c_diff <= -15.0 else "SPOT")
                            msg = f"{prefix}🔥 BULLISH ABSORPCE (Equal Lows Δ {wick_diff_l:.0f}$ | Pullback ≥ 120$): {src_name} anomálie na dně (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                            zone_bucket = int(round(min_all_l / 300.0) * 300)
                            setup_key = f"S1_BULL_{zone_bucket}"
                            if liquid_ok:
                                odesli_upozorneni(setup_key, "SETUP 1: BULLISH EQUAL LOWS", msg, cooldown_sec=3600, category_key="GLOBAL_SETUP1", category_cooldown=1800)
                            return msg, bool(liquid_ok)

        # --- 3. ÚZKÝ RANGE (ZÁMEK) ---
        max_body_pct = 0.0018
        for win in range(6, 12):
            sub_c = closes[-win:]
            ref_price = sub_c[-1] if sub_c[-1] > 0 else 75000.0
            close_spread = max(sub_c) - min(sub_c)
            close_spread_pct = (close_spread / ref_price) * 100.0

            if close_spread <= (ref_price * max_body_pct):
                c_sum = sum(cvd_12[-win:])
                s_sum = sum(scvd_12[-win:])
                range_zone_bucket = int(round(ref_price / 300.0) * 300)

                if (c_sum >= 35.0 and s_sum >= -2.0) or (s_sum >= 5.0 and c_sum >= 0.0):
                    msg = f"{prefix}🔥 BEARISH ABSORPCE (Úzký Range {close_spread_pct:.2f}% / {win} sv.): Pohlcen nákup (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok:
                        odesli_upozorneni(f"S1_BEAR_{range_zone_bucket}", "SETUP 1: BEARISH ÚZKÝ RANGE", msg, cooldown_sec=3600, category_key="GLOBAL_SETUP1", category_cooldown=1800)
                    return msg, bool(liquid_ok)
                if (c_sum <= -35.0 and s_sum <= 2.0) or (s_sum <= -5.0 and c_sum <= 0.0):
                    msg = f"{prefix}🔥 BULLISH ABSORPCE (Úzký Range {close_spread_pct:.2f}% / {win} sv.): Pohlcen prodej (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok:
                        odesli_upozorneni(f"S1_BULL_{range_zone_bucket}", "SETUP 1: BULLISH ÚZKÝ RANGE", msg, cooldown_sec=3600, category_key="GLOBAL_SETUP1", category_cooldown=1800)
                    return msg, bool(liquid_ok)

        return "Skenuji Setup 1 (Equal Highs/Lows + Úzký Range)...", False
    except Exception:
        return "Načítám data Setupu 1...", False

def scan_setup_2(candles_300, candles_1h, fut_map, oi_change_map, liquid_ok):
    try:
        if len(candles_300) < 20 or len(candles_1h) < 10:
            return "Načítám historii trhu...", False, "Skenuji levely..."

        try:
            tz_p = ZoneInfo("Europe/Prague")
        except Exception:
            tz_p = timezone(timedelta(hours=1))

        now_prague = datetime.now(tz_p)
        current_date = now_prague.date()
        yesterday_date = current_date - timedelta(days=1)

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
        lon_h, lon_l = 0.0, float("inf")

        for c in all_5m_asc:
            ts_c = int(c[0])
            dt = datetime.fromtimestamp(ts_c / 1000, tz_p)
            if dt.date() != current_date:
                continue
            today_candles.append((ts_c, float(c[1]), float(c[2]), float(c[3]), float(c[4]), dt.hour))
            if 1 <= dt.hour < 7:
                asia_h, asia_l = max(asia_h, float(c[2])), min(asia_l, float(c[3]))
            elif 9 <= dt.hour < 14:
                lon_h, lon_l = max(lon_h, float(c[2])), min(lon_l, float(c[3]))

        if asia_h == 0.0:
            asia_h, asia_l = 0.0, 0.0
        if lon_h == 0.0:
            lon_h, lon_l = 0.0, 0.0

        raw_levels = [
            ("PDH", pdh, True, 0),
            ("PDL", pdl, False, 0),
            ("ASIA H", asia_h, True, 7),
            ("ASIA L", asia_l, False, 7),
            ("LON H", lon_h, True, 14),
            ("LON L", lon_l, False, 14)
        ]
        cum_cvd_today = []
        running_cvd = 0.0
        for tc in today_candles:
            running_cvd += fut_map.get(tc[0], 0.0)
            cum_cvd_today.append(running_cvd)

        untouched_levels, pending_retest_msgs = [], []
        triggered_msg, is_triggered = None, False
        prefix = "" if liquid_ok else "⏸️ [Mimo likvidní čas] "
        n_today = len(today_candles)

        for name, val, is_high, valid_from_hour in raw_levels:
            if val <= 0 or now_prague.hour < valid_from_hour:
                continue

            sweep_idx = None
            for idx, tc in enumerate(today_candles):
                if tc[5] < valid_from_hour:
                    continue
                if is_high and tc[2] >= val:
                    sweep_idx = idx
                    break
                if not is_high and tc[3] <= val:
                    sweep_idx = idx
                    break

            if sweep_idx is None:
                untouched_levels.append(f"{name}: {val:.0f}")
                continue

            ts_sweep = today_candles[sweep_idx][0]
            oi_flush = min(
                oi_change_map.get(ts_sweep, 0.0),
                oi_change_map.get(ts_sweep, 0.0) + oi_change_map.get(ts_sweep + 300000, 0.0)
            )

            if oi_flush > -50.0:
                continue

            cvd_at_sweep = cum_cvd_today[sweep_idx]
            retest_hit = False

            min_retest_idx = sweep_idx + 2
            max_retest_idx = min(sweep_idx + 9, n_today - 1)

            if (n_today - 1) >= min_retest_idx:
                for r_idx in range(min_retest_idx, max_retest_idx + 1):
                    tc_r = today_candles[r_idx]
                    cvd_at_retest = cum_cvd_today[r_idx]
                    cvd_diff = cvd_at_retest - cvd_at_sweep

                    price_returned = (tc_r[2] >= val - 35.0) if is_high else (tc_r[3] <= val + 35.0)

                    if price_returned:
                        if is_high and cvd_diff >= 100.0:
                            if r_idx >= (n_today - 3):
                                triggered_msg = f"{prefix}🔥 SETUP 2 PLATNÝ ({name} {val:.0f}): SFP Retest ({r_idx - sweep_idx}. svíčka po sweepu) + OI {oi_flush:.1f} BTC | CVD {cvd_diff:+.1f} BTC!"
                                is_triggered = bool(liquid_ok)
                                if is_triggered:
                                    odesli_upozorneni(f"SFP_{name}_{current_date}", f"SETUP 2: SFP {name} RETEST", triggered_msg, cooldown_sec=43200, category_key="GLOBAL_SETUP2", category_cooldown=1800)
                            retest_hit = True
                            break
                        elif not is_high and cvd_diff <= -100.0:
                            if r_idx >= (n_today - 3):
                                triggered_msg = f"{prefix}🔥 SETUP 2 PLATNÝ ({name} {val:.0f}): SFP Retest ({r_idx - sweep_idx}. svíčka po sweepu) + OI {oi_flush:.1f} BTC | CVD {cvd_diff:+.1f} BTC!"
                                is_triggered = bool(liquid_ok)
                                if is_triggered:
                                    odesli_upozorneni(f"SFP_{name}_{current_date}", f"SETUP 2: SFP {name} RETEST", triggered_msg, cooldown_sec=43200, category_key="GLOBAL_SETUP2", category_cooldown=1800)
                            retest_hit = True
                            break

            candles_since_sweep = (n_today - 1) - sweep_idx
            if not retest_hit and 0 <= candles_since_sweep <= 9:
                curr_diff = cum_cvd_today[-1] - cvd_at_sweep
                sv_left = 9 - candles_since_sweep
                pending_retest_msgs.append(f"⏳ {name} ({val:.0f}) vybrán (OI {oi_flush:.1f}) – okno retestu 2–9 sv. (zbývá {sv_left} sv. | CVD Δ {curr_diff:+.1f})")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"
        if triggered_msg:
            final_msg = triggered_msg
        elif pending_retest_msgs:
            final_msg = " | ".join(pending_retest_msgs)
        else:
            final_msg = "Čekám na protnutí Macro Levelu s výplachem OI (-50 BTC) a retest (2–9 svíček)..."

        return final_msg, is_triggered, levels_str
    except Exception:
        return "Načítám levely...", False, ""

# --- 24/7 HLÍDAČ S AUTOMATICKÝM UKONČENÍM STARÝCH VLÁKEN ---
@st.cache_resource
def start_background_guardian():
    my_token = str(uuid.uuid4())
    sys.__dict__["OKX_GUARDIAN_TOKEN"] = my_token

    def _guardian_loop(thread_token):
        tick = 0
        while True:
            # Pokud byl načten novější kód, staré vlákno se okamžitě ukončí!
            if sys.__dict__.get("OKX_GUARDIAN_TOKEN") != thread_token:
                break
            try:
                poll_realtime_okx_flow()
                if tick % 3 == 0:
                    liq_ok, _ = check_liquid_hours()
                    if liq_ok:
                        data = fetch_okx_data()
                        cvd_12, scvd_12, c_12_asc = data[9], data[10], data[11]
                        c_300, c_1h, fut_map, oi_change_map = data[12], data[13], data[14], data[16]
                        scan_setup_1(c_12_asc, cvd_12, scvd_12, liq_ok)
                        scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liq_ok)
                tick += 1
            except Exception:
                pass
            time.sleep(10)

    t = threading.Thread(target=_guardian_loop, args=(my_token,), daemon=True)
    t.start()
    return my_token

start_background_guardian()

liquid_ok, liq_status_text = check_liquid_hours()
total_pnl, win_rate = load_trading_data()
(cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9,
 cvd_12, scvd_12, c_12_asc, c_300, c_1h, fut_map, spot_map, oi_change_map, b_price, vp_data, liq_data) = fetch_okx_data()
poc_1h, vah_1h, val_1h = vp_data
upper_p, upper_btc, lower_p, lower_btc = liq_data

msg1, trg1 = scan_setup_1(c_12_asc, cvd_12, scvd_12, liquid_ok)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liquid_ok)

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

# --- FUTURISTICKÝ OKX MATRIX ---
matrix_html = "\n".join([
    '<div class="matrix-unified">',
    '<div style="color: #ffffff; font-weight: 900; font-size: 18px; margin-bottom: 12px; letter-spacing: 2px; text-shadow: 0px 2px 8px rgba(0,0,0,1);">OKX ORDER FLOW & LIQUIDATION MATRIX</div>',
    '<div class="matrix-grid">',
    '<div class="thermo-card">',
    '<div style="color: #00f3ff; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 2px 4px #000;">CVD (FUT)</div>',
    f'<div style="font-size: 20px; font-weight: 900; color: {c_cvd1}; text-shadow: 0 0 10px #000;">{cvd1:+,.1f}</div>',
    '<div class="thermo-tube-wrap">',
    '<div class="thermo-scale">',
    '<span style="color:#3fb950;">+150</span>',
    '<span style="color:#7ee787;">+75</span>',
    '<span style="color:#ffffff;">0</span>',
    '<span style="color:#ffa198;">-75</span>',
    '<span style="color:#f85149;">-150</span>',
    '</div>',
    '<div class="thermo-glass">',
    '<div class="thermo-zero-line"></div>',
    f'<div class="{cvd_mercury_cls}" style="height: {cvd_bar_pct:.1f}%;"></div>',
    '</div>',
    '</div>',
    '<div style="width: 100%; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px;">',
    '<div style="font-size: 9px; color: #94a3b8; font-weight: 800;">25M / 45M DELTA</div>',
    f'<div style="font-size: 13px; font-weight: 900; color: {c_cvd5};">{cvd5:+,.1f}</div>',
    f'<div style="font-size: 11px; font-weight: 900; color: {c_cvd9}; opacity: 0.85;">{cvd9:+,.1f}</div>',
    '</div>',
    '</div>',
    '<div style="display: flex; flex-direction: column; justify-content: space-between;">',
    '<div class="liq-bumper-box">',
    '<div style="color: #f85149; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 SHORT LIQ (+2%)</div>',
    f'<div style="font-size: 19px; font-weight: 900; color: #ffffff; font-family: \'Orbitron\', sans-serif; text-shadow: 0 0 10px rgba(248,81,73,0.7);">{upper_p:,.0f} $</div>',
    f'<div style="color: #f1e05a; font-size: 11px; font-weight: 900; text-shadow: 0 1px 3px #000;">({upper_btc:.1f} BTC)</div>',
    '</div>',
    f'<div class="matrix-live-price">{b_price:,.0f}</div>',
    '<div class="liq-bumper-box">',
    '<div style="color: #3fb950; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 LONG LIQ (-2%)</div>',
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
    '</div>',
    '</div>',
    '<div class="thermo-card">',
    '<div style="color: #f1e05a; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 2px 4px #000;">SPOT CVD</div>',
    f'<div style="font-size: 20px; font-weight: 900; color: {c_scvd1}; text-shadow: 0 0 10px #000;">{scvd1:+,.1f}</div>',
    '<div class="thermo-tube-wrap">',
    '<div class="thermo-glass">',
    '<div class="thermo-zero-line"></div>',
    f'<div class="{spot_mercury_cls}" style="height: {spot_bar_pct:.1f}%;"></div>',
    '</div>',
    '<div class="thermo-scale" style="text-align: left;">',
    '<span style="color:#3fb950;">+30</span>',
    '<span style="color:#7ee787;">+15</span>',
    '<span style="color:#ffffff;">0</span>',
    '<span style="color:#ffa198;">-15</span>',
    '<span style="color:#f85149;">-30</span>',
    '</div>',
    '</div>',
    '<div style="width: 100%; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px;">',
    '<div style="font-size: 9px; color: #94a3b8; font-weight: 800;">25M / 45M DELTA</div>',
    f'<div style="font-size: 13px; font-weight: 900; color: {c_scvd5};">{scvd5:+,.1f}</div>',
    f'<div style="font-size: 11px; font-weight: 900; color: {c_scvd9}; opacity: 0.85;">{scvd9:+,.1f}</div>',
    '</div>',
    '</div>',
    '</div>',
    '</div>'
])
st.markdown(matrix_html, unsafe_allow_html=True)

# VIZUÁLNÍ GRAF (11 UZAVŘENÝCH + 1 ŽIVÁ 5M SVÍČKA)
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
        fig.add_shape(
            type="rect",
            x0=-0.8, x1=11.3,
            y0=val_1h, y1=vah_1h,
            fillcolor="rgba(247, 147, 26, 0.06)",
            line=dict(width=0),
            layer="below",
            row=1, col=1
        )
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[vah_1h, vah_1h],
            mode="lines",
            line=dict(color="rgba(247, 147, 26, 0.65)", width=1.3, dash="dash"),
            hoverinfo="skip", showlegend=False
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[poc_1h, poc_1h],
            mode="lines",
            line=dict(color="#f7931a", width=2.2),
            hoverinfo="skip", showlegend=False
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[val_1h, val_1h],
            mode="lines",
            line=dict(color="rgba(247, 147, 26, 0.65)", width=1.3, dash="dash"),
            hoverinfo="skip", showlegend=False
        ), row=1, col=1)

        for lbl_txt, lbl_val, lbl_col in [("VAH", vah_1h, "#f59e0b"), ("POC", poc_1h, "#f7931a"), ("VAL", val_1h, "#f59e0b")]:
            fig.add_annotation(
                x=0.0, y=lbl_val,
                xref="paper", yref="y",
                text=f"<b>{lbl_txt} {lbl_val:.0f}</b>",
                showarrow=False,
                xanchor="left", yanchor="middle",
                font=dict(family="Orbitron, sans-serif", size=9, color=lbl_col),
                bgcolor="rgba(4, 6, 9, 0.85)",
                bordercolor=lbl_col,
                borderwidth=1,
                borderpad=2
            )
    
    fig.add_trace(go.Candlestick(x=x_axis,
                                 open=[float(c[1]) for c in c_12_asc],
                                 high=[float(c[2]) for c in c_12_asc],
                                 low=[float(c[3]) for c in c_12_asc],
                                 close=[float(c[4]) for c in c_12_asc],
                                 increasing_line_color="#3fb950", decreasing_line_color="#f85149",
                                 increasing_fillcolor="#3fb950", decreasing_fillcolor="#f85149",
                                 increasing_line_width=1.8, decreasing_line_width=1.8,
                                 whiskerwidth=0.3,
                                 showlegend=False), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[-0.8, 13.6],
        y=[b_price, b_price],
        mode="lines",
        line=dict(color="rgba(0, 243, 255, 0.55)", width=1.4, dash="dot"),
        hoverinfo="skip",
        showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[11.0],
        y=[b_price],
        mode="markers",
        marker=dict(color="#00f3ff", size=7, line=dict(color="#ffffff", width=1.5)),
        hoverinfo="skip",
        showlegend=False
    ), row=1, col=1)

    fig.add_annotation(
        x=1.0,
        y=b_price,
        xref="paper",
        yref="y",
        text=f"<b>LIVE {b_price:.0f}</b>",
        showarrow=False,
        xanchor="right",
        yanchor="middle",
        font=dict(family="Orbitron, sans-serif", size=11, color="#00f3ff"),
        bgcolor="rgba(4, 6, 9, 0.95)",
        bordercolor="#00f3ff",
        borderwidth=1.5,
        borderpad=4
    )
                                 
    fig.add_trace(go.Scatter(x=x_axis, y=cum_cvd_chart, mode="lines+markers",
                             marker=dict(size=[0]*11 + [6], color="#00f3ff"),
                             line=dict(color="#00f3ff", width=3, shape="spline", smoothing=1.1), showlegend=False), row=2, col=1)
                             
    fig.add_trace(go.Scatter(x=x_axis, y=cum_scvd_chart, mode="lines+markers",
                             marker=dict(size=[0]*11 + [6], color="#f1e05a"),
                             line=dict(color="#f1e05a", width=3, shape="spline", smoothing=1.1), showlegend=False), row=3, col=1)

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
        height=760,
        margin=dict(l=6, r=6, t=20, b=0, pad=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, rangeslider=dict(visible=False), fixedrange=True, range=[-0.8, 13.6]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=p_rng),
        xaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=c_rng),
        xaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=s_rng)
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# SETUP KARTY 
liq_color = "#3fb950" if liquid_ok else "#94a3b8"
box1_cls = "alert-box signal-triggered" if trg1 else "alert-box"
box2_cls = "alert-box signal-triggered" if trg2 else "alert-box"

setups_html = "\n".join([
    '<div class="setups-container">',
    f'<div style="text-align: center; font-size: 11px; font-weight: 900; color: {liq_color}; letter-spacing: 1px; margin-bottom: 10px;">{liq_status_text}</div>',
    f'<div class="{box1_cls}">',
    '<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">⚡ SETUP 1: ABSORPCE (EQUAL H/L & ÚZKÝ RANGE)</div>',
    f'<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg1}</div>',
    '</div>',
    f'<div class="{box2_cls}" style="margin-bottom: 0;">',
    '<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">🎯 SETUP 2: MACRO SFP + RETEST (2–9 SVÍČEK)</div>',
    f'<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg2}</div>',
    f'<div style="color: #00f3ff; font-size: 12px; margin-top: 6px; font-weight: 800;">Zbývající levely: {l_str}</div>',
    '</div>',
    '</div>'
])
st.markdown(setups_html, unsafe_allow_html=True)

# MONEY JOURNAL
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

if st.button("🔄 AKTUALIZOVAT"):
    st.rerun()

if st.button("📲 OTESTOVAT TELEGRAM SPOJENÍ"):
    ok = odesli_upozorneni(
        "TEST_PING",
        "TEST SPOJENÍ OKX TERMINÁL",
        f"✅ Telegram notifikace + 30m Buffer funguje! Live cena BTC: {b_price:.0f} $ | CVD: {cvd1:+.1f} | Spot: {scvd1:+.1f}",
        force=True
    )
    if ok:
        st.success("Testovací zpráva byla odeslána na tvůj Telegram!")
    else:
        st.error("Odeslání selhalo.")

if st.toggle("⏱️ Auto Refresh (20s)", value=False):
    time.sleep(20)
    st.rerun()
