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

# --- NASTAVENÍ TELEGRAM NOTIFIKACÍ + OCHRANA PROTI SPAMU ---
TELEGRAM_BOT_TOKEN = "9068673685:AAEwXgVLOdO-kZ3Pvm3ATu87vZ6eZ-zP-cY"
TELEGRAM_CHAT_ID = "9209356727"

ALERT_COOLDOWN_STATE = {"last_key": "", "last_ts": 0.0}

def odesli_upozorneni(setup_nazev, detail_zpravy):
    now_ts = time.time()
    alert_key = f"{setup_nazev}_{detail_zpravy[:35]}"
    # Neposílat stejný alert vícekrát než jednou za 15 minut (900 s)
    if ALERT_COOLDOWN_STATE["last_key"] == alert_key and (now_ts - ALERT_COOLDOWN_STATE["last_ts"]) < 900:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚨 <b>{setup_nazev}</b>\n\n{detail_zpravy}",
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=5)
        
        ALERT_COOLDOWN_STATE["last_key"] = alert_key
        ALERT_COOLDOWN_STATE["last_ts"] = now_ts
    except Exception as e:
        print(f"Telegram alert selhal: {e}")

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
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@800;900&display=swap');

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

.matrix-live-price {
    font-family: 'Orbitron', sans-serif;
    font-size: 34px;
    font-weight: 900;
    color: #f0f6fc;
    letter-spacing: 2px;
    text-align: center;
    padding: 0 6px;
    text-shadow: 0 0 12px rgba(0, 243, 255, 0.4), 0 2px 5px rgba(0, 0, 0, 1);
}

.matrix-unified { 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.45), rgba(4, 6, 9, 0.85)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-position: center top;
    background-size: cover;
    border: 1px solid #2dd4bf; 
    border-radius: 16px; 
    padding: 20px 10px 25px 10px; 
    text-align: center; 
    margin-bottom: 18px; 
    box-shadow: 0 5px 30px rgba(0, 243, 255, 0.15); 
    position: relative;
    overflow: hidden;
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
        return True, f"🟢 LIKVIDNÍ OKNO AKTIVNÍ ({now_p.strftime('%H:%M')}) | 24/7 Cloud Hlídač zapnutý"
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

def to_btc_vol(raw_contracts, price, ct_val, ct_ccy):
    if ct_ccy == "BTC":
        return raw_contracts * ct_val
    return (raw_contracts * ct_val) / price if price > 0 else 0.0

