import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import time
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- NASTAVENÍ TELEGRAM NOTIFIKACÍ ---
TELEGRAM_BOT_TOKEN = "9068673685:AAEwXgVLOdO-kZ3Pvm3ATu87vZ6eZ-zP-cY"
TELEGRAM_CHAT_ID = "9209356727"

# --- TRVALÁ PAMĚŤ SERVERU (PROTI SPAMU + ŽIVÝ SBĚR OBCHODŮ, OI A LIKVIDACÍ) ---
@st.cache_resource
def get_realtime_engine():
    return {
        "lock": threading.Lock(),
        "sent_alerts": {},
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

def odesli_upozorneni(setup_id_key, setup_nazev, detail_zpravy, cooldown_sec=7200, category_key=None, category_cooldown=1800, force=False):
    now_ts = time.time()
    with ENGINE["lock"]:
        if not force:
            last_sent = ENGINE["sent_alerts"].get(setup_id_key, 0.0)
            if (now_ts - last_sent) < cooldown_sec:
                return False
            if category_key:
                last_cat_sent = ENGINE["sent_alerts"].get(category_key, 0.0)
                if (now_ts - last_cat_sent) < category_cooldown:
                    return False
        ENGINE["sent_alerts"][setup_id_key] = now_ts
        if category_key:
            ENGINE["sent_alerts"][category_key] = now_ts

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

components.html("""
<script>
    try {
        const doc = window.parent.document;
        let meta = doc.querySelector('meta[name="theme-color"]');
        if (!meta) {
            meta = doc.createElement('meta');
            meta.name = "theme-color";
            doc.head.appendChild(meta);
        }
        meta.content = "#040609";
        doc.body.style.backgroundColor = "#040609";
        doc.documentElement.style.backgroundColor = "#040609";
    } catch (e) {}
</script>
""", height=0)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;800;900&display=swap');

#MainMenu {visibility: hidden !important; display: none !important;}
header[data-testid="stHeader"] {visibility: hidden !important; display: none !important;}
footer {visibility: hidden !important; display: none !important;}
.viewerBadge_container__1QSob {display: none !important;}
[data-testid="stAppViewBlockContainer"] {
    padding-top: 0rem !important; 
    padding-bottom: 1.5rem !important; 
    padding-left: 0.4rem !important; 
    padding-right: 0.4rem !important;
    margin-top: -65px !important;
}
iframe[height="0"] {display: none !important;}

@keyframes app-heart-pulse { 
    0% { background-size: 230% auto; } 
    50% { background-size: 260% auto; } 
    100% { background-size: 230% auto; } 
}
.stApp { 
    background-color: #040609; 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.35), rgba(4, 6, 9, 0.75)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_glowing_ruby_red_neon_heart.jpg');
    background-attachment: fixed;
    background-position: center 45%;
    background-repeat: no-repeat;
    animation: app-heart-pulse 3.5s infinite ease-in-out;
    color: #f0f6fc; 
}

.gold-btc-banner {
    width: 100vw;
    margin-left: calc(-50vw + 50%);
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.05), rgba(4, 6, 9, 0.45)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_luxurious_glowing_golden_Bi%20(1).jpg');
    background-position: center center;
    background-size: cover;
    background-repeat: no-repeat;
    height: 480px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    padding-bottom: 25px;
    margin-bottom: 25px;
    box-shadow: 0 15px 45px rgba(0, 0, 0, 0.85);
    border-bottom: 2px solid rgba(247, 147, 26, 0.4);
}

.matrix-unified { 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.55), rgba(4, 6, 9, 0.88)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-position: center top;
    background-size: cover;
    border: 1px solid #2dd4bf; 
    border-radius: 18px; 
    padding: 16px 8px 18px 8px; 
    text-align: center; 
    margin-bottom: 18px; 
    box-shadow: 0 8px 35px rgba(0, 243, 255, 0.2); 
    position: relative;
    overflow: hidden;
}

.matrix-grid {
    display: grid;
    grid-template-columns: 1.05fr 1.55fr 1.05fr;
    gap: 8px;
    align-items: stretch;
}

