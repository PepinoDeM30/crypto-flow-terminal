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
    margin-top: -65px !important;
}
iframe[height="0"] {display: none !important;}

/* OBŘÍ PULZUJÍCÍ 3D SRDCE */
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

/* ZLATÝ BTC BANNER */
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

/* ŽIVÁ CENA UPROSTŘED DOMU */
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

/* OKX MATRIX (ZÁKLADNÍ BLOK S PADÁKEM) */
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

/* SPOLEČNÝ BLOK PRO SETUPY 1 a 2 S BANKOVKAMI */
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

/* SETUP KARTY */
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

/* VÝSLEDKY PNL */
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
    """Zjistí přesnou velikost kontraktu (ctVal a měnu) přímo z OKX, aby nedocházelo k zkreslení."""
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
        f"https://eea.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDC-SWAP&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar={bar}&limit={limit}&t={ts}"
    ]
    for u in urls:
        try:
            data = requests.get(u, timeout=4).json().get("data", [])
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
        # Prioritně bereme books-full (až 5000 úrovní), aby 3. pásmo nikdy nevyschlo
        endpoints = [
            ("https://eea.okx.com/api/v5/market/books-full?instId=BTC-USD_UM_XPERP-310404&sz=5000", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books-full?instId=BTC-USD_UM_XPERP-310404&sz=5000", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books-full?instId=BTC-USDC-SWAP&sz=5000", "BTC-USDC-SWAP"),
            ("https://eea.okx.com/api/v5/market/books?instId=BTC-USD_UM_XPERP-310404&sz=400", "BTC-USD_UM_XPERP-310404"),
            ("https://www.okx.com/api/v5/market/books?instId=BTC-USDC-SWAP&sz=400", "BTC-USDC-SWAP"),
            ("https://www.okx.com/api/v5/market/books-full?instId=BTC-USD-SWAP&sz=5000", "BTC-USD-SWAP")
        ]
        book = {}
        active_inst = "BTC-USD_UM_XPERP-310404"
        for bu, inst_name in endpoints:
            try:
                res = requests.get(bu, timeout=4).json().get("data", [])
                if res and (res[0].get("asks") or res[0].get("bids")):
                    book = res[0]
                    active_inst = inst_name
                    break
            except Exception:
                continue

        ct_val, ct_ccy = get_contract_spec(active_inst)
        asks = book.get("asks", [])
        bids = book.get("bids", [])
        
        sum_bids, sum_asks = 0.0, 0.0
        
        # 3 čistá pásma po 100 USD (0-100, 100-200, 200-300) + celkový součet do 400 USD
        for a in asks:
            p, v = float(a[0]), float(a[1])
            dist = p - btc_price
            if 0 <= dist <= 400:
                vol = to_btc_vol(v, p, ct_val, ct_ccy)
                sum_asks += vol
                if dist <= 100: ask_v1 += vol
                elif dist <= 200: ask_v2 += vol
                elif dist <= 300: ask_v3 += vol
                
        for b in bids:
            p, v = float(b[0]), float(b[1])
            dist = btc_price - p
            if 0 <= dist <= 400:
                vol = to_btc_vol(v, p, ct_val, ct_ccy)
                sum_bids += vol
                if dist <= 100: bid_v1 += vol
                elif dist <= 200: bid_v2 += vol
                elif dist <= 300: bid_v3 += vol
                
        imb_vol = sum_bids - sum_asks
    except Exception:
        pass
        
    return imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3