def get_market_radar(btc_price, ts):
    imb_vol = 0.0
    ask_v1, ask_v2, ask_v3 = 0.0, 0.0, 0.0
    bid_v1, bid_v2, bid_v3 = 0.0, 0.0, 0.0
    try:
        endpoints = [
            ("https://eea.okx.com/api/v5/market/books-full?instId=BTC-USD_UM_XPERP-310404&sz=5000", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books-full?instId=BTC-USD_UM_XPERP-310404&sz=5000", "BTC-USD_UM_XPERP-310404"),
            ("https://eea.okx.com/api/v5/market/books?instId=BTC-USD_UM_XPERP-310404&sz=400", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books?instId=BTC-USD_UM_XPERP-310404&sz=400", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books-full?instId=BTC-USDT-SWAP&sz=5000", "BTC-USDT-SWAP")
        ]
        book, active_inst = {}, "BTC-USD_UM_XPERP-310404"
        for bu, inst_name in endpoints:
            try:
                res = requests.get(f"{bu}&t={ts}", timeout=4).json().get("data", [])
                if res and (res[0].get("asks") or res[0].get("bids")):
                    book, active_inst = res[0], inst_name
                    break
            except Exception:
                continue

        ct_val, ct_ccy = get_contract_spec(active_inst)
        for a in book.get("asks", []):
            p, v = float(a[0]), float(a[1])
            dist = p - btc_price
            if 0 <= dist <= 400:
                vol = to_btc_vol(v, p, ct_val, ct_ccy)
                imb_vol -= vol
                if dist <= 100: ask_v1 += vol
                elif dist <= 200: ask_v2 += vol
                elif dist <= 300: ask_v3 += vol
                
        for b in book.get("bids", []):
            p, v = float(b[0]), float(b[1])
            dist = btc_price - p
            if 0 <= dist <= 400:
                vol = to_btc_vol(v, p, ct_val, ct_ccy)
                imb_vol += vol
                if dist <= 100: bid_v1 += vol
                elif dist <= 200: bid_v2 += vol
                elif dist <= 300: bid_v3 += vol
    except Exception:
        pass

    current_radar = (imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3)
    if (ask_v1 + ask_v2 + bid_v1 + bid_v2) > 0:
        try:
            st.session_state["last_valid_radar"] = current_radar
        except Exception:
            pass
        return current_radar
    try:
        return st.session_state.get("last_valid_radar", current_radar)
    except Exception:
        return current_radar

def compute_1m_bridge_delta(candles_1m, candle_open_ts, is_spot=False):
    total_delta = 0.0
    for m in candles_1m:
        try:
            m_ts = int(m[0])
            if candle_open_ts <= m_ts < candle_open_ts + 300000:
                o, h, l, cl = float(m[1]), float(m[2]), float(m[3]), float(m[4])
                if h <= l: continue
                vol_btc = float(m[5]) if is_spot else float(m[6])
                body_pressure = (cl - o) / (h - l)
                wick_pressure = (2.0 * cl - h - l) / (h - l)
                combined_ratio = 0.55 * body_pressure + 0.45 * wick_pressure
                total_delta += vol_btc * combined_ratio * 0.15
        except Exception:
            continue
    return total_delta

def compute_1h_volume_profile(candles_1m_vp, c_12_asc):
    source_candles = candles_1m_vp[1:61] if len(candles_1m_vp) >= 30 else c_12_asc
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
    ts = int(time.time() * 1000)
    try:
        candles_300 = get_okx_candles("5m", 300, ts, ["BTC-USD_UM_XPERP-310404", "BTC-USDT-SWAP"])
        fallback_p = float(candles_300[0][4]) if candles_300 else 75000.0
        btc_price = get_live_xperp_price(fallback_p, ts)
        candles_1h = get_okx_candles("1H", 72, ts, ["BTC-USD_UM_XPERP-310404", "BTC-USDT-SWAP"])
        
        c_12_desc = candles_300[1:13] if len(candles_300) >= 13 else candles_300[:12]
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
            except: continue

        spot_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SPOT&period=5m&limit=100&t={ts}", timeout=5).json().get("data", [])
        spot_map = {}
        for row in spot_res:
            try:
                open_ts = int(row[0]) - 300000
                spot_map[open_ts] = float(row[2]) - float(row[1])
            except: continue

        candles_1m_fut = get_okx_candles("1m", 62, ts, ["BTC-USDT-SWAP", "BTC-USD_UM_XPERP-310404"])
        missing_spot = any(int(c[0]) not in spot_map for c in c_12_asc[-2:])
        candles_1m_spot = get_okx_candles("1m", 25, ts, ["BTC-USDT"]) if missing_spot else []

        cvd_12, scvd_12 = [], []
        for c in c_12_asc:
            open_ts = int(c[0])
            if open_ts in fut_map: cvd_12.append(fut_map[open_ts])
            else:
                val_f = compute_1m_bridge_delta(candles_1m_fut, open_ts, False)
                fut_map[open_ts] = val_f
                cvd_12.append(val_f)

            if open_ts in spot_map: scvd_12.append(spot_map[open_ts])
            else:
                val_s = compute_1m_bridge_delta(candles_1m_spot, open_ts, True)
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
                except: continue

        oi_12 = []
        if len(oi_res) >= 13:
            for i in range(12, 0, -1):
                open_curr = int(oi_res[i - 1][0]) - 300000
                oi_12.append(oi_change_map.get(open_curr, 0.0))
        else:
            oi_12 = [0.0] * 12

        radar_data = get_market_radar(btc_price, ts)
        vp_data = compute_1h_volume_profile(candles_1m_fut, c_12_asc)
        
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
                cvd_12, scvd_12, c_12_asc, candles_300, candles_1h, fut_map, spot_map, oi_change_map, btc_price, radar_data, vp_data)
    except Exception:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                [], [], [], [], [], {}, {}, {}, 75000.0, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

