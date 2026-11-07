import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide")

st.markdown("""
    <style>
    /* PROFESIONÁLNÍ DARK TERMINAL DESIGN */
    .stApp {
        background-color: #06080c;
        background-image: 
            radial-gradient(circle at 50% 0%, rgba(247, 147, 26, 0.1) 0%, transparent 45%),
            linear-gradient(rgba(255, 255, 255, 0.01) 1px, transparent 1px);
        background-size: 100% 100%, 20px 20px;
        color: #f0f6fc;
    }
    header[data-testid="stHeader"] {
        background: #06080c !important;
        border-bottom: 1px solid #1f2937 !important;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
    }

    /* HLAVNÍ HLAVIČKA S 3D BITCOIN MINCÍ */
    .crypto-header {
        display: flex;
        align-items: center;
        gap: 16px;
        background: linear-gradient(135deg, #0d131f 0%, #162032 100%);
        border: 1px solid #2d3748;
        border-left: 5px solid #f7931a;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }
    .title-text {
        font-size: 20px;
        font-weight: 900;
        letter-spacing: 1.5px;
        color: #ffffff;
    }

    /* MATICE OKX ORDER FLOW S VELKÝM PULZUJÍCÍM SRDCEM */
    .global-card {
        background: linear-gradient(135deg, #0d131f 0%, #111827 100%);
        border: 1px solid #2d3748;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }
    @keyframes heartbeat-lux {
        0% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(255, 75, 75, 0.4)); }
        15% { transform: scale(1.25); filter: drop-shadow(0 0 16px rgba(255, 75, 75, 0.9)); }
        30% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(255, 75, 75, 0.4)); }
        45% { transform: scale(1.15); filter: drop-shadow(0 0 12px rgba(255, 75, 75, 0.7)); }
        60% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(255, 75, 75, 0.4)); }
        100% { transform: scale(1); filter: drop-shadow(0 0 4px rgba(255, 75, 75, 0.4)); }
    }
    .lux-heart {
        display: inline-block;
        animation: heartbeat-lux 1.3s infinite ease-in-out;
    }
    .live-pulse-text { font-size: 11px; color: #ff7b72; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; }

    /* TRADING JOURNAL S DOLAROVÝM MOTIVEM */
    .banknote-card {
        background: linear-gradient(135deg, #062314 0%, #0d3822 100%);
        border: 1px solid #1f7a43;
        border-left: 5px solid #2ea043;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 6px 20px rgba(11, 61, 35, 0.4);
    }

    /* KARTY SETUP 1 A SETUP 2 */
    .alert-box-setup1 {
        background: #0d131f;
        border: 1px solid #2d3748;
        border-left: 5px solid #f7931a;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }
    .alert-box-setup2 {
        background: #0d131f;
        border: 1px solid #2d3748;
        border-left: 5px solid #a371f7;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    }
    .setup-main-title {
        font-size: 16px;
        font-weight: 900;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .setup-sub-text {
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.5;
        color: #94a3b8;
    }

    /* PŘEPÍNAČ */
    div[role="radiogroup"] {
        background: #0d131f;
        border: 1px solid #2d3748;
        padding: 6px;
        border-radius: 12px;
        display: flex;
        justify-content: space-around;
        margin-bottom: 14px;
    }
    div[role="radiogroup"] label {
        font-weight: 800 !important;
        font-size: 13.5px !important;
        color: #e2e8f0 !important;
    }

    .signal-triggered {
        background-color: #230c10 !important;
        border: 1px solid #f85149 !important;
        animation: pulse-alert 1s infinite alternate;
    }
    @keyframes pulse-alert {
        0% { box-shadow: 0 0 6px rgba(248, 81, 73, 0.4); }
        100% { box-shadow: 0 0 20px rgba(248, 81, 73, 0.8); }
    }

    /* TLAČÍTKA DOLE */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #111827 0%, #1f2937 100%);
        color: #f0f6fc !important;
        border: 1px solid #374151 !important;
        border-radius: 10px;
        padding: 11px 14px;
        font-size: 13.5px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #1f2937 0%, #374151 100%);
        border-color: #f7931a !important;
        color: #f7931a !important;
    }

    .metric-title { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; font-weight: 800; }
    .metric-value { font-size: 24px; font-weight: 900; margin-top: 4px; }
    .negative { color: #f85149; }
    .positive { color: #3fb950; }
    .neutral { color: #f1e05a; }
    </style>
""", unsafe_allow_html=True)

