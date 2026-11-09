import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import time
from datetime import datetime, timezone, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    padding: 16px; 
    border-radius: 15px; 
    margin-bottom: 12px; 
    backdrop-filter: blur(1px); 
    height: 125px;
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

def get_okx_candles(bar, limit, ts):
    urls = [
        f"https://eea.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar={bar}&limit={limit}&t={ts}",
        f"https://eea.okx.com/api/v5/market/candles?instId=BTC-USDT&bar={bar}&limit={limit}&t={ts}"
    ]
    for u in urls:
        try:
            data = requests.get(u, timeout=5).json().get("data", [])
            if data: return data
        except Exception:
            continue
    return []

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
            ("https://www.okx.com/api/v5/market/books?instId=BTC-USD-SWAP&sz=400", "BTC-USD-SWAP"),
            ("https://eea.okx.com/api/v5/market/books?instId=BTC-USD-SWAP&sz=400", "BTC-USD-SWAP"),
            ("https://www.okx.com/api/v5/market/books?instId=BTC-USDT&sz=400", "BTC-USDT")
        ]
        book, active_inst = {}, "BTC-USD-SWAP"
        for bu, inst_name in endpoints:
            try:
                res = requests.get(bu, timeout=5).json().get("data", [])
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
    return imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3

def fetch_okx_data():
    ts = int(time.time() * 1000)
    try:
        candles_300 = get_okx_candles("5m", 300, ts)
        btc_price = float(candles_300[0][4]) if candles_300 else 76000.0
        candles_1h = get_okx_candles("1H", 72, ts)
        
        # Bereme čistých 12 UZAVŘENÝCH svíček pro křivky (stabilní historie)
        c_12_desc = candles_300[1:13] if len(candles_300) >= 13 else candles_300[:12]
        c_12_asc = c_12_desc[::-1] 

        # 1. FUTURES CVD MAP (Uzavřené 5M svíčky)
        vol_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&limit=20&t={ts}", timeout=6).json().get("data", [])
        fut_map = {}
        for row in vol_res:
            tot_vol = float(row[2]) + float(row[1])
            delta_raw = float(row[2]) - float(row[1])
            fut_map[int(row[0])] = (delta_raw / btc_price) if tot_vol > 50000 else delta_raw

        # 2. SPOT CVD MAP (Uzavřené 5M svíčky)
        spot_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SPOT&period=5m&limit=20&t={ts}", timeout=6).json().get("data", [])
        spot_map = {}
        for row in spot_res:
            tot_vol = float(row[2]) + float(row[1])
            delta_raw = float(row[2]) - float(row[1])
            spot_map[int(row[0])] = (delta_raw / btc_price) if tot_vol > 50000 else delta_raw

        # 3. OPEN INTEREST MAP
        oi_res = requests.get(f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&limit=20&t={ts}", timeout=6).json().get("data", [])
        oi_map = {int(row[0]): float(row[1]) for row in oi_res}
        candle_close_map = {int(c[0]): float(c[4]) for c in candles_300}

        cvd_12, scvd_12, oi_12 = [], [], []

        for i, c in enumerate(c_12_asc):
            t = int(c[0])
            cvd_12.append(fut_map.get(t, 0.0))
            scvd_12.append(spot_map.get(t, 0.0))

            t_prev = t - 300000
            p_curr = candle_close_map.get(t, btc_price)
            p_prev = candle_close_map.get(t_prev, btc_price)
            chg = (oi_map.get(t, 0.0) / p_curr) - (oi_map.get(t_prev, 0.0) / p_prev) if p_curr > 0 and p_prev > 0 else 0.0
            oi_12.append(chg)

        radar_data = get_market_radar(btc_price, ts)
        
        cvd_1 = sum(cvd_12[-1:]) if len(cvd_12) >= 1 else 0.0
        cvd_5 = sum(cvd_12[-5:]) if len(cvd_12) >= 5 else 0.0
        cvd_9 = sum(cvd_12[-9:]) if len(cvd_12) >= 9 else 0.0

        scvd_1 = sum(scvd_12[-1:]) if len(scvd_12) >= 1 else 0.0
        scvd_5 = sum(scvd_12[-5:]) if len(scvd_12) >= 5 else 0.0
        scvd_9 = sum(scvd_12[-9:]) if len(scvd_12) >= 9 else 0.0
        
        oi_1 = sum(oi_12[-1:]) if len(oi_12) >= 1 else 0.0
        oi_5 = sum(oi_12[-5:]) if len(oi_12) >= 5 else 0.0
        oi_9 = sum(oi_12[-9:]) if len(oi_12) >= 9 else 0.0

        return cvd_1, cvd_5, cvd_9, scvd_1, scvd_5, scvd_9, oi_1, oi_5, oi_9, cvd_12, scvd_12, c_12_asc, candles_1h, oi_res, btc_price, radar_data
    except Exception:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [], [], [], [], [], 76000.0, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

def scan_setup_1(c_12_asc, cvd_12):
    try:
        if len(c_12_asc) < 12 or len(cvd_12) < 12: return "Načítám data...", False
        best_w = None
        for length in range(3, 13):
            sub_c = c_12_asc[-length:]
            b_highs = [max(float(k[1]), float(k[4])) for k in sub_c]
            b_lows = [min(float(k[1]), float(k[4])) for k in sub_c]
            if min(b_lows) == 0: continue
            r_pct = ((max(b_highs) - min(b_lows)) / min(b_lows)) * 100
            
            if r_pct <= 0.25:
                cum_cvd = sum(cvd_12[-length:])
                if best_w is None or abs(cum_cvd) > abs(best_w["cvd"]): best_w = {"len": length, "pct": r_pct, "cvd": cum_cvd}
        if best_w is None: return "Trh trenduje. Mimo 0,25% zámek.", False
        
        if abs(best_w["cvd"]) >= 200: 
            return f"🔥 SETUP 1 PLATNÝ! ({best_w['len']} svíček | {best_w['pct']:.2f}%) CVD: {best_w['cvd']:+.1f} BTC.", True
        return f"Range aktivní ({best_w['len']} svíček | {best_w['pct']:.2f}%). CVD: {best_w['cvd']:+.1f} BTC.", False
    except Exception: return "Načítám data...", False

def scan_setup_2(c_12_asc, candles_1h, oi_data, btc_price):
    try:
        if len(c_12_asc) < 5 or len(oi_data) < 4:
            return "Načítám historii trhu...", False, "Skenuji levely..."

        tz_offset = timezone(timedelta(hours=1))
        now_prague = datetime.now(tz_offset)
        current_date = now_prague.date()
        yesterday_date = current_date - timedelta(days=1)

        pdh, pdl = 0.0, float('inf')
        for c in candles_1h:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
            if dt.date() == yesterday_date:
                pdh = max(pdh, float(c[2]))
                pdl = min(pdl, float(c[3]))
        if pdh == 0.0: pdh, pdl = 0.0, 0.0

        asia_h, asia_l = 0.0, float('inf')
        lon_h, lon_l = 0.0, float('inf')

        for c in c_12_asc:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
            if dt.date() != current_date: continue
            h = dt.hour
            high, low = float(c[2]), float(c[3])
            if 1 <= h < 7:
                asia_h = max(asia_h, high)
                asia_l = min(asia_l, low)
            elif 9 <= h < 14:
                lon_h = max(lon_h, high)
                lon_l = min(lon_l, low)

        if asia_h == 0.0: asia_h, asia_l = 0.0, 0.0
        if lon_h == 0.0: lon_h, lon_l = 0.0, 0.0

        raw_levels = [
            ("PDH", pdh, True, 0),
            ("PDL", pdl, False, 0),
            ("ASIA H", asia_h, True, 7),
            ("ASIA L", asia_l, False, 7),
            ("LON H", lon_h, True, 14),
            ("LON L", lon_l, False, 14),
        ]

        c_last = c_12_asc[-1]
        c_last_high, c_last_low = float(c_last[2]), float(c_last[3])
        
        untouched_levels = []
        triggered_msg = None
        is_triggered = False

        for name, val, is_high, valid_from_hour in raw_levels:
            if val <= 0: continue

            already_swept_before = False
            for c in c_12_asc[:-1]:
                dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
                if dt.date() != current_date: continue
                if dt.hour >= valid_from_hour:
                    if is_high and float(c[2]) >= val: already_swept_before = True; break
                    if not is_high and float(c[3]) <= val: already_swept_before = True; break

            if already_swept_before: continue

            dt_last = datetime.fromtimestamp(int(c_last[0]) / 1000, tz_offset)
            if dt_last.date() == current_date and dt_last.hour >= valid_from_hour:
                if is_high and c_last_high >= val:
                    triggered_msg = f"👀 {name} ({val:.0f}) poprvé dotknuto."
                    is_triggered = True
                    continue
                elif not is_high and c_last_low <= val:
                    triggered_msg = f"👀 {name} ({val:.0f}) poprvé dotknuto."
                    is_triggered = True
                    continue

            untouched_levels.append(f"{name}: {val:.0f}")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"
        final_msg = triggered_msg if triggered_msg else "Čekám na první protnutí Macro Levelu..."
        return final_msg, is_triggered, levels_str
    except Exception:
        return "Načítám levely...", False, ""

total_pnl, win_rate = load_trading_data()
cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9, cvd_12, scvd_12, c_12_asc, c_1h, oi_res, b_price, radar = fetch_okx_data()
imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3 = radar

msg1, trg1 = scan_setup_1(c_12_asc, cvd_12)
msg2, trg2, l_str = scan_setup_2(c_12_asc, c_1h, oi_res, b_price)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

imb_color = '#3fb950' if imb_vol >= 0 else '#f85149'

c_cvd1 = '#3fb950' if cvd1 >= 0 else '#f85149'
c_cvd5 = '#3fb950' if cvd5 >= 0 else '#f85149'
c_cvd9 = '#3fb950' if cvd9 >= 0 else '#f85149'

c_scvd1 = '#3fb950' if scvd1 >= 0 else '#f85149'
c_scvd5 = '#3fb950' if scvd5 >= 0 else '#f85149'
c_scvd9 = '#3fb950' if scvd9 >= 0 else '#f85149'

c_oi1 = '#3fb950' if oi1 >= 0 else '#3fb950'
c_oi5 = '#3fb950' if oi5 >= 0 else '#3fb950'
c_oi9 = '#3fb950' if oi9 >= 0 else '#3fb950'

pnl_color = '#3fb950' if total_pnl >= 0 else '#f85149'
pnl_sign = '+$' if total_pnl >= 0 else '-$'

st.markdown(f"""
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

# NOVÁ SEKCE: VIZUÁLNÍ DETEKCE ABSORPCE (Fixní 12 svíček, stabilní křivky)
st.markdown("""
<div style="text-align: center; margin-top: 5px; margin-bottom: -15px; z-index: 10; position: relative;">
    <div style="color: #ffffff; font-weight: 900; font-size: 16px; letter-spacing: 2px; text-shadow: 0 2px 5px black;">ABSORPCE (1H)</div>
    <div style="color: #2dd4bf; font-size: 10px; font-weight: 800; letter-spacing: 1px; text-shadow: 0 1px 3px black;">PRICE 🔹 FUTURES CVD 🔸 SPOT CVD</div>
</div>
""", unsafe_allow_html=True)

if len(c_12_asc) == 12 and len(cvd_12) == 12 and len(scvd_12) == 12:
    x_axis = list(range(12))
    
    cum_cvd_chart, cum_scvd_chart = [], []
    curr_c, curr_s = 0, 0
    for i in range(12):
        curr_c += cvd_12[i]
        curr_s += scvd_12[i]
        cum_cvd_chart.append(curr_c)
        cum_scvd_chart.append(curr_s)
        
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.34, 0.33, 0.33])
    
    # 1. Price (Svíčky)
    fig.add_trace(go.Candlestick(x=x_axis,
                                 open=[float(c[1]) for c in c_12_asc],
                                 high=[float(c[2]) for c in c_12_asc],
                                 low=[float(c[3]) for c in c_12_asc],
                                 close=[float(c[4]) for c in c_12_asc],
                                 increasing_line_color='#3fb950', decreasing_line_color='#f85149',
                                 increasing_fillcolor='#3fb950', decreasing_fillcolor='#f85149',
                                 showlegend=False), row=1, col=1)
                                 
    # 2. Futures CVD (Modrá křivka)
    fig.add_trace(go.Scatter(x=x_axis, y=cum_cvd_chart, mode='lines', 
                             line=dict(color='#00f3ff', width=3, shape='spline', smoothing=1.1), showlegend=False), row=2, col=1)
                             
    # 3. Spot CVD (Žlutá křivka)
    fig.add_trace(go.Scatter(x=x_axis, y=cum_scvd_chart, mode='lines', 
                             line=dict(color='#f1e05a', width=3, shape='spline', smoothing=1.1), showlegend=False), row=3, col=1)

    def get_smart_range(arr):
        if not arr: return [0, 1]
        mn, mx = min(arr), max(arr)
        pd_val = (mx - mn) * 0.15
        if pd_val == 0: pd_val = 10
        return [mn - pd_val, mx + pd_val]

    p_rng = get_smart_range([float(c[3]) for c in c_12_asc] + [float(c[2]) for c in c_12_asc])
    c_rng = get_smart_range(cum_cvd_chart)
    s_rng = get_smart_range(cum_scvd_chart)

    fig.update_layout(
        height=550,
        margin=dict(l=0, r=0, t=25, b=0, pad=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, rangeslider=dict(visible=False), fixedrange=True),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=p_rng),
        xaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
        yaxis2=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=c_rng),
        xaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
        yaxis3=dict(showgrid=False, zeroline=False, showticklabels=False, fixedrange=True, range=s_rng)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# SETUP KARTY
st.markdown(f"""
<div class="setups-container">
<div class="alert-box {"signal-triggered" if trg1 else ""}">
<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">⚡ SETUP 1: ABSORPCE</div>
<div style="color: #e2e8f0; font-size: 14px; font-weight: 700;">{msg1}</div>
</div>
<div class="alert-box {"signal-triggered" if trg2 else ""}" style="margin-bottom: 0;">
<div style="color: #f7931a; font-weight: 900; font-size: 18px; margin-bottom: 5px;">🎯 SETUP 2: MACRO SFP</div>
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
<div style="font-size: 34px; font-weight: 900; color: {pnl_color if False else '#f1e05a'}; text-shadow: 0px 2px 10px rgba(0,0,0,0.9);">{win_rate:.2f} %</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

if st.button("🔄 AKTUALIZOVAT"): pass
if st.toggle("⏱️ Auto Refresh (20s)", value=False):
    time.sleep(20)
    st.rerun()