def scan_setup_1(c_12_asc, cvd_12, scvd_12, liquid_ok):
    try:
        if len(c_12_asc) < 12 or len(cvd_12) < 12 or len(scvd_12) < 12:
            return "Načítám 1H strukturu svíček...", False

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
                
                # BEARISH EQUAL HIGHS
                wick_diff_h = abs(highs[j] - highs[i])
                if wick_diff_h <= 50.0:
                    if max(highs[i], highs[j]) >= max_all_h - 25.0:
                        max_between_h = max(highs[i + 1:j])
                        min_pullback_h = min(lows[i + 1:j])
                        if max_between_h <= max(highs[i], highs[j]) + 15.0 and (max(highs[i], highs[j]) - min_pullback_h) >= 120.0:
                            c_diff = cum_c[j] - cum_c[i]
                            s_diff = cum_s[j] - cum_s[i]
                            if c_diff >= 15.0 or s_diff >= 3.0:
                                src_name = "CVD+SPOT" if (c_diff >= 15.0 and s_diff >= 3.0) else ("CVD" if c_diff >= 15.0 else "SPOT")
                                msg = f"{prefix}🔥 BEARISH ABSORPCE (Equal Highs Δ {wick_diff_h:.0f}$ | Pullback ≥ 120$): {src_name} anomálie na vrcholu (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                                if liquid_ok: odesli_upozorneni("SETUP 1: BEARISH EQUAL HIGHS", msg)
                                return msg, bool(liquid_ok)

                # BULLISH EQUAL LOWS
                wick_diff_l = abs(lows[j] - lows[i])
                if wick_diff_l <= 50.0:
                    if min(lows[i], lows[j]) <= min_all_l + 25.0:
                        min_between_l = min(lows[i + 1:j])
                        max_bounce_l = max(highs[i + 1:j])
                        if min_between_l >= min(lows[i], lows[j]) - 15.0 and (max_bounce_l - min(lows[i], lows[j])) >= 120.0:
                            c_diff = cum_c[j] - cum_c[i]
                            s_diff = cum_s[j] - cum_s[i]
                            if c_diff <= -15.0 or s_diff <= -3.0:
                                src_name = "CVD+SPOT" if (c_diff <= -15.0 and s_diff <= -3.0) else ("CVD" if c_diff <= -15.0 else "SPOT")
                                msg = f"{prefix}🔥 BULLISH ABSORPCE (Equal Lows Δ {wick_diff_l:.0f}$ | Pullback ≥ 120$): {src_name} anomálie na dně (CVD {c_diff:+.1f} / Spot {s_diff:+.1f})!"
                                if liquid_ok: odesli_upozorneni("SETUP 1: BULLISH EQUAL LOWS", msg)
                                return msg, bool(liquid_ok)

        max_body_pct = 0.0020
        for win in range(5, 13):
            sub_c = closes[-win:]
            ref_price = sub_c[-1] if sub_c[-1] > 0 else 75000.0
            close_spread = max(sub_c) - min(sub_c)
            close_spread_pct = (close_spread / ref_price) * 100.0

            if close_spread <= (ref_price * max_body_pct):
                c_sum = sum(cvd_12[-win:])
                s_sum = sum(scvd_12[-win:])

                if c_sum >= 35.0 or s_sum >= 5.0:
                    msg = f"{prefix}🔥 BEARISH ABSORPCE (Úzký Range {close_spread_pct:.2f}% / {win} sv.): Pohlcen nákup (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok: odesli_upozorneni("SETUP 1: BEARISH ÚZKÝ RANGE", msg)
                    return msg, bool(liquid_ok)
                if c_sum <= -35.0 or s_sum <= -5.0:
                    msg = f"{prefix}🔥 BULLISH ABSORPCE (Úzký Range {close_spread_pct:.2f}% / {win} sv.): Pohlcen prodej (CVD {c_sum:+.1f} BTC | Spot {s_sum:+.1f} BTC)!"
                    if liquid_ok: odesli_upozorneni("SETUP 1: BULLISH ÚZKÝ RANGE", msg)
                    return msg, bool(liquid_ok)

        return "Skenuji Setup 1 (Equal Highs/Lows pullback ≥ 120$ NEBO Úzký Range ≤ 0,20% + CVD/Spot anomálie)...", False
    except Exception:
        return "Načítám data Setupu 1...", False

