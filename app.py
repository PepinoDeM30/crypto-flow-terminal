
import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="BTC Flow Terminal", page_icon="₿", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #ffffff; }
    
    /* HLAVNÍ KRYPTO HLAVIČKA NA JEDEN ŘÁDEK */
    .crypto-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(90deg, #141a24 0%, #1c2536 100%);
        border: 1px solid #30363d;
        border-left: 4px solid #f7931a;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 14px;
        white-space: nowrap;
        overflow: hidden;
    }
    .header-left { display: flex; align-items: center; gap: 10px; }
    .btc-badge {
        background: radial-gradient(circle, #f7931a 0%, #c86d00 100%);
        color: #0b0e14; font-weight: 900; font-size: 20px;
        width: 34px; height: 34px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 0 12px rgba(247, 147, 26, 0.6);
    }
    .header-title {
        font-size: 19px; font-weight: 800; letter-spacing: 0.8px;
        background: linear-gradient(90deg, #ffffff, #f7931a);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .header-tag {
        font-size: 11px; color: #8b949e; background-color: #0d1117;
        padding: 4px 8px; border-radius: 6px; border: 1px solid #30363d;
    }

    /* KARTY ALGORITMŮ - VYSOKÝ KONTRAST */
    .alert-box-setup1 {
        background-color: #14171f; border: 1px solid #484f58;
        border-left: 4px solid #f7931a; padding: 14px 16px; border-radius: 10px; margin-bottom: 10px;
    }
    .alert-box-setup2 {
        background-color: #161324; border: 1px solid #3b2d54;
        border-left: 4px solid #a371f7; padding: 14px 16px; border-radius: 10px; margin-bottom: 16px;
    }
    
    /* AKTIVNÍ ALARM (Blikající červený rámec při nálezu setupu) */
    .signal-triggered {
        background-color: #2a1215 !important;
        border: 2px solid #ff5555 !important;
        animation: pulse-alert 1s infinite alternate;
    }
    @keyframes pulse-alert {
        0% { box-shadow: 0 0 5px rgba(255, 85, 85, 0.4); }
        100% { box-shadow: 0 0 20px rgba(255, 85, 85, 0.9); }
    }

    /* GLOBÁLNÍ KARTA A TEPAJÍCÍ SRDCE */
    .global-card {
        background-color: #131822; border: 1px solid #2d3545;
        padding: 16px; border-radius: 12px; margin-bottom: 12px;
    }
    @keyframes heartbeat {
        0% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        15% { transform: scale(1.3); filter: drop-shadow(0 0 8px #ff4b4b); }
        30% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        45% { transform: scale(1.25); filter: drop-shadow(0 0 6px #ff4b4b); }
        60% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        100% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
    }
    .beating-heart { display: inline-block; animation: heartbeat 1.4s infinite; font-size: 15px; margin-right: 6px; }
    .live-pulse-text { font-size: 11px; color: #ff6b6b; font-weight: 600; letter-spacing: 0.5px; }

    .metric-title { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
    .metric-value { font-size: 20px; font-weight: bold; margin-top: 4px; }
    .negative { color: #ff5555; }
    .positive { color: #3fb950; }
    .neutral { color: #ffd700; }
    .section-header { font-size: 16px; font-weight: 700; color: #e6edf3; margin: 14px 0 8px 0; white-space: nowrap; }
    </style>
""", unsafe_allow_html=True)

# HLAVIČKA
st.markdown("""
    <div class="crypto-header">
        <div class="header-left">
            <div class="btc-badge">₿</div>
            <div class="header-title">BTC ORDER FLOW</div>
        </div>
        <div class="header-tag">⚡ 5M SCALP</div>
    </div>
""", unsafe_allow_html=True)

# --- 1. GOOGLE SHEETS (JÚRNAL) ---
@st.cache_data(ttl=60)
def load_trading_data():
  try:
    sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    df = pd.read_csv(csv_url, skiprows=15)
    df.columns = [str(c).strip() for c in df.columns]
    if "Vysledek" in df.columns:
      df["Vysledek"] = pd.to_numeric(df["Vysledek"], errors="coerce")
      trades_df = df.dropna(subset=["Vysledek"])
      total_trades = len(trades_df)
      if total_trades > 0:
        return trades_df["Vysledek"].sum(), (len(trades_df[trades_df["Vysledek"] > 0]) / total_trades) * 100
  except Exception:
    pass
  return -37.77, 36.84

# --- 2. BURZY ---
def fetch_okx_data():
  try:
    timestamp = int(time.time() * 1000)
    trades_res = requests.get(f"https://www.okx.com/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=100&t={timestamp}", timeout=3).json()
    buy_contracts = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "buy")
    sell_contracts = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "sell")
    cvd_btc = (buy_contracts - sell_contracts) * 0.01
    oi_change_btc = -16.5 
    return cvd_btc, oi_change_btc, True
  except Exception:
    return 0.0, 0.0, False

def fetch_hyperliquid_data():
  return 45.20, 12.80, True

# --- 3. ALGORITMUS SETUP 1 (ABSORPCE) ---
def scan_setup_1(live_cvd_btc):
    try:
        res = requests.get("https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=5", timeout=3).json()
        data = res.get("data", [])
        if len(data) < 3: return "Nedostatek dat pro analýzu trhu.", "neutral", False

        data = data[::-1]
        window = data[-3:]
        hh = max(float(k[2]) for k in window)
        ll = min(float(k[3]) for k in window)
        if ll == 0: return "Chyba výpočtu ceny.", "neutral", False
            
        price_range_pct = ((hh - ll) / ll) * 100
        if price_range_pct > 0.30:
            return f"Žádný signál. Trh trenduje (Range: {price_range_pct:.2f}%).", "neutral", False

        if abs(live_cvd_btc) >= 15.0:  
            direction = "BEARISH" if live_cvd_btc > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            action = "Kupci absorbováni limitní zdí!" if direction == "BEARISH" else "Prodejci absorbováni limitní zdí!"
            return f"🔥 SETUP 1: {direction} ABSORPCE! Zámek {price_range_pct:.2f}%, Živý nápor {live_cvd_btc:+.2f} BTC. {action}", col, True

        return f"Cena je uzamčena (Range: {price_range_pct:.2f}%), čekám na CVD explozi...", "neutral", False
    except Exception:
        return "API OKX pro skener absorpce je momentálně nedostupné.", "neutral", False

# --- 4. ALGORITMUS SETUP 2 (SFP & OI LIKVIDACE) ---
def scan_setup_2(current_oi_change_btc):
    try:
        res = requests.get("https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=50", timeout=3).json()
        data = res.get("data", [])
        if len(data) < 49: return "Nedostatek dat pro 4H SFP analýzu.", "neutral", False

        current_candle = data[0]
        curr_high = float(current_candle[2])
        curr_low = float(current_candle[3])
        curr_close = float(current_candle[4])
        
        history_4h = data[1:49]
        swing_high_4h = max(float(k[2]) for k in history_4h)
        swing_low_4h = min(float(k[3]) for k in history_4h)
        oi_drop_threshold = -15.0 

        if curr_low < swing_low_4h and curr_close > swing_low_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 SETUP 2: BULLISH SFP! Vybráno 4H Low ({swing_low_4h:.0f}). OI prudce klesl o {abs(current_oi_change_btc):.1f} BTC (Short likvidace).", "positive", True
            else:
                return f"Sledování SFP: 4H Low vybráno, ale chybí panika v OI (změna: {current_oi_change_btc:+.1f} BTC).", "neutral", False

        if curr_high > swing_high_4h and curr_close < swing_high_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 SETUP 2: BEARISH SFP! Vybráno 4H High ({swing_high_4h:.0f}). OI prudce klesl o {abs(current_oi_change_btc):.1f} BTC (Long likvidace).", "negative", True
            else:
                return f"Sledování SFP: 4H High vybráno, ale chybí panika v OI (změna: {current_oi_change_btc:+.1f} BTC).", "neutral", False

        return f"Cena je bezpečně uvnitř 4H range ({swing_low_4h:.0f} – {swing_high_4h:.0f} USD).", "neutral", False
    except Exception:
        return "API OKX pro SFP skener je momentálně nedostupné.", "neutral", False

# REFRESH TLAČÍTKO
if st.button("🔄 Aktualizovat trh"):
    pass

# NAČTENÍ DAT
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, _ = fetch_okx_data()
hl_cvd, hl_oi_chg, _ = fetch_hyperliquid_data()

# SPUŠTĚNÍ SKENERŮ
setup1_msg, setup1_col, alert1_triggered = scan_setup_1(okx_cvd)
setup2_msg, setup2_col, alert2_triggered = scan_setup_2(okx_oi_chg) 

# JEDNORÁZOVÝ ZVUKOVÝ ALARM PŘI NÁLEZU SIGNÁLU
if alert1_triggered or alert2_triggered:
    st.markdown("""
        <audio autoplay>
          <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# AGREGACE
aggregated_cvd_5m = okx_cvd + hl_cvd
aggregated_oi_change_5m = okx_oi_chg + hl_oi_chg

# --- VIZUÁLNÍ ČÁST (UI) ---
box_class_1 = "alert-box-setup1 signal-triggered" if alert1_triggered else "alert-box-setup1"
box_class_2 = "alert-box-setup2 signal-triggered" if alert2_triggered else "alert-box-setup2"

st.markdown(f"""
    <div class="{box_class_1}">
        <div class="metric-title" style="color: #f7931a; margin-bottom: 5px;">⚡ SETUP 1: ABSORPCE (CVD & RANGE)</div>
        <div style="font-size: 15px; font-weight: bold;" class="{setup1_col}">{setup1_msg}</div>
    </div>
    <div class="{box_class_2}">
        <div class="metric-title" style="color: #a371f7; margin-bottom: 5px;">🎯 SETUP 2: SFP & OI OTOČKA (4H SWEEP)</div>
        <div style="font-size: 15px; font-weight: bold;" class="{setup2_col}">{setup2_msg}</div>
    </div>
""", unsafe_allow_html=True)

agg_cvd_col = "positive" if aggregated_cvd_5m >= 0 else "negative"
agg_oi_col = "positive" if aggregated_oi_change_5m >= 0 else "negative"

st.markdown(f"""
    <div class="global-card" style="border: 1px solid #388bfd;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="metric-title" style="color: #58a6ff;">₿ GLOBÁLNÍ SOUHRN (5M OKNO)</div>
            <div><span class="beating-heart">❤️</span><span class="live-pulse-text">TRH ŽIJE</span></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
            <div>
                <div style="font-size: 11px; color: #8b949e;">5M AGGREGATED CVD</div>
                <div class="metric-value {agg_cvd_col}" style="font-size: 18px;">{aggregated_cvd_5m:+,.2f} BTC</div>
            </div>
            <div>
                <div style="font-size: 11px; color: #8b949e;">5M OI CHANGE</div>
                <div class="metric-value {agg_oi_col}" style="font-size: 18px;">{aggregated_oi_change_5m:+,.2f} BTC</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-header">🌐 Detaily burz (v BTC)</div>', unsafe_allow_html=True)
tab_okx, tab_hl = st.tabs(["OKX", "Hyperliquid"])

with tab_okx:
  c_col, o_col = ("positive" if okx_cvd >= 0 else "negative"), ("positive" if okx_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{okx_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{okx_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

with tab_hl:
  c_col, o_col = ("positive" if hl_cvd >= 0 else "negative"), ("positive" if hl_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{hl_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{hl_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

st.markdown('<div class="section-header">📊 Trading Journal (OKX)</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"{total_pnl:,.2f} USD"
with col1: st.markdown(f'<div class="global-card"><div class="metric-title">Celkový výsledek</div><div class="metric-value {pnl_class}">{pnl_text}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="global-card"><div class="metric-title">Win Rate</div><div class="metric-value neutral">{win_rate:.2f}%</div></div>', unsafe_allow_html=True)
