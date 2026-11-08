import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import time
from datetime import datetime, timezone, timedelta

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
    margin-top: -60px !important;
}
iframe[height="0"] {display: none !important;}

/* OBŘÍ PULZUJÍCÍ 3D SRDCE PŘES CELÝ MOBILNÍ DISPLEJ */
@keyframes app-heart-pulse { 
    0% { background-size: 230% auto; } 
    50% { background-size: 260% auto; } 
    100% { background-size: 230% auto; } 
}
.stApp { 
    background-color: #040609; 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.35), rgba(4, 6, 9, 0.72)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_glowing_ruby_red_neon_heart.jpg');
    background-attachment: fixed;
    background-position: center 45%;
    background-repeat: no-repeat;
    animation: app-heart-pulse 3.5s infinite ease-in-out;
    color: #f0f6fc; 
}

/* MAXIMÁLNÍ ZLATÝ TITUL BTC ORDER FLOW */
.header-container { 
    display: flex; 
    flex-direction: column; 
    align-items: center; 
    justify-content: flex-start; 
    margin-top: 0px; 
    margin-bottom: 14px; 
    margin-left: -10px;
    margin-right: -10px;
    position: relative;
}

/* ZLATÁ FUTURISTICKÁ CENA POSUNUTÁ NAHORU NAD OBRÁZEK */
.cyber-price-box {
    margin-top: 5px;
    margin-bottom: -32px; /* Způsobí překryv s obrázkem pod ním */
    background: rgba(20, 12, 0, 0.85);
    border: 2px solid #f7931a;
    border-radius: 12px;
    padding: 2px 30px;
    box-shadow: 0 0 25px rgba(247, 147, 26, 0.8), inset 0 0 15px rgba(247, 147, 26, 0.4);
    backdrop-filter: blur(8px);
    z-index: 10;
}
.cyber-price-text {
    font-family: 'Orbitron', sans-serif;
    font-size: 42px;
    font-weight: 900;
    color: #ffdf00; /* Zlatá barva */
    letter-spacing: 4px;
    text-shadow: 0 0 15px #f7931a, 0 0 30px #ff0000;
    line-height: 1.1;
}

/* OBRÁZEK ZVĚTŠENÝ NA MASIVNÍ VÝŠKU */
.giant-btc-img { 
    width: 100vw; 
    max-width: 100%; 
    height: 380px; /* Zásadní zvětšení na výšku */
    object-fit: cover;
    object-position: center center;
    border-radius: 0 0 25px 25px; 
    box-shadow: 0 12px 35px rgba(247, 147, 26, 0.55); 
    display: block;
}

/* JEDINÝ VELKÝ OBDÉLNÍK OKX ORDER FLOW MATRIX S PADAJÍCÍMI DOLARY UVNITŘ */
.matrix-unified-top { 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.45), rgba(4, 6, 9, 0.78)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-position: center top;
    background-size: cover;
    border: 1px solid #2dd4bf; 
    border-bottom: none;
    border-radius: 16px 16px 0 0; 
    padding: 20px 15px 14px 15px; 
    text-align: center; 
    margin-bottom: 0px; 
    box-shadow: 0 -6px 30px rgba(0, 243, 255, 0.15); 
    position: relative;
    overflow: hidden;
}

.matrix-unified-bottom {
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.78), rgba(4, 6, 9, 0.90)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-position: center bottom;
    background-size: cover;
    border: 1px solid #2dd4bf;
    border-top: none;
    border-radius: 0 0 16px 16px;
    padding: 12px 15px 18px 15px;
    text-align: center;
    margin-top: -16px;
    margin-bottom: 16px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.8);
    position: relative;
    overflow: hidden;
}

/* PŘEPÍNAČE */
div[role="radiogroup"] { 
    background: rgba(7, 11, 19, 0.92); 
    border-left: 1px solid #2dd4bf; 
    border-right: 1px solid #2dd4bf; 
    padding: 6px 10px; 
    border-radius: 0px; 
    display: flex; 
    justify-content: space-around; 
    margin-top: -16px !important;
    margin-bottom: 0px !important;
}
div[role="radiogroup"] label { font-weight: 900 !important; color: #e2e8f0 !important; font-size: 14px !important; }

/* VÝSLEDKY S HROMADOU BANKOVEK */
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
    position: relative; 
    overflow: hidden; 
    border: 1px solid #1f7a43; 
}
.money-content { position: relative; z-index: 2; display: flex; justify-content: space-around; align-items: center; }