def scan_setup_2(candles_300, candles_1h, fut_map, oi_change_map, liquid_ok):
    try:
        if len(candles_300) < 20 or len(candles_1h) < 10:
            return "Načítám historii trhu...", False, "Skenuji levely..."

        try: tz_p = ZoneInfo("Europe/Prague")
        except: tz_p = timezone(timedelta(hours=1))

        now_prague = datetime.now(tz_p)
        current_date = now_prague.date()
        yesterday_date = current_date - timedelta(days=1)

        pdh, pdl = 0.0, float('inf')
        for c in candles_1h:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_p)
            if dt.date() == yesterday_date:
                pdh, pdl = max(pdh, float(c[2])), min(pdl, float(c[3]))
        if pdh == 0.0: pdh, pdl = 0.0, 0.0

        closed_5m_asc = candles_300[1:][::-1]
        today_candles = []
        asia_h, asia_l = 0.0, float('inf')
        lon_h, lon_l = 0.0, float('inf')

        for c in closed_5m_asc:
            ts_c = int(c[0])
            dt = datetime.fromtimestamp(ts_c / 1000, tz_p)
            if dt.date() != current_date: continue
            today_candles.append((ts_c, float(c[1]), float(c[2]), float(c[3]), float(c[4]), dt.hour))
            if 1 <= dt.hour < 7: asia_h, asia_l = max(asia_h, float(c[2])), min(asia_l, float(c[3]))
            elif 9 <= dt.hour < 14: lon_h, lon_l = max(lon_h, float(c[2])), min(lon_l, float(c[3]))

        if asia_h == 0.0: asia_h, asia_l = 0.0, 0.0
        if lon_h == 0.0: lon_h, lon_l = 0.0, 0.0

        raw_levels = [("PDH", pdh, True, 0), ("PDL", pdl, False, 0), ("ASIA H", asia_h, True, 7), ("ASIA L", asia_l, False, 7), ("LON H", lon_h, True, 14), ("LON L", lon_l, False, 14)]
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
            if val <= 0 or now_prague.hour < valid_from_hour: continue

            sweep_idx = None
            for idx, tc in enumerate(today_candles):
                if tc[5] < valid_from_hour: continue
                if is_high and tc[2] >= val: sweep_idx = idx; break
                if not is_high and tc[3] <= val: sweep_idx = idx; break

            if sweep_idx is None:
                untouched_levels.append(f"{name}: {val:.0f}")
                continue

            ts_sweep = today_candles[sweep_idx][0]
            oi_flush = min(oi_change_map.get(ts_sweep, 0.0), oi_change_map.get(ts_sweep, 0.0) + oi_change_map.get(ts_sweep + 300000, 0.0))

            if oi_flush > -50.0: continue

            cvd_at_sweep = cum_cvd_today[sweep_idx]
            retest_hit = False

            if n_today > sweep_idx + 2:
                for r_idx in range(max(sweep_idx + 2, n_today - 3), n_today):
                    cvd_at_retest = cum_cvd_today[r_idx]
                    cvd_diff = cvd_at_retest - cvd_at_sweep

                    if is_high:
                        if cvd_diff >= 100.0:
                            triggered_msg = f"{prefix}🔥 SETUP 2 PLATNÝ ({name} {val:.0f}): OI výplach {oi_flush:.1f} BTC + Další pokus s vyšším CVD ({cvd_diff:+.1f} BTC)!"
                            is_triggered = bool(liquid_ok)
                            if is_triggered: odesli_upozorneni(f"SFP {name} RETEST", triggered_msg)
                            retest_hit = True; break
                    else:
                        if cvd_diff <= -100.0:
                            triggered_msg = f"{prefix}🔥 SETUP 2 PLATNÝ ({name} {val:.0f}): OI výplach {oi_flush:.1f} BTC + Další pokus s nižším CVD ({cvd_diff:+.1f} BTC)!"
                            is_triggered = bool(liquid_ok)
                            if is_triggered: odesli_upozorneni(f"SFP {name} RETEST", triggered_msg)
                            retest_hit = True; break

            if not retest_hit:
                curr_diff = cum_cvd_today[-1] - cvd_at_sweep if n_today > 0 else 0.0
                pending_retest_msgs.append(f"⏳ {name} ({val:.0f}) vybrán (OI {oi_flush:.1f}) – čekám na ±100 CVD (Δ {curr_diff:+.1f})")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"
        if triggered_msg: final_msg = triggered_msg
        elif pending_retest_msgs: final_msg = " | ".join(pending_retest_msgs)
        else: final_msg = "Čekám na protnutí Macro Levelu s výplachem OI (-50 BTC)..."

        return final_msg, is_triggered, levels_str
    except Exception:
        return "Načítám levely...", False, ""

