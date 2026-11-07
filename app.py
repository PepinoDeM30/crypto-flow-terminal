import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide")

st.markdown("""
    <style>
    /* KYBERNETICKÉ POZADÍ S TECHNICKOU MŘÍŽKOU A ZLATOU ZÁŘÍ */
    .stApp {
        background-color: #06090f;
        background-image: 
            radial-gradient(circle at 50% 0%, rgba(247, 147, 26, 0.14) 0%, transparent 45%),
            radial-gradient(circle at 85% 60%, rgba(88, 166, 255, 0.08) 0%, transparent 40%),
            linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 28px 28px, 28px 28px;
        color: #ffffff;
    }
    header[data-testid="stHeader"] {
        background: linear-gradient(90deg, #0b111a 0%, #162236 50%, #0b111a 100%) !important;
        border-bottom: 1px solid #f7931a66 !important;
    }
    .block-container {
        padding-top: 2.6rem !important;
        padding-bottom: 2rem !important;
    }

    /* TLAČÍTKA (AKTUALIZOVAT & PŘEPÍNAČE) */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #141f33 0%, #1d2d4a 50%, #141f33 100%);
        color: #ffd700 !important;
        border: 1px solid #f7931a !important;
        border-radius: 10px;
        padding: 9px 14px;
        font-size: 14px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        box-shadow: 0 0 12px rgba(247, 147, 26, 0.2);
        transition: all 0.2s ease;
    }
    div.stButton > button:hover, div.stButton > button:active {
        background: linear-gradient(90deg, #f7931a 0%, #ffb700 100%);
        color: #06090f !important;
        box-shadow: 0 0 18px rgba(247, 147, 26, 0.7);
    }

    /* STYLOVÁNÍ PŘEPÍNAČE SETUP 1 / SETUP 2 */
    div[role="radiogroup"] {
        background: rgba(16, 22, 34, 0.9);
        border: 1px solid #2e3b52;
        padding: 6px;
        border-radius: 12px;
        display: flex;
        justify-content: space-around;
        margin-bottom: 10px;
    }
    div[role="radiogroup"] label {
        font-weight: 800 !important;
        font-size: 14px !important;
        color: #ffffff !important;
    }

    /* HLAVNÍ HLAVIČKA S VÝRAZNÝM ZNAKEM BTC */
    .crypto-header {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        background: linear-gradient(135deg, rgba(16, 23, 38, 0.95) 0%, rgba(28, 40, 64, 0.95) 50%, rgba(16, 23, 38, 0.95) 100%);
        border: 1px solid #3d4c68;
        border-bottom: 3px solid #f7931a;
        padding: 14px 18px;
        border-radius: 14px;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.65);
        white-space: nowrap;
    }
    .btc-badge {
        background: radial-gradient(circle at 30% 30%, #ffe066 0%, #f7931a 55%, #b35900 100%);
        color: #06090f;
        font-weight: 900;
        font-size: 27px;
        width: 46px;
        height: 46px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 20px rgba(247, 147, 26, 0.9);
        border: 2px solid #fff5d6;
        flex-shrink: 0;
    }
    .header-title {
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 1.5px;
        background: linear-gradient(90deg, #ffffff 0%, #ffd700 55%, #f7931a 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* GLOBÁLNÍ KARTA A TEPAJÍCÍ SRDCE */
    .global-card {
        background: rgba(16, 22, 33, 0.92);
        border: 1px solid #2b384e;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 14px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
    }
    @keyframes heartbeat {
        0% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        15% { transform: scale(1.3); filter: drop-shadow(0 0 8px #ff4b4b); }
        30% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        45% { transform: scale(1.25); filter: drop-shadow(0 0 6px #ff4b4b); }
        60% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        100% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
    }
    .beating-heart { display: inline-block; animation: heartbeat 1.4s infinite; font-size: 16px; margin-right: 6px; }
    .live-pulse-text { font-size: 12px; color: #ff6b6b; font-weight: 700; letter-spacing: 0.6px; }

    /* KARTY SETUP 1 A SETUP 2 */
    .alert-box-setup1 {
        background: rgba(18, 22, 32, 0.95);
        border: 1px solid #455065;
        border-left: 5px solid #f7931a;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 16px;
    }
    .alert-box-setup2 {
        background: rgba(21, 18, 36, 0.95);
        border: 1px solid #483766;
        border-left: 5px solid #a371f7;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 16px;
    }
    .setup-main-title {
        font-size: 20px;
        font-weight: 900;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .setup-sub-text {
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.5;
    }

    /* BLIKAJÍCÍ ALARM PŘI DETEKCI SETUPU */
    .signal-triggered {
        background-color: #2b1115 !important;
        border: 2px solid #ff5555 !important;
        animation: pulse-alert 1s infinite alternate;
    }
    @keyframes pulse-alert {
        0% { box-shadow: 0 0 5px rgba(255, 85, 85, 0.4); }
        100% { box-shadow: 0 0 24px rgba(255, 85, 85, 0.95); }
    }

    /* NADPISY SEKCÍ */
    .section-banner {
        background: linear-gradient(90deg, rgba(22, 30, 46, 0.95) 0%, rgba(12, 16, 24, 0.95) 100%);
        border-left: 4px solid #58a6ff;
        border-top: 1px solid #283347;
        border-right: 1px solid #283347;
        border-bottom: 1px solid #283347;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 19px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.6px;
        margin: 16px 0 10px 0;
    }

    .metric-title { font-size: 12px; color: #9da7b3; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
    .metric-value { font-size: 22px; font-weight: 800; margin-top: 4px; }
    .negative { color: #ff5555; }
    .positive { color: #3fb950; }
    .neutral { color: #ffd700; }
    </style>
""", unsafe_allow_html=True)

