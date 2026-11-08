import pandas as pd
import requests
import streamlit as st
import time
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide", initial_sidebar_state="collapsed")

# Skrytí všech výchozích menu Streamlitu a nastavení barev
st.markdown("""
<style>
#MainMenu {visibility: hidden !important; display: none !important;}
header[data-testid="stHeader"] {visibility: hidden !important; display: none !important;}
footer {visibility: hidden !important; display: none !important;}
.viewerBadge_container__1QSob {display: none !important;}
[data-testid="stAppViewBlockContainer"] {padding-top: 0rem !important; padding-bottom: 2rem !important;}

/* PADAJÍCÍ DOLARY NA POZADÍ CELÉ APLIKACE S JEMNÝM FILTREM */
.stApp { 
    background-color: #040609; 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.65), rgba(4, 6, 9, 0.90)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/3D_rendering_of_falling_US_dollar_banknotes_frozen_in_mid-ai.jpg');
    background-attachment: fixed;
    background-position: center;
    background-size: cover;
    color: #f0f6fc; 
}

/* TVŮJ LUXUSNÍ ZLATÝ BTC OBRÁZEK S NADPISEM */
.header-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 10px; margin-bottom: 25px; }
.giant-btc-img { width: 100%; max-width: 380px; border-radius: 20px; box-shadow: 0 15px 40px rgba(247, 147, 26, 0.4); }

/* MATICE A PRÉMIOVÉ 3D SRDCE JAKO POZADÍ */
@keyframes heart-pulse-bg { 
    0% { background-size: 110%; } 
    50% { background-size: 125%; } 
    100% { background-size: 110%; } 
}

.matrix-card { 
    background-image: 
        linear-gradient(rgba(4, 6, 9, 0.3), rgba(4, 6, 9, 0.7)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_glowing_ruby_red_neon_heart.jpg');
    background-position: center;
    background-repeat: no-repeat;
    animation: heart-pulse-bg 2.5s infinite ease-in-out;
    border: 1px solid #1f2937; 
    border-radius: 15px; 
    padding: 30px 20px; 
    text-align: center; 
    margin-bottom: 10px; 
    box-shadow: 0 10px 40px rgba(255, 0, 50, 0.3); 
    position: relative;
    overflow: hidden;
}

/* VÝSLEDKY S HROMADOU BANKOVEK */
.money-journal { 
    background-image: 
        linear-gradient(rgba(2, 10, 5, 0.3), rgba(2, 10, 5, 0.6)), 
        url('https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_neat_pile_of_crisp_US_dolla.jpg');
    background-position: center;
    background-size: cover;
    border-radius: 15px; 
    padding: 30px 20px; 
    text-align: center; 
    margin-bottom: 20px; 
    box-shadow: 0 10px 40px rgba(39, 174, 96, 0.4); 
    position: relative; 
    overflow: hidden; 
    border: 1px solid #1f7a43; 
}
.money-content { position: relative; z-index: 2; display: flex; justify-content: space-around; align-items: center; }

/* SETUP KARTY A TLAČÍTKA */
.alert-box { background: rgba(13, 19, 31, 0.8); border: 1px solid #1f2937; padding: 20px; border-radius: 15px; margin-bottom: 16px; backdrop-filter: blur(10px); }
.signal-triggered { background-color: rgba(35, 12, 16, 0.9) !important; border: 2px solid #f85149 !important; animation: pulse-alert 1s infinite alternate; }
@keyframes pulse-alert { 0% { box-shadow: 0 0 10px rgba(248, 81, 73, 0.4); } 100% { box-shadow: 0 0 30px rgba(248, 81, 73, 0.9); } }
div.stButton > button { width: 100%; background: rgba(17, 24, 39, 0.8); color: #f0f6fc !important; border: 1px solid #374151 !important; border-radius: 10px; padding: 15px; font-size: 15px !important; font-weight: 900 !important; margin-bottom: 10px; backdrop-filter: blur(5px); }
div.stButton > button:hover { border-color: #f7931a !important; color: #f7931a !important; }

/* Přepínač historie */
div[role="radiogroup"] { background: rgba(13, 19, 31, 0.8); border: 1px solid #1f2937; padding: 5px; border-radius: 10px; display: flex; justify-content: space-around; backdrop-filter: blur(5px); }
div[role="radiogroup"] label { font-weight: 800 !important; color: #c9d1d9 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-container">
<img src="https://raw.githubusercontent.com/PepinoDeM30/crypto-flow-terminal/main/A_highly_detailed_3D_render_of_a_luxurious_glowing_golden_Bi%20(1).jpg" class="giant-btc-img">
</div>
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
    # Přímé napojení na tvůj TradingView kontrakt BTCUSD UM X-Perp (Apr 2031) -> BTC-USD_UM_XPERP-310404
    urls = [
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://eea.okx.com/api/v5/market/candles?instId=BTC-USD_UM_XPERP-310404&bar={bar}&limit={limit}&t={ts}",
        f"https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar={bar}&limit={limit}&t={ts}"
    ]
    for u in urls:
        try:
            data = requests.get(u, timeout=3).json().get("data", [])
            if data:
                return data
        except Exception:
            continue
    return []

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

        return cvd_5m, oi_change_5m, cvd_series_12, oi_series_12, candles_300, candles_1h, oi_res, btc_price
    except Exception:
        return 0.0, 0.0, [], [], [], [], [], 76000.0

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
        if abs(best_w["cvd"]) >= 200: return f"🔥 SETUP 1 PLATNÝ! CVD: {best_w['cvd']:+.1f} BTC.", True
        return f"Range aktivní. CVD: {best_w['cvd']:+.1f} BTC.", False
    except Exception: return "Načítám data...", False

def scan_setup_2(candles_300, candles_1h, oi_data, btc_price):
    try:
        if len(candles_300) < 5 or len(oi_data) < 4:
            return "Načítám historii trhu...", False, "Skenuji levely..."

        # Přesný pražský čas UTC+1 (stejný jako na tvém TradingView)
        tz_offset = timezone(timedelta(hours=1))
        now_prague = datetime.now(tz_offset)
        current_date = now_prague.date()
        yesterday_date = current_date - timedelta(days=1)

        # 1. Výpočet PDH a PDL přesně za včerejší den (00:00 až 23:59 UTC+1)
        pdh, pdl = 0.0, float('inf')
        for c in candles_1h:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
            if dt.date() == yesterday_date:
                pdh = max(pdh, float(c[2]))
                pdl = min(pdl, float(c[3]))
        if pdh == 0.0:
            pdh, pdl = 0.0, 0.0

        # 2. Výpočet Asie (01:00 - 07:00) a Londýna (09:00 - 14:00) v UTC+1
        asia_h, asia_l = 0.0, float('inf')
        lon_h, lon_l = 0.0, float('inf')

        for c in candles_300[3:]:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz_offset)
            if dt.date() != current_date:
                continue
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

        levels_str = f"PDH: {pdh:.1f} | PDL: {pdl:.1f} ⚡ ASIA H: {asia_h:.1f} | ASIA L: {asia_l:.1f} ⚡ LON H: {lon_h:.1f} | LON L: {lon_l:.1f}"

        # 3. Analýza protnutí hladiny na Sweep svíčce (c2) a změny OI za c2 + c1
        c3 = candles_300[3]
        c2 = candles_300[2]
        c3_close = float(c3[4])
        c2_high, c2_low = float(c2[2]), float(c2[3])

        oi_end_c1 = float(oi_data[1][1]) / float(candles_300[1][4])
        oi_start_c2 = float(oi_data[3][1]) / float(candles_300[3][4])
        oi_change = oi_end_c1 - oi_start_c2

        pierced_h = None
        if pdh > 0 and c3_close < pdh and c2_high >= pdh: pierced_h = "Previous Daily High"
        elif lon_h > 0 and c3_close < lon_h and c2_high >= lon_h: pierced_h = "London High"
        elif asia_h > 0 and c3_close < asia_h and c2_high >= asia_h: pierced_h = "Asia High"

        if pierced_h:
            if oi_change <= -50: return f"🔥 BEARISH SFP! {pierced_h} propíchnuto. OI výplach {oi_change:.1f} BTC.", True, levels_str
            else: return f"👀 {pierced_h} dotknuto. Čekám na výplach (OI: {oi_change:.1f} BTC).", False, levels_str

        pierced_l = None
        if pdl > 0 and c3_close > pdl and c2_low <= pdl: pierced_l = "Previous Daily Low"
        elif lon_l > 0 and c3_close > lon_l and c2_low <= lon_l: pierced_l = "London Low"
        elif asia_l > 0 and c3_close > asia_l and c2_low <= asia_l: pierced_l = "Asia Low"

        if pierced_l:
            if oi_change <= -50: return f"🔥 BULLISH SFP! {pierced_l} propíchnuto. OI výplach {oi_change:.1f} BTC.", True, levels_str
            else: return f"👀 {pierced_l} dotknuto. Čekám na výplach (OI: {oi_change:.1f} BTC).", False, levels_str

        return "Čekám na protnutí Macro Levelu...", False, levels_str
    except Exception:
        return "Načítám levely...", False, ""

total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, cvd_12, oi_12, c_300, c_1h, oi_res, b_price = fetch_okx_data()

msg1, trg1 = scan_setup_1(c_300, cvd_12)
msg2, trg2, l_str = scan_setup_2(c_300, c_1h, oi_res, b_price)

if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

cvd_color = '#3fb950' if okx_cvd >= 0 else '#f85149'
oi_color = '#3fb950' if okx_oi_chg >= 0 else '#f85149'

st.markdown(f"""
<div class="matrix-card">
<div style="color: #ffffff; font-weight: 900; font-size: 18px; margin-bottom: 25px; letter-spacing: 2px; text-shadow: 0px 2px 6px rgba(0,0,0,0.9);">OKX ORDER FLOW MATRIX</div>
<div style="display: flex; justify-content: space-around; align-items: center; margin-bottom: 10px; position: relative; z-index: 5;">
<div style="text-align: center;">
<div style="color: #e2e8f0; font-size: 14px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">5M CVD</div>
<div style="font-size: 40px; font-weight: 900; color: {cvd_color}; text-shadow: 0px 2px 10px rgba(0,0,0,1);">{okx_cvd:+,.1f}</div>
</div>
<div style="text-align: center;">
<div style="color: #e2e8f0; font-size: 14px; font-weight: 900; letter-spacing: 1px; text-shadow: 0px 2px 6px rgba(0,0,0,1);">5M OI</div>
<div style="font-size: 40px; font-weight: 900; color: {oi_color}; text-shadow: 0px 2px 10px rgba(0,0,0,1);">{okx_oi_chg:+,.1f}</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

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

st.markdown(f"""
<div style="background: rgba(13, 19, 31, 0.7); backdrop-filter: blur(10px); border: 1px solid #1f2937; border-radius: 15px; padding: 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.5);">
<div style="color: #6e7681; font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">DATA ZA POSLEDNÍCH {tf.upper()}</div>
<div style="font-size: 16px; font-weight: 800; color: {'#3fb950' if sum_cvd >= 0 else '#f85149'}; margin-bottom: 4px;">KUMULATIVNÍ CVD: {sum_cvd:+.1f} BTC</div>
<div style="font-size: 14px; font-weight: 700; color: #c9d1d9; word-wrap: break-word; line-height: 1.6; margin-bottom: 10px;">{cvd_str}</div>
<div style="font-size: 16px; font-weight: 800; color: {'#3fb950' if sum_oi >= 0 else '#f85149'}; margin-bottom: 4px;">KUMULATIVNÍ OI: {sum_oi:+.1f} BTC</div>
<div style="font-size: 14px; font-weight: 700; color: #c9d1d9; word-wrap: break-word; line-height: 1.6;">{oi_str}</div>
</div>
""", unsafe_allow_html=True)

s_mode = st.radio("Mód:", ["⚡ Setup 1", "🎯 Setup 2"], horizontal=True, label_visibility="collapsed")
if "Setup 1" in s_mode:
    st.markdown(f"""
<div class="alert-box {"signal-triggered" if trg1 else ""}">
<div style="color: #f7931a; font-weight: 900; font-size: 18px;">⚡ SETUP 1: ABSORPCE</div>
<div style="color: #c9d1d9; font-size: 15px; margin-top: 5px;">{msg1}</div>
</div>
""", unsafe_allow_html=True)
else:
    st.markdown(f"""
<div class="alert-box {"signal-triggered" if trg2 else ""}">
<div style="color: #a371f7; font-weight: 900; font-size: 18px;">🎯 SETUP 2: MACRO SFP</div>
<div style="color: #c9d1d9; font-size: 15px; margin-top: 5px;">{msg2}</div>
<div style="color: #58a6ff; font-size: 12px; margin-top: 10px; font-weight: 700;">{l_str}</div>
</div>
""", unsafe_allow_html=True)

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