# --- 24/7 CLOUD BACKGROUND WORKER (BĚŽÍ NA SERVERU I PŘI ZAMKNUTÉM MOBILU) ---
@st.cache_resource
def start_background_guardian():
    def _guardian_loop():
        while True:
            try:
                liq_ok, _ = check_liquid_hours()
                if liq_ok:
                    data = fetch_okx_data()
                    cvd_12, scvd_12, c_12_asc = data[9], data[10], data[11]
                    c_300, c_1h, fut_map, oi_change_map = data[12], data[13], data[14], data[16]
                    scan_setup_1(c_12_asc, cvd_12, scvd_12, liq_ok)
                    scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liq_ok)
            except Exception:
                pass
            time.sleep(30)

    t = threading.Thread(target=_guardian_loop, daemon=True)
    t.start()
    return True

start_background_guardian()

liquid_ok, liq_status_text = check_liquid_hours()
total_pnl, win_rate = load_trading_data()
(cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9,
 cvd_12, scvd_12, c_12_asc, c_300, c_1h, fut_map, spot_map, oi_change_map, b_price, radar, vp_data) = fetch_okx_data()
imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3 = radar
poc_1h, vah_1h, val_1h = vp_data

msg1, trg1 = scan_setup_1(c_12_asc, cvd_12, scvd_12, liquid_ok)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, fut_map, oi_change_map, liquid_ok)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

imb_color = '#3fb950' if imb_vol >= 0 else '#f85149'

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

st.markdown("""
<div class="gold-btc-banner"></div>
""", unsafe_allow_html=True)

# HLAVNÍ MATICE DAT
st.markdown(f"""
<div class="matrix-unified">
<div style="color: #ffffff; font-weight: 900; font-size: 20px; margin-bottom: 25px; letter-spacing: 2px; text-shadow: 0px 2px 8px rgba(0,0,0,1);">OKX ORDER FLOW MATRIX</div>
<div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 6px; align-items: center; margin-bottom: 18px;">
<div style="font-size: 25px; font-weight: 900; color: #f85149; text-align: center;">{ask_v3:.0f}</div>
<div></div>
<div style="font-size: 25px; font-weight: 900; color: #3fb950; text-align: center;">{bid_v1:.0f}</div>
<div style="font-size: 25px; font-weight: 900; color: #f85149; text-align: center;">{ask_v2:.0f}</div>
<div class="matrix-live-price">{b_price:.0f}</div>
<div style="font-size: 25px; font-weight: 900; color: #3fb950; text-align: center;">{bid_v2:.0f}</div>
<div style="font-size: 25px; font-weight: 900; color: #f85149; text-align: center;">{ask_v1:.0f}</div>
<div></div>
<div style="font-size: 25px; font-weight: 900; color: #3fb950; text-align: center;">{bid_v3:.0f}</div>
</div>
<div style="text-align: center; margin-bottom: 28px;">
<span style="font-size: 26px; font-weight: 900; color: {imb_color}; text-shadow: 0px 2px 8px rgba(0,0,0,0.8);">{imb_vol:+,.1f}</span>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; align-items: center; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 15px;">
<div style="color: #e2e8f0; font-size: 13px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">CVD</div>
<div style="color: #00f3ff; font-size: 13px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">SPOT</div>
<div style="color: #e2e8f0; font-size: 13px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">OI</div>
<div style="font-size: 28px; font-weight: 900; color: {c_cvd1};">{cvd1:+,.1f}</div>
<div style="font-size: 28px; font-weight: 900; color: {c_scvd1};">{scvd1:+,.1f}</div>
<div style="font-size: 28px; font-weight: 900; color: {c_oi1};">{oi1:+,.1f}</div>
<div style="font-size: 22px; font-weight: 900; color: {c_cvd5}; opacity: 0.85;">{cvd5:+,.1f}</div>
<div style="font-size: 22px; font-weight: 900; color: {c_scvd5}; opacity: 0.85;">{scvd5:+,.1f}</div>
<div style="font-size: 22px; font-weight: 900; color: {c_oi5}; opacity: 0.85;">{oi5:+,.1f}</div>
<div style="font-size: 18px; font-weight: 900; color: {c_cvd9}; opacity: 0.7;">{cvd9:+,.1f}</div>
<div style="font-size: 18px; font-weight: 900; color: {c_scvd9}; opacity: 0.7;">{scvd9:+,.1f}</div>
<div style="font-size: 18px; font-weight: 900; color: {c_oi9}; opacity: 0.7;">{oi9:+,.1f}</div>
</div>
</div>
""", unsafe_allow_html=True)