.thermo-card {
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.25), rgba(4, 6, 9, 0.65)),
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_vertical_futuristic_3D_cybernetic_glass_thermometer_gauge.jpg');
    background-position: center center;
    background-size: cover;
    border: 1px solid rgba(0, 243, 255, 0.45);
    border-radius: 14px;
    padding: 10px 4px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    min-height: 350px;
    box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.85), 0 0 15px rgba(0, 243, 255, 0.12);
    position: relative;
}

.thermo-tube-wrap {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 175px;
    margin: 6px 0;
    gap: 5px;
}

.thermo-scale {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    font-family: 'Orbitron', sans-serif;
    font-size: 8px;
    font-weight: 800;
    color: #cbd5e1;
    text-align: right;
    text-shadow: 0 1px 3px #000;
}

.thermo-glass {
    width: 22px;
    height: 100%;
    background: rgba(4, 8, 15, 0.82);
    border: 1.5px solid rgba(247, 147, 26, 0.65);
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.35), 0 0 10px rgba(247, 147, 26, 0.25);
}

.thermo-zero-line {
    position: absolute;
    top: 50%;
    left: 0;
    width: 100%;
    height: 2px;
    background: #ffffff;
    z-index: 4;
    box-shadow: 0 0 6px #00f3ff;
}

@keyframes plasma-pump {
    0% { filter: brightness(1.0) drop-shadow(0 0 6px currentColor); }
    50% { filter: brightness(1.45) drop-shadow(0 0 14px currentColor); }
    100% { filter: brightness(1.0) drop-shadow(0 0 6px currentColor); }
}

.thermo-mercury-up {
    position: absolute;
    bottom: 50%;
    left: 2px;
    right: 2px;
    background: linear-gradient(180deg, #00f3ff 0%, #3fb950 100%);
    border-radius: 8px 8px 0 0;
    color: #3fb950;
    animation: plasma-pump 1.8s infinite ease-in-out;
    z-index: 2;
}

.thermo-mercury-down {
    position: absolute;
    top: 50%;
    left: 2px;
    right: 2px;
    background: linear-gradient(180deg, #f85149 0%, #ff0055 100%);
    border-radius: 0 0 8px 8px;
    color: #f85149;
    animation: plasma-pump 1.8s infinite ease-in-out;
    z-index: 2;
}

.liq-bumper-box {
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.35), rgba(4, 6, 9, 0.72)),
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_futuristic_3D_horizontal_HUD_target_bumper_frame_on_a_pitc.jpg');
    background-position: center center;
    background-size: cover;
    border: 1.5px solid rgba(247, 147, 26, 0.65);
    border-radius: 13px;
    padding: 10px 6px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.85), inset 0 0 14px rgba(0, 243, 255, 0.18);
}

.matrix-live-price {
    font-family: 'Orbitron', sans-serif;
    font-size: 31px;
    font-weight: 900;
    color: #f0f6fc;
    letter-spacing: 1px;
    text-align: center;
    padding: 10px 2px;
    margin: 6px 0;
    background: radial-gradient(circle, rgba(0, 243, 255, 0.14) 0%, rgba(4, 6, 9, 0.65) 80%);
    border-top: 1px solid rgba(0, 243, 255, 0.35);
    border-bottom: 1px solid rgba(0, 243, 255, 0.35);
    border-radius: 10px;
    text-shadow: 0 0 14px rgba(0, 243, 255, 0.65), 0 2px 6px rgba(0, 0, 0, 1);
}

.oi-center-box {
    background: linear-gradient(180deg, rgba(10, 16, 28, 0.88), rgba(4, 6, 9, 0.95));
    border: 1px solid rgba(0, 243, 255, 0.45);
    border-radius: 12px;
    padding: 8px 6px;
    margin-top: 8px;
    box-shadow: inset 0 0 12px rgba(0, 243, 255, 0.15);
}

.oi-bar-track {
    width: 100%;
    height: 10px;
    background: rgba(4, 8, 15, 0.9);
    border: 1px solid rgba(247, 147, 26, 0.5);
    border-radius: 6px;
    position: relative;
    overflow: hidden;
    margin: 5px 0;
}