# --- 1. HLAVNÍ HLAVIČKA S PROPRACOVANOU 3D SVG BITCOIN MINCÍ ---
st.markdown("""
    <div class="crypto-header">
        <!-- Vektorová 3D Bitcoin Mince s hlubokým leskem -->
        <svg width="48" height="48" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0 3px 6px rgba(247,147,26,0.5)); flex-shrink: 0;">
            <circle cx="32" cy="32" r="30" fill="url(#btc_3d_grad)" stroke="#ffeaa7" stroke-width="2"/>
            <circle cx="32" cy="32" r="26" stroke="#b35900" stroke-width="1" stroke-dasharray="2 2" opacity="0.6"/>
            <path d="M39.5 27.2c.4-2.6-1.6-4-4.3-4.9l.9-3.6-2.2-.6-.9 3.5c-.6-.1-1.2-.3-1.8-.5l.9-3.5-2.2-.6-.9 3.6c-.5-.1-1-.2-1.5-.4l-3.2-.8-.6 2.5s1.7.4 1.7.4c1 .2 1.2.9 1.2 1.4l-1.2 4.8c.1 0 .2.1.3.1l-.3-.1-1.7 6.8c-.1.3-.4.8-1.2.6 0 0-1.7-.4-1.7-.4l-1.2 2.9 3 .8c.6.2 1.1.3 1.7.5l-.9 3.7 2.2.6.9-3.6c.6.2 1.2.3 1.8.5l-.9 3.7 2.2.6.9-3.7c3.7.7 6.5.4 7.7-3 1-2.8-.1-4.4-2-5.4 1.4-.3 2.5-1.2 2.8-3.1zm-5 7c-.7 2.8-5.4 1.3-6.9.9l1.2-5c1.6.4 6.4 1.2 5.7 4.1zm.7-7.1c-.6 2.5-4.5 1.2-5.8.9l1.1-4.4c1.3.3 5.4 1 4.7 3.5z" fill="#06080c"/>
            <defs>
                <radialGradient id="btc_3d_grad" cx="35%" cy="35%" r="75%">
                    <stop offset="0%" stop-color="#ffe066"/>
                    <stop offset="45%" stop-color="#f7931a"/>
                    <stop offset="100%" stop-color="#994d00"/>
                </radialGradient>
            </defs>
        </svg>
        <div class="title-text">BTC ORDER FLOW</div>
    </div>
""", unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS (NAČTENÍ Z ŘÁDKU 18 / SLOUPEC C A G) ---
@st.cache_data(ttl=30)
def load_trading_data():
    try:
        sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url, header=None)
        
        row_summary = df.iloc[17] # Řádek 18 v tabulce
        pnl_raw = str(row_summary.iloc[2]).replace(" ", "").replace(",", ".")
        total_pnl = float(pnl_raw) if pnl_raw not in ["nan", "0", "0.0"] else -41.03
        
        win_raw = str(row_summary.iloc[6]).replace("%", "").replace(" ", "").replace(",", ".")
        win_rate = float(win_raw) if win_raw not in ["nan", "0", "0.0"] else 38.10
        
        return total_pnl, win_rate
    except Exception:
        pass
    return -41.03, 38.10

# --- 3. ŽIVÁ DATA Z OKX ---
def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_5m = 0.0
    oi_change_5m = 0.0
    cvd_series_12 = []
    candles_96 = []
    oi_series_3 = []

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
        if len(oi_res) >= 4:
            for i in range(3, 0, -1):
                curr = float(oi_res[i-1][1])
                prev = float(oi_res[i][1])
                oi_series_3.append((curr - prev) / btc_price)
            oi_change_5m = oi_series_3[-1]

        return cvd_5m, oi_change_5m, cvd_series_12, oi_series_3, candles_96
    except Exception:
        return 0.0, 0.0, [], [], []

# --- 4. SKENERY ---
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
                    best_valid_window = {"length": length, "range_pct": body_range_pct, "cum_cvd": cum_cvd}

        if best_valid_window is None:
            return "Trh trenduje mimo 0,25% zámek.", "neutral", False

        w_len = best_valid_window["length"]
        w_rng = best_valid_window["range_pct"]
        w_cvd = best_valid_window["cum_cvd"]

        if abs(w_cvd) >= target_cum_cvd:
            direction = "BEARISH" if w_cvd > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            return f"🔥 SETUP 1 PLATNÝ ({direction})! Range: {w_len} svíček, CVD: {w_cvd:+.1f} BTC.", col, True

        return f"Aktivní range: {w_len} svíček v zámku {w_rng:.2f} %. Kumulativní CVD: {w_cvd:+.1f} BTC.", "neutral", False
    except Exception:
        return "Skener zpracovává data...", "neutral", False

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
                return f"🔥 BULLISH SFP! Vybráno Low ({swing_low_8h:.0f} USD) + OI propad o {current_oi_change_btc:.1f} BTC.", "positive", True
            return f"Pozor: 4H-8H Low vybráno, chybí výplach OI ({current_oi_change_btc:+.1f} BTC).", "neutral", False

        if curr_high > swing_high_8h and curr_close < swing_high_8h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 BEARISH SFP! Vybráno High ({swing_high_8h:.0f} USD) + OI propad o {current_oi_change_btc:.1f} BTC.", "negative", True
            return f"Pozor: 4H-8H High vybráno, chybí výplach OI ({current_oi_change_btc:+.1f} BTC).", "neutral", False

        return "Cena v bezpečném pásmu. Žádný sweep.", "neutral", False
    except Exception:
        return "Skener zpracovává data...", "neutral", False

total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, cvd_series_12, oi_series_3, candles_96 = fetch_okx_data()

