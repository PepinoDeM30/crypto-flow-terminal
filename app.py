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
        padding-top: 2.2rem !important;
        padding-bottom: 3rem !important;
    }

    /* 3D EFEKT PRO NADPISY A HLAVNÍ TEXTY */
    .text-3d {
        text-shadow: 0 1px 0 #cccccc, 0 2px 0 #c9c9c9, 0 3px 0 #bbbbbb, 0 4px 0 #b9b9b9, 
                     0 5px 0 #aaaaaa, 0 6px 1px rgba(0,0,0,0.3), 0 0 5px rgba(0,0,0,0.5), 
                     0 1px 3px rgba(0,0,0,0.5), 0 3px 5px rgba(0,0,0,0.4), 0 5px 10px rgba(0,0,0,0.4);
    }
    .title-3d {
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 1.5px;
        background: linear-gradient(90deg, #ffffff 0%, #ffd700 55%, #f7931a 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(2px 3px 4px rgba(0,0,0,0.7));
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
        box-shadow: 0 0 20px rgba(247, 147, 26, 0.9), inset 0 2px 4px rgba(255,255,255,0.6);
        border: 2px solid #fff5d6;
        flex-shrink: 0;
    }

    /* GLOBÁLNÍ KARTY A 3D PULZUJÍCÍ SRDCE */
    .global-card {
        background: rgba(16, 22, 33, 0.92);
        border: 1px solid #2b384e;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 14px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    @keyframes heartbeat {
        0% { transform: scale(1); filter: drop-shadow(0 0 4px #ff4b4b); }
        15% { transform: scale(1.35); filter: drop-shadow(0 0 12px #ff4b4b); }
        30% { transform: scale(1); filter: drop-shadow(0 0 4px #ff4b4b); }
        45% { transform: scale(1.25); filter: drop-shadow(0 0 10px #ff4b4b); }
        60% { transform: scale(1); filter: drop-shadow(0 0 4px #ff4b4b); }
        100% { transform: scale(1); filter: drop-shadow(0 0 4px #ff4b4b); }
    }
    .beating-heart { display: inline-block; animation: heartbeat 1.4s infinite; font-size: 18px; margin-right: 6px; }
    .live-pulse-text { font-size: 12px; color: #ff6b6b; font-weight: 700; letter-spacing: 0.8px; }

    /* BANKOVKOVÝ DESIGN PRO TRADING JOURNAL (SMARAGDOVÁ ZÁŘ) */
    .banknote-card {
        background: linear-gradient(135deg, rgba(11, 41, 26, 0.95) 0%, rgba(18, 61, 39, 0.95) 50%, rgba(11, 41, 26, 0.95) 100%);
        border: 1px solid #2ecc71;
        border-left: 5px solid #27ae60;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 14px;
        box-shadow: 0 6px 20px rgba(39, 174, 96, 0.25), inset 0 1px 0 rgba(255,255,255,0.1);
    }

    /* KARTY SETUP 1 A SETUP 2 */
    .alert-box-setup1 {
        background: rgba(18, 22, 32, 0.95);
        border: 1px solid #455065;
        border-left: 5px solid #f7931a;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.4);
    }
    .alert-box-setup2 {
        background: rgba(21, 18, 36, 0.95);
        border: 1px solid #483766;
        border-left: 5px solid #a371f7;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.4);
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
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }

    /* TLAČÍTKA DOLE */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #141f33 0%, #1d2d4a 50%, #141f33 100%);
        color: #ffd700 !important;
        border: 1px solid #f7931a !important;
        border-radius: 10px;
        padding: 11px 14px;
        font-size: 14px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        box-shadow: 0 4px 14px rgba(247, 147, 26, 0.3);
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #f7931a 0%, #ffb700 100%);
        color: #06090f !important;
        box-shadow: 0 0 20px rgba(247, 147, 26, 0.8);
    }

    .metric-title { font-size: 12px; color: #9da7b3; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
    .metric-value { font-size: 24px; font-weight: 900; margin-top: 4px; }
    .negative { color: #ff5555; }
    .positive { color: #3fb950; }
    .neutral { color: #ffd700; }
    </style>
""", unsafe_allow_html=True)

# --- 1. HLAVNÍ HLAVIČKA ---
st.markdown("""
    <div class="crypto-header">
        <div class="btc-badge">₿</div>
        <div class="title-3d">BTC ORDER FLOW</div>
    </div>
""", unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS (NAČTENÍ PŘESNĚ Z ŘÁDKU 18 / SLOUPCE C A G) ---
@st.cache_data(ttl=30)
def load_trading_data():
    try:
        sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url, header=None)
        
        # Řádek 18 v tabulce (index 17 v Pythonu) obsahuje souhrn
        # Sloupec C (index 2) je celkový PnL, Sloupec G (index 6) je Win Rate
        row_summary = df.iloc[17]
        
        pnl_raw = str(row_summary.iloc[2]).replace(" ", "").replace(",", ".")
        total_pnl = float(pnl_raw) if pnl_raw not in ["nan", "0", "0.0"] else -41.03
        
        win_raw = str(row_summary.iloc[6]).replace("%", "").replace(" ", "").replace(",", ".")
        win_rate = float(win_raw) if win_raw not in ["nan", "0", "0.0"] else 38.10
        
        return total_pnl, win_rate
    except Exception:
        pass
    return -41.03, 38.10

# --- 3. ŽIVÁ DATA Z OKX (AŽ 96 SVÍČEK PRO 8H SFP + CVD HISTORIE) ---
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

# --- 4. SETUP 1: DYNAMICKÝ RANGE 3–12 SVÍČEK (0.25% TĚLA + ±200 BTC CVD) ---
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
            r3_pct = ((bh3 - bl3) / bl3) * 100 if bl3 > 0