.setups-container {
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.75), rgba(4, 6, 9, 0.92)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-position: center bottom;
    background-size: cover;
    border: 1px solid #2dd4bf;
    border-radius: 16px;
    padding: 15px;
    margin-bottom: 18px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.8);
}

.alert-box { 
    background: rgba(13, 19, 31, 0.35); 
    border: 1px solid rgba(31, 41, 55, 0.6); 
    padding: 14px; 
    border-radius: 15px; 
    margin-bottom: 12px; 
    backdrop-filter: blur(1px); 
    min-height: 125px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    text-align: center;
}
.signal-triggered { 
    background-color: rgba(35, 12, 16, 0.55) !important; 
    border: 2px solid #f85149 !important; 
    animation: pulse-alert 1s infinite alternate; 
}
@keyframes pulse-alert { 0% { box-shadow: 0 0 10px rgba(248, 81, 73, 0.4); } 100% { box-shadow: 0 0 30px rgba(248, 81, 73, 0.9); } }

.money-journal { 
    background-image: 
        linear-gradient(rgba(2, 10, 5, 0.3), rgba(2, 10, 5, 0.6)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_neat_pile_of_crisp_US_dolla.jpg');
    background-position: center;
    background-size: cover;
    border-radius: 15px; 
    padding: 26px 20px; 
    text-align: center; 
    margin-bottom: 18px; 
    box-shadow: 0 10px 40px rgba(39, 174, 96, 0.4); 
    border: 1px solid #1f7a43; 
}
.money-content { position: relative; z-index: 2; display: flex; justify-content: space-around; align-items: center; }

div.stButton > button { width: 100%; background: rgba(17, 24, 39, 0.85); color: #f0f6fc !important; border: 1px solid #374151 !important; border-radius: 10px; padding: 14px; font-size: 15px !important; font-weight: 900 !important; margin-bottom: 10px; }
div.stButton > button:hover { border-color: #00f3ff !important; color: #00f3ff !important; }
</style>
""", unsafe_allow_html=True)

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
        return True, f"🟢 LIKVIDNÍ OKNO AKTIVNÍ ({now_p.strftime('%H:%M')}) | 24/7 Alpha Hlídač + Live 5M zapnutý"
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
        
        # 16 svíček (80 minut) pro 3-dotykový skener Setupu 1 + posledních 12 svíček pro graf
        c_16_desc = [list(c) for c in candles_300[0:16]] if len(candles_300) >= 16 else [list(c) for c in candles_300]
        if c_16_desc:
            c_16_desc[0][4] = str(btc_price)
            if btc_price > float(c_16_desc[0][2]):
                c_16_desc[0][2] = str(btc_price)
            if btc_price < float(c_16_desc[0][3]):
                c_16_desc[0][3] = str(btc_price)

        c_16_asc = c_16_desc[::-1]
        c_12_asc = c_16_asc[-12:] if len(c_16_asc) >= 12 else c_16_asc
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

        candles_1m_fut = get_okx_candles("1m", 85, ts, ["BTC-USDT-SWAP", "BTC-USD_UM_XPERP-310404"])
        candles_1m_spot = get_okx_candles("1m", 40, ts, ["BTC-USDT"])

        cvd_16, scvd_16 = [], []
        live_open_ts = int(c_16_asc[-1][0]) if c_16_asc else 0

        for idx, c in enumerate(c_16_asc):
            open_ts = int(c[0])
            is_live_candle = (open_ts == live_open_ts)

            if not is_live_candle and open_ts in fut_map:
                cvd_16.append(fut_map[open_ts])
            else:
                val_f = get_1m_real_or_calibrated_delta(candles_1m_fut, open_ts, is_spot=False, scale_factor=0.18)
                fut_map[open_ts] = val_f
                cvd_16.append(val_f)

            if not is_live_candle and open_ts in spot_map:
                scvd_16.append(spot_map[open_ts])
            else:
                val_s = get_1m_real_or_calibrated_delta(candles_1m_spot, open_ts, is_spot=True, scale_factor=0.16)
                spot_map[open_ts] = val_s
                scvd_16.append(val_s)

        cvd_12 = cvd_16[-12:] if len(cvd_16) >= 12 else cvd_16
        scvd_12 = scvd_16[-12:] if len(scvd_16) >= 12 else scvd_16

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
                cvd_12, scvd_12, c_12_asc, candles_300, candles_1h, fut_map, spot_map, oi_change_map, btc_price, vp_data, liq_data,
                c_16_asc, cvd_16, scvd_16)
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                [], [], [], [], [], {}, {}, {}, 75000.0, (0.0, 0.0, 0.0), (74500.0, 95.0, 72500.0, 95.0),
                [], [], [])

def scan_setup_1(c_scan_asc, cvd_scan, scvd_scan, liquid_ok):
    try:
        n = len(c_scan_asc)
        if n < 12 or len(cvd_scan) < n or len(scvd_scan) < n:
            return "Načítám strukturu svíček...", False

        opens = [float(c[1]) for c in c_scan_asc]
        highs = [float(c[2]) for c in c_scan_asc]
        lows = [float(c[3]) for c in c_scan_asc]
        closes = [float(c[4]) for c in c_scan_asc]
        timestamps = [int(c[0]) for c in c_scan_asc]
        curr_price = closes[-1] if closes[-1] > 0 else 75000.0

        cum_c, cum_s = [], []
        cc, cs = 0.0, 0.0
        for idx in range(n):
            cc += cvd_scan[idx]
            cs += scvd_scan[idx]
            cum_c.append(cc)
            cum_s.append(cs)

        prefix = "" if liquid_ok else "⏸️ [Mimo likvidní čas] "
        min_pullback_usd = curr_price * 0.0018  # 0.18 % z aktuální ceny

        # --- 1. TRIPLE EQUAL HIGHS / LOWS (1. vrchol/dno + 2 pokusy o retest = 3 dotyky: i, j, k) ---
        # Třetí dotyk (k) musí být čerstvý (poslední živá nebo těsně uzavřená svíčka)
        for k in range(n - 1, max(n - 3, 3), -1):
            for j in range(k - 2, 1, -1):
                for i in range(j - 2, -1, -1):

                    # A) BEARISH TRIPLE EQUAL HIGHS (3 vrcholy v toleranci 0.08 % od 1. vrcholu)
                    tol_h = highs[i] * 0.0008
                    diff_ij_h = abs(highs[j] - highs[i])
                    diff_ik_h = abs(highs[k] - highs[i])
                    if diff_ij_h <= tol_h and diff_ik_h <= tol_h:
                        lows_ij = lows[i + 1:j]
                        lows_jk = lows[j + 1:k]
                        if lows_ij and lows_jk:
                            min_pb1 = min(lows_ij)
                            pb1_idx = (i + 1) + lows_ij.index(min_pb1)
                            min_pb2 = min(lows_jk)
                            pb2_idx = (j + 1) + lows_jk.index(min_pb2)

                            # Každý z obou retestů musí mít červený pullback a zelenou návratovou svíčku
                            red_1 = any(closes[m] < opens[m] for m in range(i + 1, pb1_idx + 1))
                            green_1 = any(closes[m] > opens[m] for m in range(pb1_idx, j + 1))
                            red_2 = any(closes[m] < opens[m] for m in range(j + 1, pb2_idx + 1))
                            green_2 = any(closes[m] > opens[m] for m in range(pb2_idx, k + 1))

                            top_ceil = max(highs[i], highs[j], highs[k])
                            max_between_all = max(highs[i + 1:k])
                            deepest_pb = top_ceil - min(min_pb1, min_pb2)
                            second_pb = top_ceil - max(min_pb1, min_pb2)

                            if (red_1 and green_1 and red_2 and green_2 and
                                max_between_all <= top_ceil + (highs[i] * 0.0003) and
                                deepest_pb >= min_pullback_usd and
                                second_pb >= (curr_price * 0.0009)):

                                c_diff = cum_c[k] - cum_c[i]
                                s_diff = cum_s[k] - cum_s[i]

                                # Anomálie od 1. do 3. vrcholu: CVD >= +50 BTC nebo Spot >= +10 BTC (CVD >= -10 BTC)
                                valid_bear = (c_diff >= 50.0 and s_diff >= -2.0) or (s_diff >= 10.0 and c_diff >= -10.0)
                                if valid_bear:
                                    src_name = "CVD+SPOT" if (c_diff >= 50.0 and s_diff >= 10.0) else ("CVD" if c_diff >= 50.0 else "SPOT")
                                    max_wick_diff = max(diff_ij_h, diff_ik_h)
                                    msg = f"{prefix}🔥 BEARISH ALPHA ABSORPCE (3x Equal Highs Δ {max_wick_diff:.0f}$ / ≤0.08% | Pullback ≥ 0.18%): {src_name} anomálie 1.→3. vrchol (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                                    zone_bucket = int(round(top_ceil / 150.0) * 150)
                                    setup_key = f"EQH3_{timestamps[i]}_{zone_bucket}"
                                    if liquid_ok:
                                        odesli_upozorneni(setup_key, "SETUP 1: BEARISH 3x EQUAL HIGHS", msg, cooldown_sec=7200, category_key="SETUP1_ANY", category_cooldown=1800)
                                    return msg, bool(liquid_ok)

                    # B) BULLISH TRIPLE EQUAL LOWS (3 dna v toleranci 0.08 % od 1. dna)
                    tol_l = lows[i] * 0.0008
                    diff_ij_l = abs(lows[j] - lows[i])
                    diff_ik_l = abs(lows[k] - lows[i])
                    if diff_ij_l <= tol_l and diff_ik_l <= tol_l:
                        highs_ij = highs[i + 1:j]
                        highs_jk = highs[j + 1:k]
                        if highs_ij and highs_jk:
                            max_b1 = max(highs_ij)
                            b1_idx = (i + 1) + highs_ij.index(max_b1)
                            max_b2 = max(highs_jk)
                            b2_idx = (j + 1) + highs_jk.index(max_b2)

                            green_b1 = any(closes[m] > opens[m] for m in range(i + 1, b1_idx + 1))
                            red_r1 = any(closes[m] < opens[m] for m in range(b1_idx, j + 1))
                            green_b2 = any(closes[m] > opens[m] for m in range(j + 1, b2_idx + 1))
                            red_r2 = any(closes[m] < opens[m] for m in range(b2_idx, k + 1))

                            bot_floor = min(lows[i], lows[j], lows[k])
                            min_between_all = min(lows[i + 1:k])
                            highest_bounce = max(max_b1, max_b2) - bot_floor
                            second_bounce = min(max_b1, max_b2) - bot_floor

                            if (green_b1 and red_r1 and green_b2 and red_r2 and
                                min_between_all >= bot_floor - (lows[i] * 0.0003) and
                                highest_bounce >= min_pullback_usd and
                                second_bounce >= (curr_price * 0.0009)):

                                c_diff = cum_c[k] - cum_c[i]
                                s_diff = cum_s[k] - cum_s[i]

                                # Anomálie od 1. do 3. dna: CVD <= -50 BTC nebo Spot <= -10 BTC (CVD <= +10 BTC)
                                valid_bull = (c_diff <= -50.0 and s_diff <= 2.0) or (s_diff <= -10.0 and c_diff <= 10.0)
                                if valid_bull:
                                    src_name = "CVD+SPOT" if (c_diff <= -50.0 and s_diff <= -10.0) else ("CVD" if c_diff <= -50.0 else "SPOT")
                                    max_wick_diff = max(diff_ij_l, diff_ik_l)
                                    msg = f"{prefix}🔥 BULLISH ALPHA ABSORPCE (3x Equal Lows Δ {max_wick_diff:.0f}$ / ≤0.08% | Odraz ≥ 0.18%): {src_name} anomálie 1.→3. dno (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                                    zone_bucket = int(round(bot_floor / 150.0) * 150)
                                    setup_key = f"EQL3_{timestamps[i]}_{zone_bucket}"
                                    if liquid_ok:
                                        odesli_upozorneni(setup_key, "SETUP 1: BULLISH 3x EQUAL LOWS", msg, cooldown_sec=7200, category_key="SETUP1_ANY", category_cooldown=1800)
                                    return msg, bool(liquid_ok)

        # --- 2. ÚZKÝ RANGE (ZÁMEK 0.15 % BODY-TO-BODY, CVD ±50 BTC NEBO SPOT ±10 BTC) ---
        max_body_pct = 0.0015
        for win in range(6, 13):
            sub_c = closes[-win:]
            ref_price = sub_c[-1] if sub_c[-1] > 0 else 75000.0
            close_spread = max(sub_c) - min(sub_c)
            close_spread_pct = (close_spread / ref_price) * 100.0

            if close_spread <= (ref_price * max_body_pct):
                c_sum = sum(cvd_scan[-win:])
                s_sum = sum(scvd_scan[-win:])
                range_zone_bucket = int(round(ref_price / 200.0) * 200)

                if (c_sum >= 50.0 and s_sum >= -2.0) or (s_sum >= 10.0 and c_sum >= -10.0):
                    msg = f"{prefix}🔥 BEARISH ALPHA ABSORPCE (Úzký Range {close_spread_pct:.2f}% ≤0.15% / {win} sv.): Pohlcen nákup (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok:
                        odesli_upozorneni(f"RNG_BEAR_ZONE_{range_zone_bucket}", "SETUP 1: BEARISH ÚZKÝ RANGE", msg, cooldown_sec=7200, category_key="SETUP1_ANY", category_cooldown=1800)
                    return msg, bool(liquid_ok)
                if (c_sum <= -50.0 and s_sum <= 2.0) or (s_sum <= -10.0 and c_sum <= 10.0):
                    msg = f"{prefix}🔥 BULLISH ALPHA ABSORPCE (Úzký Range {close_spread_pct:.2f}% ≤0.15% / {win} sv.): Pohlcen prodej (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok:
                        odesli_upozorneni(f"RNG_BULL_ZONE_{range_zone_bucket}", "SETUP 1: BULLISH ÚZKÝ RANGE", msg, cooldown_sec=7200, category_key="SETUP1_ANY", category_cooldown=1800)
                    return msg, bool(liquid_ok)

        return "Skenuji Alpha Setup 1 (3x Equal Highs/Lows ±0.08% s CVD ±50 / Spot ±10 NEBO Úzký Range ≤0.15%)...", False
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

        pdh, pdl = 0.0, float('inf')
        for c in candles_1h:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_p)
            if dt.date() == yesterday_date:
                pdh, pdl = max(pdh, float(c[2])), min(pdl, float(c[3]))
        if pdh == 0.0:
            pdh, pdl = 0.0, 0.0

        all_5m_asc = candles_300[::-1]
        today_candles = []
        asia_h, asia_l = 0.0, float('inf')
        lon_h, lon_l = 0.0, float('inf')

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
            retest_tol = val * 0.0008  # Tolerance retestu 0.08 % od hladiny

            min_retest_idx = sweep_idx + 2
            max_retest_idx = min(sweep_idx + 9, n_today - 1)

            if (n_today - 1) >= min_retest_idx:
                for r_idx in range(min_retest_idx, max_retest_idx + 1):
                    tc_r = today_candles[r_idx]
                    cvd_at_retest = cum_cvd_today[r_idx]
                    cvd_diff = cvd_at_retest - cvd_at_sweep

                    price_returned = (tc_r[2] >= val - retest_tol) if is_high else (tc_r[3] <= val + retest_tol)

                    # Obousměrná anomálie CVD: >= +100 BTC NEBO <= -100 BTC u Bearish i Bullish
                    if price_returned and abs(cvd_diff) >= 100.0:
                        if r_idx >= (n_today - 3):
                            flow_type = "Absorpce" if ((is_high and cvd_diff > 0) or (not is_high and cvd_diff < 0)) else "Iniciativní odmítnutí"
                            triggered_msg = f"{prefix}🔥 SETUP 2 ALPHA ({name} {val:.0f}): SFP Retest ≤0.08% ({r_idx - sweep_idx}. sv. po sweepu) + OI {oi_flush:.1f} BTC | {flow_type} CVD {cvd_diff:+.1f} BTC!"
                            is_triggered = bool(liquid_ok)
                            if is_triggered:
                                odesli_upozorneni(f"SFP_{name}_{current_date}", f"SETUP 2: SFP {name} RETEST", triggered_msg, cooldown_sec=14400)
                        retest_hit = True
                        break

            candles_since_sweep = (n_today - 1) - sweep_idx
            if not retest_hit and 0 <= candles_since_sweep <= 9:
                curr_diff = cum_cvd_today[-1] - cvd_at_sweep
                sv_left = 9 - candles_since_sweep
                pending_retest_msgs.append(f"⏳ {name} ({val:.0f}) vybrán (OI {oi_flush:.1f}) – čekám retest ±0.08% s ±100 CVD (zbývá {sv_left} sv. | Δ {curr_diff:+.1f})")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"
        if triggered_msg:
            final_msg = triggered_msg
        elif pending_retest_msgs:
            final_msg = " | ".join(pending_retest_msgs)
        else:
            final_msg = "Čekám na protnutí Macro Levelu s výplachem OI (-50 BTC) a retest ±0.08% (2–9 svíček, ±100 CVD)..."

        return final_msg, is_triggered, levels_str
    except Exception:
        return "Načítám levely...", False, ""

@st.cache_resource
def start_background_guardian():
    def _guardian_loop():
        tick = 0
        while True:
            try:
                poll_realtime_okx_flow()
                if tick % 3 == 0:
                    liq_ok, _ = check_liquid_hours()
                    if liq_ok:
                        data = fetch_okx_data()
                        c_300, c_1h, fut_map, oi_change_map = data[12], data[13], data[14], data[16]
                        c_16_asc, cvd_16, scvd_16 = data[20], data[21], data[22]
                        scan_setup_1(c_16_asc, cvd_16, scvd_16, liq_ok)
                        scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liq_ok)
                tick += 1
            except Exception:
                pass
            time.sleep(10)

    t = threading.Thread(target=_guardian_loop, daemon=True)
    t.start()
    return True

start_background_guardian()

liquid_ok, liq_status_text = check_liquid_hours()
total_pnl, win_rate = load_trading_data()
(cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9,
 cvd_12, scvd_12, c_12_asc, c_300, c_1h, fut_map, spot_map, oi_change_map, b_price, vp_data, liq_data,
 c_16_asc, cvd_16, scvd_16) = fetch_okx_data()
poc_1h, vah_1h, val_1h = vp_data
upper_p, upper_btc, lower_p, lower_btc = liq_data

msg1, trg1 = scan_setup_1(c_16_asc, cvd_16, scvd_16, liquid_ok)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liquid_ok)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

c_cvd1 = '#3fb950' if cvd1 >= 0 else '#f85149'
c_cvd5 = '#3fb950' if cvd5 >= 0 else '#f85149'
c_cvd9 = '#3fb950' if cvd9 >= 0 else '#f85149'

c_scvd1 = '#3fb950' if scvd1 >= 0 else '#f85149'
c_scvd5 = '#3fb950' if scvd5 >= 0 else '#f85149'
c_scvd9 = '#3fb950' if scvd9 >= 0 else '#f85149'

c_oi1 = '#3fb950' if oi1 >= 0 else '#f85149'
c_oi5 = '#3fb950' if oi5 >= 0 else '#f85149'
c_oi9 = '#3fb950' if oi9 >= 0 else '#f85149'

pnl_color = '#3fb950' if total_pnl >= 0 else '#f85149'
pnl_sign = '+$' if total_pnl >= 0 else '-$'

cvd_bar_pct = min(48.0, max(4.0, (abs(cvd5) / 150.0) * 48.0))
cvd_mercury_cls = "thermo-mercury-up" if cvd5 >= 0 else "thermo-mercury-down"

spot_bar_pct = min(48.0, max(4.0, (abs(scvd5) / 30.0) * 48.0))
spot_mercury_cls = "thermo-mercury-up" if scvd5 >= 0 else "thermo-mercury-down"

oi_bar_pct = min(48.0, max(4.0, (abs(oi5) / 120.0) * 48.0))
oi_bar_left = "50%" if oi5 >= 0 else f"{50.0 - oi_bar_pct:.1f}%"
oi_bar_color = "#3fb950" if oi5 >= 0 else "#f85149"

st.markdown('<div class="gold-btc-banner"></div>', unsafe_allow_html=True)

# --- FUTURISTICKÝ OKX MATRIX ---
matrix_html = f"""<div class="matrix-unified">
<div style="color: #ffffff; font-weight: 900; font-size: 18px; margin-bottom: 12px; letter-spacing: 2px; text-shadow: 0px 2px 8px rgba(0,0,0,1);">OKX ORDER FLOW & LIQUIDATION MATRIX</div>
<div class="matrix-grid">
<div class="thermo-card">
<div style="color: #00f3ff; font-size: 12px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 2px 4px #000;">CVD (FUT)</div>
<div style="font-size: 20px; font-weight: 900; color: {c_cvd1}; text-shadow: 0 0 10px #000;">{cvd1:+,.1f}</div>
<div class="thermo-tube-wrap">
<div class="thermo-scale">
<span style="color:#3fb950;">+150</span>
<span style="color:#7ee787;">+75</span>
<span style="color:#ffffff;">0</span>
<span style="color:#ffa198;">-75</span>
<span style="color:#f85149;">-150</span>
</div>
<div class="thermo-glass">
<div class="thermo-zero-line"></div>
<div class="{cvd_mercury_cls}" style="height: {cvd_bar_pct:.1f}%;"></div>
</div>
</div>
<div style="width: 100%; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 4px;">
<div style="font-size: 9px; color: #94a3b8; font-weight: 800;">25M / 45M DELTA</div>
<div style="font-size: 13px; font-weight: 900; color: {c_cvd5};">{cvd5:+,.1f}</div>
<div style="font-size: 11px; font-weight: 900; color: {c_cvd9}; opacity: 0.85;">{cvd9:+,.1f}</div>
</div>
</div>
<div style="display: flex; flex-direction: column; justify-content: space-between;">
<div class="liq-bumper-box">
<div style="color: #f85149; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 SHORT LIQ (+2%)</div>
<div style="font-size: 19px; font-weight: 900; color: #ffffff; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px rgba(248,81,73,0.7);">{upper_p:,.0f} $</div>
<div style="color: #f1e05a; font-size: 11px; font-weight: 900; text-shadow: 0 1px 3px #000;">({upper_btc:.1f} BTC)</div>
</div>
<div class="matrix-live-price">{b_price:,.0f}</div>
<div class="liq-bumper-box">
<div style="color: #3fb950; font-size: 10px; font-weight: 900; letter-spacing: 1px; text-shadow: 0 1px 4px #000;">🎯 LONG LIQ (-2%)</div>
<div style="font-size: 19px; font-weight: 900; color: #ffffff; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px rgba(63,185,80,0.7);">{lower_p:,.0f} $</div>
<div style="color: #f1e05a; font-size: 11px; font-weight: 900; text-shadow: 0 1px 3px #000;">({lower_btc:.1f} BTC)</div>
</div>
<div class="oi-center-box">
<div style="color: #00f3ff; font-size: 10px; font-weight: 900; letter-spacing: 1px;">OPEN INTEREST (OI)</div>
<div class="oi-bar-track">
<div style="position:absolute; left:50%; top:0; bottom:0; width:2px; background:#fff; z-index:3;"></div>
<div style="position:absolute; top:1px; bottom:1px; left:{oi_bar_left}; width:{oi_bar_pct:.1f}%; background:{oi_bar_color}; border-radius:4px; box-shadow: 0 0 8px {oi_bar_color};"></div>
</div>
<div style="font-size: 15px; font-weight: 900; color: {c_oi1};">{oi1:+,.1f} BTC</div>
<div style="font-size: 11px; font-weight: 800; color: #cbd5e1;"><span style="color:{c_oi5};">{oi5:+,.1f}</span> | <span style="color:{c_oi9};">{oi9:+,.1f}</span></div>
</div>
</div>
<div class="thermo-card">
<div style="color: #f1e05a; font-size: 12px
