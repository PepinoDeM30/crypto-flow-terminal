import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #040609;
        color: #f0f6fc;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
    }
    
    /* GIGANTICKÁ 3D MINCE A NADPIS */
    .giant-header {
        text-align: center;
        margin-bottom: 30px;
        position: relative;
    }
    .giant-btc-img {
        width: 100%;
        max-width: 350px;
        border-radius: 20px;
        box-shadow: 0 15px 40px rgba(247, 147, 26, 0.4);
        margin-bottom: -40px; /* Posune nadpis přes obrázek */
        position: relative;
        z-index: 1;
    }
    .giant-title {
        font-size: 32px;
        font-weight: 900;
        letter-spacing: 2px;
        color: #ffffff;
        text-shadow: 0 5px 15px rgba(0,0,0,0.9), 0 2px 5px rgba(0,0,0,0.8);
        position: relative;
        z-index: 2;
        background: rgba(0,0,0,0.4);
        padding: 10px;
        border-radius: 10px;
        display: inline-block;
    }

    /* MATICE S OBROVSKÝM SRDCEM */
    .matrix-card {
        background: linear-gradient(180deg, #0d131f 0%, #06080c 100%);
        border: 1px solid #1f2937;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    @keyframes giant-pulse {
        0% { transform: scale(1); filter: drop-shadow(0 0 15px rgba(255, 50, 50, 0.5)); }
        15% { transform: scale(1.2); filter: drop-shadow(0 0 35px rgba(255, 50, 50, 0.9)); }
        30% { transform: scale(1); filter: drop-shadow(0 0 15px rgba(255, 50, 50, 0.5)); }
        45% { transform: scale(1.15); filter: drop-shadow(0 0 25px rgba(255, 50, 50, 0.7)); }
        60% { transform: scale(1); filter: drop-shadow(0 0 15px rgba(255, 50, 50, 0.5)); }
        100% { transform: scale(1); filter: drop-shadow(0 0 15px rgba(255, 50, 50, 0.5)); }
    }
    .giant-heart {
        width: 120px; /* OBROVSKÉ SRDCE */
        height: auto;
        animation: giant-pulse 1.3s infinite ease-in-out;
        margin: 20px 0;
    }
    
    /* VÝSLEDKY NA POZADÍ PENĚZ */
    .money-journal {
        background: url('https://images.unsplash.com/photo-1611928482473-7b27d24eab80?q=80&w=800&auto=format&fit=crop') center/cover;
        border-radius: 15px;
        padding: 30px 20px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(39, 174, 96, 0.3);
        position: relative;
        overflow: hidden;
    }
    /* Tmavý filtr přes peníze, aby šla přečíst čísla */
    .money-overlay {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(4, 20, 10, 0.85);
        z-index: 1;
    }
    .money-content {
        position: relative;
        z-index: 2;
    }

    /* KARTY SETUP 1 A SETUP 2 */
    .alert-box {
        background: #0d131f;
        border: 1px solid #1f2937;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 16px;
    }
    .signal-triggered {
        background-color: #230c10 !important;
        border: 2px solid #f85149 !important;
        animation: pulse-alert 1s infinite alternate;
    }
    @keyframes pulse-alert {
        0% { box-shadow: 0 0 10px rgba(248, 81, 73, 0.4); }
        100% { box-shadow: 0 0 30px rgba(248, 81, 73, 0.9); }
    }

    /* SPODNÍ TLAČÍTKA */
    div.stButton > button {
        width: 100%;
        background: #111827;
        color: #f0f6fc !important;
        border: 1px solid #374151 !important;
        border-radius: 10px;
        padding: 15px;
        font-size: 15px !important;
        font-weight: 900 !important;
    }
    div.stButton > button:hover {
        border-color: #f7931a !important;
        color: #f7931a !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. GIGANTICKÁ 3D HLAVIČKA BITCOINU ---
st.markdown("""
    <div class="giant-header">
        <img src="https://images.unsplash.com/photo-1621416894569-0f39ed31d247?q=80&w=800&auto=format&fit=crop" class="giant-btc-img">
        <div class="giant-title">BTC ORDER FLOW</div>
    </div>
""", unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS (NAČTENÍ Z ŘÁDKU 18) ---
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

# --- 3. ŽIVÁ DATA Z OKX ---
def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_5m, oi_change_5m = 0.0, 0.0
    cvd_series_12, candles_96, oi_series_3 = [], [], []
    try:
        c_url = f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=96&t={ts}"
        candles_96 = requests.get(c_url, timeout=3).json().get("data", [])
        btc_price = float(candles_96[0][4]) if candles_96 else 76000.0

        vol_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&unit=1&t={ts}"
        vol_res = requests.get(vol_url, timeout=3).json().get("data", [])
        if len(vol_res) >= 12:
            for row in vol_res[:12][::-1]:
                delta_raw = float(row[2]) - float(row[1])
                cvd_series_12.append((delta_raw / btc_price) if (float(row[2]) + float(row[1])) > 50000 else delta_raw)
            cvd_5m = cvd_series_12[-1]

        oi_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&t={ts}"
        oi_res = requests.get(oi_url, timeout=3).json().get("data", [])
        if len(oi_res) >= 4:
            for i in range(3, 0, -1):
                oi_series_3.append((float(oi_res[i-1][1]) - float(oi_res[i][1])) / btc_price)
            oi_change_5m = oi_series_3[-1]

        return cvd_5m, oi_change_5m, cvd_series_12, oi_series_3, candles_96
    except Exception:
        return 0.0, 0.0, [], [], []

# --- SKENERY ---
def scan_setup_1(candles_96, cvd_series_12):
    try:
        if len(candles_96) < 12 or len(cvd_series_12) < 12: return "Načítám 12 svíček...", False
        candles_12 = candles_96[:12][::-1]
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
        if best_w is None: return "Trh mimo 0,25% zámek.", False
        if abs(best_w["cvd"]) >= 200: return f"🔥 SETUP 1 PLATNÝ! CVD: {best_w['cvd']:+.1f} BTC.", True
        return f"Range aktivní. CVD: {best_w['cvd']:+.1f} BTC.", False
    except Exception: return "Načítám data...", False

def scan_setup_2(candles_96, current_oi):
    try:
        if len(candles_96) < 96: return "Načítám 8H historii...", False
        low_8h, high_8h = min(float(k[3]) for k in candles_96[48:96]), max(float(k[2]) for k in candles_96[48:96])
        curr = candles_96[0]
        if float(curr[3]) < low_8h and float(curr[4]) > low_8h:
            if current_oi <= -70: return f"🔥 BULLISH SFP! OI propad o {current_oi:.1f} BTC.", True
            return "Pozor: 4H-8H Low vybráno, chybí výplach OI.", False
        if float(curr[2]) > high_8h and float(curr[4]) < high_8h:
            if current_oi <= -70: return f"🔥 BEARISH SFP! OI propad o {current_oi:.1f} BTC.", True
            return "Pozor: 4H-8H High vybráno, chybí výplach OI.", False
        return "Cena v bezpečném pásmu.", False
    except Exception: return "Načítám data...", False

# DATA
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, cvd_12, oi_3, c_96 = fetch_okx_data()
msg1, trg1 = scan_setup_1(c_96, cvd_12)
msg2, trg2 = scan_setup_2(c_96, okx_oi_chg)

# ZVUK
if trg1 or trg2:
    st.markdown('<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

# --- 4. MATICE S OBROVSKÝM SRDCEM UPROSTŘED ---
c1, c2, c3 = (cvd_12[-3], cvd_12[-2], cvd_12[-1]) if len(cvd_12) >= 3 else (0, 0, 0)
o1, o2, o3 = (oi_3[0], oi_3[1], oi_3[2]) if len(oi_3) >= 3 else (0, 0, 0)

st.markdown(f"""
    <div class="matrix-card">
        <div style="color: #58a6ff; font-weight: 900; font-size: 18px; margin-bottom: 10px; letter-spacing: 2px;">OKX ORDER FLOW MATRIX</div>
        
        <!-- OBROVSKÉ CENTRÁLNÍ SRDCE -->
        <img src="https://cdn.pixabay.com/photo/2017/02/09/16/59/heart-2052845_960_720.png" class="giant-heart">
        
        <div style="display: flex; justify-content: space-around; align-items: center; margin-bottom: 20px;">
            <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 13px; font-weight: 800; letter-spacing: 1px;">5M CVD</div>
                <div style="font-size: 32px; font-weight: 900; color: {'#3fb950' if okx_cvd >= 0 else '#f85149'};">{okx_cvd:+,.1f}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: #94a3b8; font-size: 13px; font-weight: 800; letter-spacing: 1px;">5M OI</div>
                <div style="font-size: 32px; font-weight: 900; color: {'#3fb950' if okx_oi_chg >= 0 else '#f85149'};">{okx_oi_chg:+,.1f}</div>
            </div>
        </div>
        <div style="color: #6e7681; font-size: 12px; font-weight: 800; text-transform: uppercase;">Posledních 15 minut</div>
        <div style="font-size: 14px; font-weight: 700; color: #c9d1d9;">CVD: {c1:+.1f} | {c2:+.1f} | {c3:+.1f}</div>
        <div style="font-size: 14px; font-weight: 700; color: #c9d1d9;">OI: {o1:+.1f} | {o2:+.1f} | {o3:+.1f}</div>
    </div>
""", unsafe_allow_html=True)

# --- PŘEPÍNAČ SETUPŮ ---
s_mode = st.radio("Mód:", ["⚡ Setup 1: Absorpce", "🎯 Setup 2: SFP"], horizontal=True, label_visibility="collapsed")
if "Setup 1" in s_mode:
    st.markdown(f'<div class="alert-box {"signal-triggered" if trg1 else ""}"><div style="color: #f7931a; font-weight: 900; font-size: 18px;">⚡ SETUP 1</div><div style="color: #c9d1d9; font-size: 15px; margin-top: 5px;">{msg1}</div></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="alert-box {"signal-triggered" if trg2 else ""}"><div style="color: #a371f7; font-weight: 900; font-size: 18px;">🎯 SETUP 2</div><div style="color: #c9d1d9; font-size: 15px; margin-top: 5px;">{msg2}</div></div>', unsafe_allow_html=True)

# --- 5. VÝSLEDKY NA OBROVSKÉM FOTO-POZADÍ 3D BANKOVEK ---
st.markdown(f"""
    <div class="money-journal">
        <div class="money-overlay"></div>
        <div class="money-content" style="display: flex; justify-content: space-around;">
            <div>
                <div style="color: #7ee787; font-size: 14px; font-weight: 900; letter-spacing: 2px;">CELKOVÝ PNL</div>
                <div style="font-size: 40px; font-weight: 900; color: {'#3fb950' if total_pnl >= 0 else '#f85149'};">
                    {('+$' if total_pnl >= 0 else '-$')}{abs(total_pnl):,.2f}
                </div>
            </div>
            <div>
                <div style="color: #f1e05a; font-size: 14px; font-weight: 900; letter-spacing: 2px;">WIN RATE</div>
                <div style="font-size: 40px; font-weight: 900; color: #f1e05a;">{win_rate:.2f} %</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- SPODEK ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🔄 AKTUALIZOVAT"): pass
if st.toggle("⏱️ Auto Refresh (20s)", value=False):
    time.sleep(20)
    st.rerun()