# VIZUÁLNÍ DETEKCE ABSORPCE + 1H VOLUME PROFILE
st.markdown(f"""
<div style="text-align: center; margin-top: 5px; margin-bottom: -15px; z-index: 10; position: relative;">
    <div style="color: #ffffff; font-weight: 900; font-size: 16px; letter-spacing: 2px; text-shadow: 0 2px 5px black;">ABSORPCE & 1H VOLUME PROFILE</div>
    <div style="color: #2dd4bf; font-size: 10px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 1px 3px black;">VAH: {vah_1h:.0f} 🔸 POC: {poc_1h:.0f} 🔸 VAL: {val_1h:.0f}</div>
</div>
""", unsafe_allow_html=True)

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

    # 0. Vykreslení 1H Volume Profile (Value Area podsvícení + VAH, POC, VAL linky)
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
        # VAH linka
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[vah_1h, vah_1h],
            mode='lines',
            line=dict(color='rgba(247, 147, 26, 0.65)', width=1.3, dash='dash'),
            hoverinfo='skip', showlegend=False
        ), row=1, col=1)
        # POC linka (hlavní magnet)
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[poc_1h, poc_1h],
            mode='lines',
            line=dict(color='#f7931a', width=2.2),
            hoverinfo='skip', showlegend=False
        ), row=1, col=1)
        # VAL linka
        fig.add_trace(go.Scatter(
            x=[-0.8, 11.3], y=[val_1h, val_1h],
            mode='lines',
            line=dict(color='rgba(247, 147, 26, 0.65)', width=1.3, dash='dash'),
            hoverinfo='skip', showlegend=False
        ), row=1, col=1)

        # Štítky VAH, POC, VAL vlevo
        for lbl_txt, lbl_val, lbl_col in [("VAH", vah_1h, "#f59e0b"), ("POC", poc_1h, "#f7931a"), ("VAL", val_1h, "#f59e0b")]:
            fig.add_annotation(
                x=0.0, y=lbl_val,
                xref='paper', yref='y',
                text=f"<b>{lbl_txt} {lbl_val:.0f}</b>",
                showarrow=False,
                xanchor='left', yanchor='middle',
                font=dict(family="Orbitron, sans-serif", size=9, color=lbl_col),
                bgcolor="rgba(4, 6, 9, 0.85)",
                bordercolor=lbl_col,
                borderwidth=1,
                borderpad=2
            )
    
    # 1. Price (12 uzavřených 5m svíček)
    fig.add_trace(go.Candlestick(x=x_axis,
                                 open=[float(c[1]) for c in c_12_asc],
                                 high=[float(c[2]) for c in c_12_asc],
                                 low=[float(c[3]) for c in c_12_asc],
                                 close=[float(c[4]) for c in c_12_asc],
                                 increasing_line_color='#3fb950', decreasing_line_color='#f85149',
                                 increasing_fillcolor='#3fb950', decreasing_fillcolor='#f85149',
                                 increasing_line_width=1.8, decreasing_line_width=1.8,
                                 whiskerwidth=0.3,
                                 showlegend=False), row=1, col=1)

    # NEZÁVISLÝ LIVE PRICE TRACKER
    fig.add_trace(go.Scatter(
        x=[-0.8, 13.6],
        y=[b_price, b_price],
        mode='lines',
        line=dict(color='rgba(0, 243, 255, 0.55)', width=1.4, dash='dot'),
        hoverinfo='skip',
        showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[11.55],
        y=[b_price],
        mode='markers',
        marker=dict(color='#00f3ff', size=7, line=dict(color='#ffffff', width=1.5)),
        hoverinfo='skip',
        showlegend=False
    ), row=1, col=1)

    # Pravý posuvný štítek
    fig.add_annotation(
        x=1.0,
        y=b_price,
        xref='paper',
        yref='y',
        text=f"<b>{b_price:.0f}</b>",
        showarrow=False,
        xanchor='right',
        yanchor='middle',
        font=dict(family="Orbitron, sans-serif", size=12, color="#00f3ff"),
        bgcolor="rgba(4, 6, 9, 0.95)",
        bordercolor="#00f3ff",
        borderwidth=1.5,
        borderpad=4
    )
                                 
    # 2. Futures CVD 
    fig.add_trace(go.Scatter(x=x_axis, y=cum_cvd_chart, mode='lines', 
                             line=dict(color='#00f3ff', width=3, shape='spline', smoothing=1.1), showlegend=False), row=2, col=1)
                             
    # 3. Spot CVD 
    fig.add_trace(go.Scatter(x=x_axis, y=cum_scvd_chart, mode='lines', 
                             line=dict(color='#f1e05a', width=3, shape='spline', smoothing=1.1), showlegend=False), row=3, col=1)

    def get_smart_range(arr, pad_ratio=0.02):
        if not arr: return [0, 1]
        mn, mx = min(arr), max(arr)
        pd_val = (mx - mn) * pad_ratio
        if pd_val == 0: pd_val = 10
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
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, rangeslider=dict(visible=False), fixedrange=True, range=[-0.8, 13.6]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=p_rng),
        xaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=c_rng),
        xaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=[-0.8, 13.6]),
        yaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=s_rng)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# SETUP KARTY 