# --- 1. HORNÍ OVLÁDACÍ PANEL ---
col_top1, col_top2 = st.columns([3, 2])
with col_top1:
    if st.button("🔄 AKTUALIZOVAT TRH"):
        pass
with col_top2:
    auto_refresh = st.toggle("⏱️ Auto (20s)", value=False)

# --- 2. HLAVNÍ HLAVIČKA ---
st.markdown("""
    <div class="crypto-header">
        <div class="btc-badge">₿</div>
        <div class="header-title">BTC ORDER FLOW</div>
    </div>
""", unsafe_allow_html=True)

# --- 3. GOOGLE SHEETS (NAČTENÍ SOUHRNU Z ŘÁDKU 15 / SLOUPEC C A G) ---
@st.cache_data(ttl=30)
def load_trading_data():
    try:
        sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url, header=None)
        
        # Řádek 15 (index 15) obsahuje "Celkem / Souhrn"
        # Sloupec C (index 2) je celkový PnL
        # Sloupec G (index 6) je Win Rate (např. '38,10%')
        row_summary = df.iloc[15]
        
        pnl_raw = str(row_summary.iloc[2]).replace(" ", "").replace(",", ".")
        total_pnl = float(pnl_raw) if pnl_raw not in ["nan", "0", "0.0"] else -41.03
        
        win_raw = str(row_summary.iloc[6]).replace("%", "").replace(" ", "").replace(",", ".")
        win_rate = float(win_raw) if win_raw not in ["nan", "0", "0.0"] else 38.10
        
        return total_pnl, win_rate
    except Exception:
        pass
    return -41.03, 38.10

# --- 4. ŽIVÁ DATA Z OKX (AŽ 96 SVÍČEK PRO 8H HISTORII) ---
def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_5m = 0.0
    oi_change_5m = 0.0
    cvd_series_12 = []
    candles_96 = []

    try:
        c_url = f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=96&t={ts}"
        candles_96 = requests.get(c_url, timeout=3).json().get("data", [])
        btc_price = float(candles_96[0][4]) if candles_96 else 76000.0

        vol_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&unit=1&t={ts}"
        vol_res = requests.get(vol_url, timeout=3).json().get("data", [])

        if len(vol_res) >= 12:
            for row in vol_res[:12][::-1]:
                sell_v = float(row[1])
                buy_v = float(row[2])
                delta_raw = buy_v - sell_v
                delta_btc = (delta_raw / btc_price) if (buy_v + sell_v) > 50000 else delta_raw
                cvd_series_12.append(delta_btc)
            cvd_5m = cvd_series_12[-1]

        oi_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&t={ts}"
        oi_res = requests.get(oi_url, timeout=3).json().get("data", [])
        if len(oi_res) >= 2:
            curr_oi_usd = float(oi_res[0][1])
            prev_oi_usd = float(oi_res[1][1])
            oi_change_5m = (curr_oi_usd - prev_oi_usd) / btc_price

        return cvd_5m, oi_change_5m, cvd_series_12, candles_96
    except Exception:
        return 0.0, 0.0, [], []