/* SETUP KARTY A TLAČÍTKA */
.alert-box { background: rgba(13, 19, 31, 0.85); border: 1px solid #1f2937; padding: 18px; border-radius: 15px; margin-top: 6px; margin-bottom: 16px; backdrop-filter: blur(10px); }
.signal-triggered { background-color: rgba(35, 12, 16, 0.95) !important; border: 2px solid #f85149 !important; animation: pulse-alert 1s infinite alternate; }
@keyframes pulse-alert { 0% { box-shadow: 0 0 10px rgba(248, 81, 73, 0.4); } 100% { box-shadow: 0 0 30px rgba(248, 81, 73, 0.9); } }

div.stButton > button { width: 100%; background: rgba(17, 24, 39, 0.85); color: #f0f6fc !important; border: 1px solid #374151 !important; border-radius: 10px; padding: 14px; font-size: 15px !important; font-weight: 900 !important; margin-bottom: 10px; backdrop-filter: blur(5px); }
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
        pnl_raw = str(row_summary.iloc[2]).replace(" ", "").replace(",", ".")
        total_pnl = float(pnl_raw) if pnl_raw not in ["nan", "0", "0.0"] else -41.03
        win_raw = str(row_summary.iloc[6]).replace("%", "").replace(" ", "").replace(",", ".")
        win_rate = float(win_raw) if win_raw not in ["nan", "0", "0.0"] else 38.10
        return total_pnl, win_rate
    except Exception:
        return -41.03, 38.10

def get_okx_candles(bar, limit, ts):
    urls = [
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://eea.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar={bar}&limit={limit}&t={ts}"
    ]
    for u in urls:
        try:
            data = requests.get(u, timeout=3).json().get("data", [])
            if data: return data
        except Exception:
            continue
    return []

def get_market_radar(btc_price, ts):
    ls_ratio = 50.0
    imb_vol, best_bid_p, best_bid_v, best_ask_p, best_ask_v = 0.0, 0.0, 0.0, 0.0, 0.0
    try:
        ls_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=5m&limit=1&t={ts}"
        ls_data = requests.get(ls_url, timeout=2).json().get("data", [])
        if ls_data:
            ratio_val = float(ls_data[0][1])
            ls_ratio = (ratio_val / (ratio_val + 1)) * 100
    except Exception:
        pass

    try:
        book_urls = [
            f"https://www.okx.com/api/v5/market/books?instId=BTC-USD_UM_XPERP-310404&sz=400&t={ts}",
            f"https://eea.okx.com/api/v5/market/books?instId=BTC-USD_UM_XPERP-310404&sz=400&t={ts}",
            f"https://www.okx.com/api/v5/market/books?instId=BTC-USD-SWAP&sz=400&t={ts}"
        ]
        book = {}
        for bu in book_urls:
            res = requests.get(bu, timeout=2).json().get("data", [])
            if res:
                book = res[0]
                break

        bids = book.get("bids", [])
        asks = book.get("asks", [])
        
        lower_bound = btc_price - 200
        upper_bound = btc_price + 200
        
        sum_bids = 0.0
        bid_blocks = {}
        for b in bids:
            p, v = float(b[0]), float(b[1])
            if p >= lower_bound:
                btc_vol = (v * 100) / p
                sum_bids += btc_vol
                block_10 = round(p / 10) * 10
                bid_blocks[block_10] = bid_blocks.get(block_10, 0) + btc_vol
                
        sum_asks = 0.0
        ask_blocks = {}
        for a in asks:
            p, v = float(a[0]), float(a[1])
            if p <= upper_bound:
                btc_vol = (v * 100) / p
                sum_asks += btc_vol
                block_10 = round(p / 10) * 10
                ask_blocks[block_10] = ask_blocks.get(block_10, 0) + btc_vol
                
        imb_vol = sum_bids - sum_asks
        
        if bid_blocks:
            best_bid_p = max(bid_blocks, key=bid_blocks.get)
            best_bid_v = bid_blocks[best_bid_p]
        if ask_blocks:
            best_ask_p = max(ask_blocks, key=ask_blocks.get)
            best_ask_v = ask_blocks[best_ask_p]
    except Exception:
        pass
        
    return ls_ratio, imb_vol, best_bid_p, best_bid_v, best_ask_p, best_ask_v

def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_5m, oi_change_5m = 0.0, 0.0
    cvd_series_12, oi_series_12 = [], []
    try:
        candles_300 = get_okx_candles("5m", 300, ts)
        btc_price = float(candles_300[0][4]) if candles_300 else 76000.0

        candles_1h = get_okx_candles("1H", 72, ts)

        vol_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&unit=1&t={ts}"
        vol_res = requests.get(vol_url, timeout=3).json().get("data", [])
        if len(vol_res) >= 12:
            for row in vol_res[:12][::-1]:
                delta_raw = float(row[2]) - float(row[1])
                cvd_series_12.append((delta_raw / btc_price) if (float(row[2]) + float(row[1])) > 50000 else delta_raw)
            cvd_5m = cvd_series_12[-1]

        oi_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&limit=13&t={ts}"
        oi_res = requests.get(oi_url, timeout=3).json().get("data", [])
        if len(oi_res) >= 13 and len(candles_300) >= 13:
            for i in range(12, 0, -1):
                p_curr = float(candles_300[i-1][4])
                p_prev = float(candles_300[i][4])
                oi_series_12.append((float(oi_res[i-1][1]) / p_curr) - (float(oi_res[i][1]) / p_prev))
            oi_change_5m = oi_series_12[-1]
        else:
            oi_series_12 = [0.0] * 12

        radar_data = get_market_radar(btc_price, ts)

        return cvd_5m, oi_change_5m, cvd_series_12, oi_series_12, candles_300, candles_1h, oi_res, btc_price, radar_data
    except Exception:
        return 0.0, 0.0, [], [], [], [], [], 76000.0, (50.0, 0.0, 0.0, 0.0, 0.0, 0.0)

def scan_setup_1(candles_300, cvd_series_12):
    try:
        if len(candles_300) < 12 or len(cvd_series_12) < 12: return "Načítám data...", False
        candles_12 = candles_300[:12][::-1]
        best_w = None
        for length in range(3, 13):
            sub_c = candles_12[-length:]
            b_highs = [max(float(k[1]), float(k[4])) for k in sub_c]
            b_lows = [min(float(k[1]), float(k[4])) for k in sub_c]
            if min(b_lows) == 0: continue
            r_pct = ((max(b_highs) - min(b_lows)) / min(b_lows)) * 100
            if r_pct <= 0.25:
                cum_cvd = sum(cvd_series_12[-length:])
                if best_w is None or abs(cum_cvd) > abs(best_w["cvd"]): best_w = {"len": length, "pct": r_pct, "cvd": cum_cvd}
        if best_w is None: return "Trh trenduje. Mimo 0,25% zámek.", False
        
        if abs(best_w["cvd"]) >= 200: 
            return f"🔥 SETUP 1 PLATNÝ! ({best_w['len']} svíček) CVD: {best_w['cvd']:+.1f} BTC.", True
        return f"Range aktivní ({best_w['len']} svíček). CVD: {best_w['cvd']:+.1f} BTC.", False
    except Exception: return "Načítám data...", False

def scan_setup_2(candles_300, candles_1h, oi_data, btc_price):
    try:
        if len(candles_300) < 5 or len(oi_data) < 4:
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

        for c in candles_300[3:]:
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

        c2 = candles_300[2]
        c1 = candles_300[1]
        c0 = candles_300[0]
        c2_high, c2_low = float(c2[2]), float(c2[3])
        c1_high, c1_low = float(c1[2]), float(c1[3])
        c0_high, c0_low = float(c0[2]), float(c0[3])

        oi_end_c1 = float(oi_data[1][1]) / float(candles_300[1][4])
        oi_start_c2 = float(oi_data[3][1]) / float(candles_300[3][4])
        oi_change = oi_end_c1 - oi_start_c2

        untouched_levels = []
        triggered_msg = None
        is_triggered = False

        for name, val, is_high, valid_from_hour in raw_levels:
            if val <= 0:
                continue

            already_swept_before_c2 = False
            for c in candles_300[3:]:
                dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
                if dt.date() != current_date:
                    continue
                if dt.hour >= valid_from_hour:
                    if is_high and float(c[2]) >= val:
                        already_swept_before_c2 = True
                        break
                    if not is_high and float(c[3]) <= val:
                        already_swept_before_c2 = True
                        break

            if already_swept_before_c2:
                continue

            dt_c2 = datetime.fromtimestamp(int(c2[0]) / 1000, tz_offset)
            if dt_c2.date() == current_date and dt_c2.hour >= valid_from_hour:
                if is_high and c2_high >= val:
                    if oi_change <= -50:
                        triggered_msg = f"🔥 BEARISH SFP! {name} ({val:.0f}) poprvé vybráno! OI výplach {oi_change:.1f} BTC."
                        is_triggered = True
                    else:
                        triggered_msg = f"👀 {name} ({val:.0f}) poprvé dotknuto. OI: {oi_change:.1f} BTC."
                    continue
                elif not is_high and c2_low <= val:
                    if oi_change <= -50:
                        triggered_msg = f"🔥 BULLISH SFP! {name} ({val:.0f}) poprvé vybráno! OI výplach {oi_change:.1f} BTC."
                        is_triggered = True
                    else:
                        triggered_msg = f"👀 {name} ({val:.0f}) poprvé dotknuto. OI: {oi_change:.1f} BTC."
                    continue

            dt_c1 = datetime.fromtimestamp(int(c1[0]) / 1000, tz_offset)
            if dt_c1.date() == current_date and dt_c1.hour >= valid_from_hour:
                if (is_high and (c1_high >= val or c0_high >= val)) or (not is_high and (c1_low <= val or c0_low <= val)):
                    continue

            untouched_levels.append(f"{name}: {val:.0f}")

        levels_str = " ⚡ ".join(untouched_levels) if untouched_levels else "Všechny aktivní levely už byly vybrány"
        final_msg = triggered_msg if triggered_msg else "Čekám na první protnutí Macro Levelu..."

        return final_msg, is_triggered, levels_str
    except Exception:
        return "Načítám levely...", False, ""

total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, cvd_12, oi_12, c_300, c_1h, oi_res, b_price, radar = fetch_okx_data()
ls_ratio, imb_vol, bid_p, bid_v, ask_p, ask_v = radar

msg1, trg1 = scan_setup_1(c_300, cvd_12)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, oi_res, b_price)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

cvd_color = '#3fb950' if okx_cvd >= 0 else '#f85149'
oi_color = '#3fb950' if okx_oi_chg >= 0 else '#f85149'
imb_color = '#3fb950' if imb_vol >= 0 else '#f85149'
imb_text = 'PŘEVAHA KUPCŮ' if imb_vol >= 0 else 'PŘEVAHA PRODEJCŮ'

# 1. HLAVNÍ 3D TITUL BTC CO NEJVÍC NAHOŘE A MAXIMÁLNĚ VELKÝ + ZLATÁ CENA NAHOŘE
st.markdown(f"""
<div class="header-container">
<div class="cyber-price-box">
<div class="cyber-price-text">{b_price:.0f}</div>
</div>
<img src="https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_luxurious_glowing_golden_Bi%20(1).jpg" class="giant-btc-img">
</div>
""", unsafe_allow_html=True)

# 2. HORNÍ ČÁST JEDNOTNÉHO OBDÉLNÍKU: OKX ORDER FLOW MATRIX + LIQUIDITY RADAR (BEZ ODSAZENÍ)
st.markdown(f"""
<div class="matrix-unified-top">
<div style="color: #ffffff; font-weight: 900; font-size: 19px; margin-bottom: 18px; letter-spacing: 2px; text-shadow: 0px 2px 8px rgba(0,0,0,1);">OKX ORDER FLOW MATRIX</div>
<div style="display: flex; justify-content: space-around; align-items: center; margin-bottom: 18px;">
<div style="text-align: center;">
<div style="color: #e2e8f0; font-size: 13px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">5M CVD</div>
<div style="font-size: 38px; font-weight: 900; color: {cvd_color}; text-shadow: 0px 2px 10px rgba(0,0,0,1);">{okx_cvd:+,.1f}</div>
</div>
<div style="text-align: center;">
<div style="color: #e2e8f0; font-size: 13px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">5M OI</div>
<div style="font-size: 38px; font-weight: 900; color: {oi_color}; text-shadow: 0px 2px 10px rgba(0,0,0,1);">{okx_oi_chg:+,.1f}</div>
</div>
</div>
<div style="border-top: 1px solid rgba(255,255,255,0.2); padding-top: 14px; margin-top: 10px;">
<div style="color: #00f3ff; font-size: 12px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">LIQUIDITY & RETAIL RADAR (± 200 USD | 10$ BLOKY)</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 14px;">
<span style="font-weight: 800; color: #e2e8f0;">L/S Účty:</span>
<span><strong style="color: #3fb950;">{ls_ratio:.0f}% LONG</strong> <span style="color: #6e7681;">|</span> <strong style="color: #f85149;">{100 - ls_ratio:.0f}% SHORT</strong></span>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 14px;">
<span style="font-weight: 800; color: #e2e8f0;">Pasivní Tlak (±200$):</span>
<span style="font-weight: 900; color: {imb_color};">{imb_vol:+,.1f} BTC ({imb_text})</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 13px; background: rgba(4, 6, 9, 0.65); padding: 8px 12px; border-radius: 8px;">
<div style="text-align: left;"><span style="color: #f85149; font-weight: 900;">🔴 Ask Zeď:</span> <strong>{ask_v:.1f} BTC</strong> na {ask_p:.0f}</div>
<div style="text-align: right;"><span style="color: #3fb950; font-weight: 900;">🟢 Bid Zeď:</span> <strong>{bid_v:.1f} BTC</strong> na {bid_p:.0f}</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# 3. STŘEDNÍ PŘEPÍNAČ HISTORIE (INTEGROVANÝ PŘÍMO DO MATRIX OBDÉLNÍKU)
tf = st.radio("Historie matice", ["15m", "30m", "45m", "60m"], horizontal=True, label_visibility="collapsed")
if tf == "15m": n = 3
elif tf == "30m": n = 6
elif tf == "45m": n = 9
else: n = 12

sub_cvd = cvd_12[-n:] if len(cvd_12) >= n else cvd_12
sub_oi = oi_12[-n:] if len(oi_12) >= n else oi_12
sum_cvd = sum(sub_cvd)
sum_oi = sum(sub_oi)
cvd_str = " | ".join([f"{x:+.1f}" for x in sub_cvd])
oi_str = " | ".join([f"{x:+.1f}" for x in sub_oi])

# 4. SPODNÍ ČÁST JEDNOTNÉHO OBDÉLNÍKU: HISTORIE ZA 15m/30m/45m/60m
st.markdown(f"""
<div class="matrix-unified-bottom">
<div style="color: #00f3ff; font-size: 12px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 1px;">DATA ZA POSLEDNÍCH {tf.upper()}</div>
<div style="font-size: 16px; font-weight: 900; color: {'#3fb950' if sum_cvd >= 0 else '#f85149'}; margin-bottom: 3px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">KUMULATIVNÍ CVD: {sum_cvd:+.1f} BTC</div>
<div style="font-size: 13px; font-weight: 700; color: #e2e8f0; word-wrap: break-word; line-height: 1.5; margin-bottom: 10px;">{cvd_str}</div>
<div style="font-size: 16px; font-weight: 900; color: {'#3fb950' if sum_oi >= 0 else '#f85149'}; margin-bottom: 3px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">KUMULATIVNÍ OI: {sum_oi:+.1f} BTC</div>
<div style="font-size: 13px; font-weight: 700; color: #e2e8f0; word-wrap: break-word; line-height: 1.5;">{oi_str}</div>
</div>
""", unsafe_allow_html=True)

# 5. PŘEPÍNAČ SETUPŮ 1 A 2
s_mode = st.radio("Mód:", ["⚡ Setup 1", "🎯 Setup 2"], horizontal=True, label_visibility="collapsed")
if "Setup 1" in s_mode:
    st.markdown(f"""
<div class="alert-box {"signal-triggered" if trg1 else ""}">
<div style="color: #f7931a; font-weight: 900; font-size: 18px;">⚡ SETUP 1: ABSORPCE</div>
<div style="color: #e2e8f0; font-size: 15px; margin-top: 5px; font-weight: 700;">{msg1}</div>
</div>
""", unsafe_allow_html=True)
else:
    st.markdown(f"""
<div class="alert-box {"signal-triggered" if trg2 else ""}">
<div style="color: #a371f7; font-weight: 900; font-size: 18px;">🎯 SETUP 2: MACRO SFP (PRVNÍ DOTEK)</div>
<div style="color: #e2e8f0; font-size: 15px; margin-top: 5px; font-weight: 700;">{msg2}</div>
<div style="color: #00f3ff; font-size: 13px; margin-top: 10px; font-weight: 800;">Zbývající aktivní levely: {l_str}</div>
</div>
""", unsafe_allow_html=True)

# 6. PNL & WIN RATE
pnl_color = '#3fb950' if total_pnl >= 0 else '#f85149'
pnl_sign = '+$' if total_pnl >= 0 else '-$'

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