liq_color = "#3fb950" if liquid_ok else "#94a3b8"
st.markdown(f"""
<div class="setups-container">
<div style="text-align: center; font-size: 11px; font-weight: 900; color: {liq_color}; letter-spacing: 1px; margin-bottom: 10px;">{liq_status_text}</div>
<div class="alert-box {"signal-triggered" if trg1 else ""}">
<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">⚡ SETUP 1: ABSORPCE (EQUAL H/L & ÚZKÝ RANGE)</div>
<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg1}</div>
</div>
<div class="alert-box {"signal-triggered" if trg2 else ""}" style="margin-bottom: 0;">
<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">🎯 SETUP 2: MACRO SFP + RETEST</div>
<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg2}</div>
<div style="color: #00f3ff; font-size: 12px; margin-top: 6px; font-weight: 800;">Zbývající levely: {l_str}</div>
</div>
</div>
""", unsafe_allow_html=True)

# MONEY JOURNAL
st.markdown(f"""
<div class="money-journal">
<div class="money-content">
<div style="text-align: center;">
<div style="color: #7ee787; font-size: 14px; font-weight: 900; letter-spacing: 2px; text-shadow: 0px 2px 6px rgba(0,0,0,0.9);">CELKOVÝ PNL</div>
<div style="font-size: 34px; font-weight: 900; color: {pnl_color}; text-shadow: 0px 2px 10px rgba(0,0,0,0.9);">{pnl_sign}{abs(total_pnl):,.2f}</div>
</div>
<div style="text-align: center;">
<div style="color: #f1e05a; font-size: 14px; font-weight: 900; letter-spacing: 2px; text-shadow: 0px 2px 6px rgba(0,0,0,0.9);">WIN RATE</div>
<div style="font-size: 34px; font-weight: 900; color: #f1e05a; text-shadow: 0px 2px 10px rgba(0,0,0,0.9);">{win_rate:.2f} %</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

if st.button("🔄 AKTUALIZOVAT"): pass
if st.toggle("⏱️ Auto Refresh (20s)", value=False):
    time.sleep(20)
    st.rerun()