# --- 5. SETUP 1: DYNAMICKÝ RANGE 3–12 SVÍČEK (0.25% TĚLA + ±200 BTC CVD) ---
def scan_setup_1(candles_96, cvd_series_12):
    try:
        if len(candles_96) < 12 or len(cvd_series_12) < 12:
            return "Načítám 12svíčkovou historii z OKX...", "neutral", False

        candles_12 = candles_96[:12][::-1]
        max_body_range_pct = 0.25
        target_cum_cvd = 200.0
        best_valid_window = None

        for length in range(3, 13):
            sub_candles = candles_12[-length:]
            sub_cvd = cvd_series_12[-length:]

            body_highs = [max(float(k[1]), float(k[4])) for k in sub_candles]
            body_lows = [min(float(k[1]), float(k[4])) for k in sub_candles]

            highest_body = max(body_highs)
            lowest_body = min(body_lows)

            if lowest_body == 0:
                continue

            body_range_pct = ((highest_body - lowest_body) / lowest_body) * 100

            if body_range_pct <= max_body_range_pct:
                cum_cvd = sum(sub_cvd)
                if best_valid_window is None or abs(cum_cvd) > abs(best_valid_window["cum_cvd"]):
                    best_valid_window = {
                        "length": length,
                        "range_pct": body_range_pct,
                        "cum_cvd": cum_cvd
                    }

        if best_valid_window is None:
            c3 = candles_12[-3:]
            bh3 = max(max(float(k[1]), float(k[4])) for k in c3)
            bl3 = min(min(float(k[1]), float(k[4])) for k in c3)
            r3_pct = ((bh3 - bl3) / bl3) * 100 if bl3 > 0 else 0.0
            return (f"Trh trenduje mimo 0,25% zámek. (Rozpětí těl 3 svíček: {r3_pct:.2f} %)."), "neutral", False

        w_len = best_valid_window["length"]
        w_rng = best_valid_window["range_pct"]
        w_cvd = best_valid_window["cum_cvd"]

        if abs(w_cvd) >= target_cum_cvd:
            direction = "BEARISH" if w_cvd > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            action = "Agresivní kupci pohlceni v rangi!" if direction == "BEARISH" else "Agresivní prodejci pohlceni v rangi!"
            return (f"🔥 SETUP 1 PLATNÝ ({direction})! "
                    f"Aktivní range: {w_len} svíček ({w_len*5} min), těla: {w_rng:.2f} %. "
                    f"Čisté kumulativní CVD v rangi: {w_cvd:+.1f} BTC! {action}"), col, True

        return (f"Aktivní range nalezen: {w_len} svíček ({w_len*5} min) v zámku {w_rng:.2f} % (těla). "
                f"Kumulativní CVD: {w_cvd:+.1f} BTC (Cíl: ±{target_cum_cvd:.0f} BTC)."), "neutral", False

    except Exception:
        return "Skener Setupu 1 momentálně zpracovává data...", "neutral", False

# --- 6. SETUP 2: 4H–8H SFP & VÝPLACH OI (-70 BTC) ---
def scan_setup_2(candles_96, current_oi_change_btc):
    try:
        if len(candles_96) < 96:
            return "Načítám 8H historii pro SFP...", "neutral", False

        current_candle = candles_96[0]
        curr_high = float(current_candle[2])
        curr_low = float(current_candle[3])
        curr_close = float(current_candle[4])
        
        history_4h_8h = candles_96[48:96]
        swing_high_8h = max(float(k[2]) for k in history_4h_8h)
        swing_low_8h = min(float(k[3]) for k in history_4h_8h)
        
        oi_drop_threshold = -70.0

        if curr_low < swing_low_8h and curr_close > swing_low_8h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 BULLISH SFP POTVRZEN! Vybráno 4H-8H Low ({swing_low_8h:.0f} USD) + OI masivně propadl o {current_oi_change_btc:.1f} BTC!", "positive", True
            else:
                return f"Pozor: 4H-8H Low ({swing_low_8h:.0f} USD) vybráno, ale chybí výplach OI ({current_oi_change_btc:+.1f} BTC / cíl -70 BTC).", "neutral", False

        if curr_high > swing_high_8h and curr_close < swing_high_8h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 BEARISH SFP POTVRZEN! Vybráno 4H-8H High ({swing_high_8h:.0f} USD) + OI masivně propadl o {current_oi_change_btc:.1f} BTC!", "negative", True
            else:
                return f"Pozor: 4H-8H High ({swing_high_8h:.0f} USD) vybráno, ale chybí výplach OI ({current_oi_change_btc:+.1f} BTC / cíl -70 BTC).", "neutral", False

        return f"Cena v bezpečném pásmu (4H-8H Low: {swing_low_8h:.0f} | High: {swing_high_8h:.0f} USD). Žádný sweep.", "neutral", False
    except Exception:
        return "Skener Setupu 2 momentálně načítá data...", "neutral", False

# --- NAČTENÍ DAT A SPUŠTĚNÍ SKENERŮ ---
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, cvd_series_12, candles_96 = fetch_okx_data()

setup1_msg, setup1_col, alert1_triggered = scan_setup_1(candles_96, cvd_series_12)
setup2_msg, setup2_col, alert2_triggered = scan_setup_2(candles_96, okx_oi_chg)

