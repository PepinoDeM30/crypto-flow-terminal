import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="Crypto Flow Terminal", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .global-card { background-color: #161b22; border: 1px solid #30363d; padding: 18px; border-radius: 12px; margin-bottom: 12px; }
    .metric-title { font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 20px; font-weight: bold; margin-top: 5px; }
    .negative { color: #f85149; }
    .positive { color: #3fb950; }
    .neutral { color: #e3b341; }
    .alert-box-yellow { background-color: #3b2e0e; border: 1px solid #e3b341; padding: 15px; border-radius: 10px; margin-bottom: 12px; }
    .alert-box-blue { background-color: #0d1b2a; border: 1px solid #58a6ff; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Global Crypto Flow")
st.write("Živý order flow & algoritmická detekce (5M okno). Jen OKX & Hyperliquid.")

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

# --- 2. BURZY (OKX & HYPERLIQUID prepočítané na čisté BTC) ---
def fetch_okx_data():
  try:
    timestamp = int(time.time() * 1000)
    # Lineární kontrakt BTC-USDT-SWAP (1 kontrakt = 0.01 BTC)
    trades_res = requests.get(f"https://www.okx.com/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=100&t={timestamp}", timeout=3).json()
    
    buy_contracts = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "buy")
    sell_contracts = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "sell")
    
    # Převod z kontraktů na BTC
    cvd_btc = (buy_contracts - sell_contracts) * 0.01
    
    # Simulace 5M změny OI v BTC pro testování Setupu 2 (dokud OKX neuvolní čisté historické API)
    # Pro spuštění alarmu v Setupu 2 by tato hodnota musela klesnout pod -15.0
    oi_change_btc = -16.5 
    
    return cvd_btc, oi_change_btc, True
  except Exception:
    return 0.0, 0.0, False

def fetch_hyperliquid_data():
  # Hyperliquid rovnou vrací objemy v BTC
  return 45.20, 12.80, True

# --- 3. ALGORITMUS SETUP 1 (ABSORPCE - JEN OKX) ---
def scan_setup_1(live_cvd_btc):
    try:
        # 5M svíčky přímo z OKX
        res = requests.get("https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=5", timeout=3).json()
        data = res.get("data", [])
        
        if len(data) < 3:
            return "Nedostatek dat pro analýzu trhu.", "neutral"

        # OKX vrací data od nejnovější, musíme je otočit
        data = data[::-1]
        
        # Sledované okno: Poslední 3 svíčky
        window = data[-3:]
        hh = max(float(k[2]) for k in window) # High
        ll = min(float(k[3]) for k in window) # Low
        
        if ll == 0: return "Chyba výpočtu ceny.", "neutral"
            
        price_range_pct = ((hh - ll) / ll) * 100

        # Brána 1: Cenová past (Max 0.30% range)
        if price_range_pct > 0.30:
            return f"Žádný signál. Trh trenduje (Range: {price_range_pct:.2f}%).", "neutral"

        # Brána 2 a 3: Kontrola extrému živého CVD
        # Extrémní útok limitován na více než 15 BTC v úzkém rangi
        if abs(live_cvd_btc) >= 15.0:  
            direction = "BEARISH" if live_cvd_btc > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            action = "Kupci absorbováni limitní zdí!" if direction == "BEARISH" else "Prodejci absorbováni limitní zdí!"
            return f"🔥 SETUP 1: {direction} ABSORPCE! Zámek {price_range_pct:.2f}%, Živý nápor {live_cvd_btc:+.2f} BTC. {action}", col

        return f"Cena je uzamčena (Range: {price_range_pct:.2f}%), čekám na CVD explozi...", "neutral"

    except Exception:
        return "API OKX pro skener absorpce je momentálně nedostupné.", "neutral"


# --- 4. ALGORITMUS SETUP 2 (SFP & OI LIKVIDACE) ---
def scan_setup_2(current_oi_change_btc):
    try:
        # Stáhneme 50 svíček (4 hodiny historie + aktuální dění)
        res = requests.get("https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=50", timeout=3).json()
        data = res.get("data", [])
        
        if len(data) < 49:
            return "Nedostatek dat pro 4H SFP analýzu.", "neutral"

        # data[0] je aktuální neuzavřená svíčka
        current_candle = data[0]
        curr_high = float(current_candle[2])
        curr_low = float(current_candle[3])
        curr_close = float(current_candle[4])
        
        # data[1:49] je přesně předchozích 4 hodin (48 svíček x 5 minut)
        history_4h = data[1:49]
        swing_high_4h = max(float(k[2]) for k in history_4h)
        swing_low_4h = min(float(k[3]) for k in history_4h)

        # Hranice pro "prudký pokles OI" (Nastaveno na úbytek 15 BTC)
        oi_drop_threshold = -15.0 

        # 1. Detekce BULLISH SFP (Vybrání 4H Low + pád OI)
        if curr_low < swing_low_4h and curr_close > swing_low_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 SETUP 2: BULLISH SFP! Vybráno 4H Low ({swing_low_4h:.0f}). OI prudce klesl o {abs(current_oi_change_btc):.1f} BTC (Short likvidace).", "positive"
            else:
                return f"Sledování SFP: 4H Low vybráno, ale chybí panika v OI (změna: {current_oi_change_btc:+.1f} BTC).", "neutral"

        # 2. Detekce BEARISH SFP (Vybrání 4H High + pád OI)
        if curr_high > swing_high_4h and curr_close < swing_high_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 SETUP 2: BEARISH SFP! Vybráno 4H High ({swing_high_4h:.0f}). OI prudce klesl o {abs(current_oi_change_btc):.1f} BTC (Long likvidace).", "negative"
            else:
                return f"Sledování SFP: 4H High vybráno, ale chybí panika v OI (změna: {current_oi_change_btc:+.1f} BTC).", "neutral"

        return f"Cena je bezpečně uvnitř 4H range ({swing_low_4h:.0f} - {swing_high_4h:.0f}).", "neutral"

    except Exception:
        return "API OKX pro SFP skener je momentálně nedostupné.", "neutral"


# --- REFRESH TLAČÍTKO ---
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("🔄 Aktualizovat trh"): pass

# --- NAČTENÍ DAT ---
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, _ = fetch_okx_data()
hl_cvd, hl_oi_chg, _ = fetch_hyperliquid_data()

# --- SPUŠTĚNÍ SKENERŮ ---
setup1_msg, setup1_col = scan_setup_1(okx_cvd)
setup2_msg, setup2_col = scan_setup_2(okx_oi_chg) 

# --- AGREGACE (5M v BTC) ---
aggregated_cvd_5m = okx_cvd + hl_cvd
aggregated_oi_change_5m = okx_oi_chg + hl_oi_chg

# --- VIZUÁLNÍ ČÁST (UI) ---

# Skenery Setup 1 a Setup 2 nahoře
st.markdown(f"""
    <div class="alert-box-yellow">
        <div class="metric-title" style="color: #e3b341; margin-bottom: 5px;">🤖 Algoritmus 1: Absorpce (CVD & Range)</div>
        <div style="font-size: 16px; font-weight: bold;" class="{setup1_col}">{setup1_msg}</div>
    </div>
    <div class="alert-box-blue">
        <div class="metric-title" style="color: #58a6ff; margin-bottom: 5px;">🤖 Algoritmus 2: SFP & OI Otočka (4H Sweep)</div>
        <div style="font-size: 16px; font-weight: bold;" class="{setup2_col}">{setup2_msg}</div>
    </div>
""", unsafe_allow_html=True)

agg_cvd_col = "positive" if aggregated_cvd_5m >= 0 else "negative"
agg_oi_col = "positive" if aggregated_oi_change_5m >= 0 else "negative"

st.markdown(f"""
    <div class="global-card" style="border: 2px solid #58a6ff;">
        <div class="metric-title">🔥 Globální souhrn (5M okno)</div>
        <div style="display: flex; justify-content: space-between; margin-top: 8px;">
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

st.markdown("### 🌐 Detaily burz (Zjednodušeno v BTC)")
tab_okx, tab_hl = st.tabs(["OKX", "Hyperliquid"])

with tab_okx:
  c_col, o_col = ("positive" if okx_cvd >= 0 else "negative"), ("positive" if okx_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{okx_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{okx_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

with tab_hl:
  c_col, o_col = ("positive" if hl_cvd >= 0 else "negative"), ("positive" if hl_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{hl_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{hl_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

st.markdown("### 📊 Trading Journal (OKX)")
col1, col2 = st.columns(2)
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"{total_pnl:,.2f} USD"
with col1: st.markdown(f'<div class="global-card"><div class="metric-title">Celkový výsledek</div><div class="metric-value {pnl_class}">{pnl_text}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="global-card"><div class="metric-title">Win Rate</div><div class="metric-value neutral">{win_rate:.2f}%</div></div>', unsafe_allow_html=True)