setup1_msg, setup1_col, alert1_triggered = scan_setup_1(candles_96, cvd_series_12)
setup2_msg, setup2_col, alert2_triggered = scan_setup_2(candles_96, okx_oi_chg)

if alert1_triggered or alert2_triggered:
    st.markdown("""
        <audio autoplay>
          <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# --- OKX ORDER FLOW MATRIX S VELKÝM PULZUJÍCÍM SVG SRDCEM ---
cvd_col = "positive" if okx_cvd >= 0 else "negative"
oi_col = "positive" if okx_oi_chg >= 0 else "negative"

c1, c2, c3 = (cvd_series_12[-3], cvd_series_12[-2], cvd_series_12[-1]) if len(cvd_series_12) >= 3 else (0, 0, 0)
oi1, oi2, oi3 = (oi_series_3[0], oi_series_3[1], oi_series_3[2]) if len(oi_series_3) >= 3 else (0, 0, 0)

st.markdown(f"""
    <div class="global-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 13px; font-weight: 800; color: #58a6ff; letter-spacing: 1px;">OKX ORDER FLOW MATRIX</div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <div class="lux-heart">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="#ff4b4b" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                    </svg>
                </div>
                <span class="live-pulse-text">TRH ŽIJE</span>
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 14px;">
            <div>
                <div class="metric-title">AKTUÁLNÍ 5M CVD</div>
                <div class="metric-value {cvd_col}">{okx_cvd:+,.2f} BTC</div>
            </div>
            <div>
                <div class="metric-title">AKTUÁLNÍ 5M OI</div>
                <div class="metric-value {oi_col}">{okx_oi_chg:+,.2f} BTC</div>
            </div>
        </div>
        <hr style="border-color: #1f2937; margin: 14px 0;">
        <div class="metric-title" style="margin-bottom: 6px;">HISTORIE POSLEDNÍCH 3 SVÍČEK (15 MIN)</div>
        <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 700;">
            <div>CVD: <span class="{'positive' if c1 >= 0 else 'negative'}">{c1:+.1f}</span> | <span class="{'positive' if c2 >= 0 else 'negative'}">{c2:+.1f}</span> | <span class="{'positive' if c3 >= 0 else 'negative'}">{c3:+.1f} BTC</span></div>
            <div>OI: <span class="{'positive' if oi1 >= 0 else 'negative'}">{oi1:+.1f}</span> | <span class="{'positive' if oi2 >= 0 else 'negative'}">{oi2:+.1f}</span> | <span class="{'positive' if oi3 >= 0 else 'negative'}">{oi3:+.1f} BTC</span></div>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- PŘEPÍNAČ SETUPŮ ---
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

# --- TRADING JOURNAL S DOLAROVÝMI MOTIVY (BEZ TEXTOVÉHO NADPISU) ---
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"+${total_pnl:,.2f} USD"

col1, col2 = st.columns(2)

with col1:
    st.markdown(f'''
        <div class="banknote-card">
            <div>
                <div class="metric-title" style="color: #7ee787;">CELKOVÝ VÝSLEDEK</div>
                <div class="metric-value {pnl_class}">{pnl_text}</div>
            </div>
            <!-- SVG Hromada dolarových bankovek -->
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3);">
                <path d="M21 4H3C1.9 4 1 4.9 1 6V18C1 19.1 1.9 20 3 20H21C22.1 20 23 19.1 23 18V6C23 4.9 22.1 4 21 4ZM21 18H3V6H21V18ZM12 8C9.79 8 8 9.79 8 12C8 14.21 9.79 16 12 16C14.21 16 16 14.21 16 12C16 9.79 14.21 8 12 8ZM12 14.5C10.62 14.5 9.5 13.38 9.5 12C9.5 10.62 10.62 9.5 12 9.5C13.38 9.5 14.5 10.62 14.5 12C14.5 13.38 13.38 14.5 12 14.5Z" fill="#3fb950"/>
            </svg>
        </div>
    ''', unsafe_allow_html=True)

with col2:
    st.markdown(f'''
        <div class="banknote-card" style="border-left-color: #f1e05a; border-color: #89571e; background: linear-gradient(135deg, #1f1b09 0%, #2e260d 100%);">
            <div>
                <div class="metric-title" style="color: #f1e05a;">WIN RATE</div>
                <div class="metric-value neutral">{win_rate:.2f} %</div>
            </div>
            <!-- SVG Zlatá hromada peněz / úspěch -->
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink: 0; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3);">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" fill="#f1e05a"/>
            </svg>
        </div>
    ''', unsafe_allow_html=True)

# --- OVLÁDACÍ PRVKY ÚPLNĚ DOLE ---
st.markdown("<br>", unsafe_allow_html=True)
col_bot1, col_bot2 = st.columns([3, 2])
with col_bot1:
    if st.button("🔄 AKTUALIZOVAT TRH"):
        pass
with col_bot2:
    auto_refresh = st.toggle("⏱️ Auto (20s)", value=False)

if auto_refresh:
    time.sleep(20)
    st.rerun()