def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_series_12, spot_cvd_series_12, oi_series_12 = [], [], []
    try:
        candles_300 = get_okx_candles("5m", 300, ts)
        btc_price = float(candles_300[0][4]) if candles_300 else 76000.0
        candles_1h = get_okx_candles("1H", 72, ts)

        # Mapa uzavřených cen podle timestampu svíčky (odstranění falešného přepočtu živou cenou)
        candle_close_map = {int(c[0]): float(c[4]) for c in candles_300}

        # 1. FUTURES CVD (5m uzavřené svíčky, unit=1 je přímo v BTC)
        vol_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&unit=1&t={ts}"
        vol_res = requests.get(vol_url, timeout=5).json().get("data", [])
        if len(vol_res) >= 12:
            for row in vol_res[:12][::-1]:
                cvd_series_12.append(float(row[2]) - float(row[1]))

        # 2. SPOT CVD (5m uzavřené svíčky, unit=1 je přímo v BTC)
        spot_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SPOT&period=5m&unit=1&t={ts}"
        spot_res = requests.get(spot_url, timeout=5).json().get("data", [])
        if len(spot_res) >= 12:
            for row in spot_res[:12][::-1]:
                spot_cvd_series_12.append(float(row[2]) - float(row[1]))

        # 3. OPEN INTEREST (5m uzavřené svíčky spárované s uzavřenou cenou dané svíčky)
        oi_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&limit=13&t={ts}"
        oi_res = requests.get(oi_url, timeout=5).json().get("data", [])
        if len(oi_res) >= 13 and len(candles_300) >= 14:
            for i in range(12, 0, -1):
                ts_curr = int(oi_res[i-1][0])
                ts_prev = int(oi_res[i][0])
                # Použijeme přesnou uzavírací cenu svíčky se stejným timestampem (ne živou cenu!)
                p_curr = candle_close_map.get(ts_curr, float(candles_300[i][4]))
                p_prev = candle_close_map.get(ts_prev, float(candles_300[i+1][4]))
                oi_series_12.append((float(oi_res[i-1][1]) / p_curr) - (float(oi_res[i][1]) / p_prev))
        else:
            oi_series_12 = [0.0] * 12

        radar_data = get_market_radar(btc_price, ts)
        
        cvd_1 = sum(cvd_series_12[-1:]) if len(cvd_series_12) >= 1 else 0.0
        cvd_5 = sum(cvd_series_12[-5:]) if len(cvd_series_12) >= 5 else 0.0
        cvd_9 = sum(cvd_series_12[-9:]) if len(cvd_series_12) >= 9 else 0.0

        scvd_1 = sum(spot_cvd_series_12[-1:]) if len(spot_cvd_series_12) >= 1 else 0.0
        scvd_5 = sum(spot_cvd_series_12[-5:]) if len(spot_cvd_series_12) >= 5 else 0.0
        scvd_9 = sum(spot_cvd_series_12[-9:]) if len(spot_cvd_series_12) >= 9 else 0.0
        
        oi_1 = sum(oi_series_12[-1:]) if len(oi_series_12) >= 1 else 0.0
        oi_5 = sum(oi_series_12[-5:]) if len(oi_series_12) >= 5 else 0.0
        oi_9 = sum(oi_series_12[-9:]) if len(oi_series_12) >= 9 else 0.0

        return cvd_1, cvd_5, cvd_9, scvd_1, scvd_5, scvd_9, oi_1, oi_5, oi_9, cvd_series_12, candles_300, candles_1h, oi_res, btc_price, radar_data
    except Exception:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [], [], [], [], 76000.0, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

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
            return f"🔥 SETUP 1 PLATNÝ! ({best_w['len']} svíček | {best_w['pct']:.2f}%) CVD: {best_w['cvd']:+.1f} BTC.", True
        return f"Range aktivní ({best_w['len']} svíček | {best_w['pct']:.2f}%). CVD: {best_w['cvd']:+.1f} BTC.", False
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
cvd1, cvd5, cvd9, scvd1, scvd5, scvd9, oi1, oi5, oi9, cvd_12, c_300, c_1h, oi_res, b_price, radar = fetch_okx_data()
imb_vol, ask_v1, ask_v2, ask_v3, bid_v1, bid_v2, bid_v3 = radar

msg1, trg1 = scan_setup_1(c_300, cvd_12)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, oi_res, b_price)

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

st.markdown(f"""
<div class="gold-btc-banner"></div>
""", unsafe_allow_html=True)

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