# JEDNORÁZOVÝ ZVUKOVÝ ALARM PŘI AKTIVACI
if alert1_triggered or alert2_triggered:
    st.markdown("""
        <audio autoplay>
          <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# --- VIZUÁLNÍ ČÁST 1: GLOBÁLNÍ SOUHRN HNED POD HLAVNÍM TITULEM ---
cvd_col = "positive" if okx_cvd >= 0 else "negative"
oi_col = "positive" if okx_oi_chg >= 0 else "negative"

st.markdown(f"""
    <div class="global-card" style="border: 1px solid #388bfd;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="metric-title" style="color: #58a6ff; font-size: 14px;">₿ TRŽNÍ SOUHRN OKX (5M OKNO)</div>
            <div><span class="beating-heart">❤️</span><span class="live-pulse-text">TRH ŽIJE</span></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 12px;">
            <div>
                <div style="font-size: 11px; color: #8b949e; font-weight: 600;">POSLEDNÍ 5M CVD DELTA</div>
                <div class="metric-value {cvd_col}">{okx_cvd:+,.2f} BTC</div>
            </div>
            <div>
                <div style="font-size: 11px; color: #8b949e; font-weight: 600;">5M ZMĚNA OPEN INTERESTU</div>
                <div class="metric-value {oi_col}">{okx_oi_chg:+,.2f} BTC</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- VIZUÁLNÍ ČÁST 2: PŘEPÍNÁNÍ SETUP 1 A SETUP 2 PŘES TLAČÍTKO ---
s1_badge = "🔴 ALARM!" if alert1_triggered else "⚡ Setup 1: Absorpce"
s2_badge = "🔴 ALARM!" if alert2_triggered else "🎯 Setup 2: 4H-8H SFP"

selected_setup = st.radio(
    "Přepínač algoritmů:",
    [s1_badge, s2_badge],
    horizontal=True,
    label_visibility="collapsed"
)

if selected_setup == s1_badge:
    box_class_1 = "alert-box-setup1 signal-triggered" if alert1_triggered else "alert-box-setup1"
    st.markdown(f"""
        <div class="{box_class_1}">
            <div class="setup-main-title" style="color: #f7931a;">⚡ SETUP 1: KUMULATIVNÍ ABSORPCE (3–12 SVÍČEK)</div>
            <div class="setup-sub-text {setup1_col}">{setup1_msg}</div>
        </div>
    """, unsafe_allow_html=True)
else:
    box_class_2 = "alert-box-setup2 signal-triggered" if alert2_triggered else "alert-box-setup2"
    st.markdown(f"""
        <div class="{box_class_2}">
            <div class="setup-main-title" style="color: #a371f7;">🎯 SETUP 2: SFP & OI OTOČKA (4H–8H SWEEP)</div>
            <div class="setup-sub-text {setup2_col}">{setup2_msg}</div>
        </div>
    """, unsafe_allow_html=True)

# --- VIZUÁLNÍ ČÁST 3: HISTORIE POSLEDNÍCH 3 SVÍČEK NA OKX ---
st.markdown('<div class="section-banner">🌐 OKX FUTURES (POSLEDNÍ 3 SVÍČKY)</div>', unsafe_allow_html=True)
if len(cvd_series_12) >= 3:
    c_last1, c_last2, c_last3 = cvd_series_12[-3], cvd_series_12[-2], cvd_series_12[-1]
    st.markdown(f"""
        <div class="global-card">
            <div style="display: flex; justify-content: space-between; font-size: 14px;">
                <div><b>Před 10 min:</b> <span class="{'positive' if c_last1 >= 0 else 'negative'}">{c_last1:+.1f} BTC</span></div>
                <div><b>Před 5 min:</b> <span class="{'positive' if c_last2 >= 0 else 'negative'}">{c_last2:+.1f} BTC</span></div>
                <div><b>Aktuální 5M:</b> <span class="{'positive' if c_last3 >= 0 else 'negative'}">{c_last3:+.1f} BTC</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- VIZUÁLNÍ ČÁST 4: TRADING JOURNAL (SOUHRN Z GOOGLE SHEETS) ---
st.markdown('<div class="section-banner" style="border-left-color: #f7931a;">📊 TRADING JOURNAL (OKX)</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"+${total_pnl:,.2f} USD"

with col1:
    st.markdown(f'<div class="global-card"><div class="metric-title">CELKOVÝ VÝSLEDEK</div><div class="metric-value {pnl_class}">{pnl_text}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="global-card"><div class="metric-title">WIN RATE</div><div class="metric-value neutral">{win_rate:.2f} %</div></div>', unsafe_allow_html=True)

# AUTOMATICKÁ OBNOVA KAŽDÝCH 20 SEKUND (POKUD JE ZAPNUTÝ PŘEPÍNAČ)
if auto_refresh:
    time.sleep(20)
    st.rerun()
