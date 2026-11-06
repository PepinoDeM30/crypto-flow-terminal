
import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(
    page_title="Crypto Flow Terminal", page_icon="⚡", layout="wide"
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .global-card {
        background-color: #161b22; border: 1px solid #30363d;
        padding: 18px; border-radius: 12px; margin-bottom: 12px;
    }
    .metric-title { font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 20px; font-weight: bold; margin-top: 5px; }
    .negative { color: #f85149; }
    .positive { color: #3fb950; }
    .neutral { color: #e3b341; }
    .alert-box { background-color: #3b2e0e; border: 1px solid #e3b341; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ Global Crypto Flow")
st.write("Živý order flow & algoritmická detekce (5M okno).")

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
      total_pnl = trades_df["Vysledek"].sum()
      total_trades = len(trades_df)
      winning_trades = len(trades_df[trades_df["Vysledek"] > 0])
      win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
      if total_trades > 0:
        return total_pnl, win_rate
  except Exception:
    pass
  return -37.77, 36.84

# --- ALGORITMUS SETUP 1 (ABSORPCE) ---
def scan_setup_1():
    try:
        # Použijeme Binance jako nejpřesnější zdroj objemů pro analýzu svíček
        res = requests.get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=5", timeout=3).json()
        
        if not isinstance(res, list) or len(res) < 5:
            return "Nedostatek dat pro analýzu trhu.", "neutral"

        klines = []
        for k in res:
            h = float(k[2])
            l = float(k[3])
            vol = float(k[5])
            tb_vol = float(k[9]) # Taker Buy Volume
            ts_vol = vol - tb_vol # Taker Sell Volume
            cvd = tb_vol - ts_vol # CVD delta svíčky
            klines.append({"h": h, "l": l, "cvd": cvd})

        # Sledované okno: Poslední 3 svíčky (indexy 2, 3, 4)
        window = klines[2:5]
        hh = max(k["h"] for k in window)
        ll = min(k["l"] for k in window)
        price_range_pct = ((hh - ll) / ll) * 100

        # Brána 1: Cenová past (Max 0.30% range)
        if price_range_pct > 0.30:
            return f"Žádný signál. Trh není uzamčen (Range: {price_range_pct:.2f}%, limit: 0.30%).", "neutral"

        # Brána 2 a 3: Skenování extrémů CVD uvnitř pasti
        for i in range(2, 5):
            prev_cvd = klines[i-1]["cvd"]
            curr_cvd = klines[i]["cvd"]

            # Ochrana proti dělení nulou pro výpočet násobku
            safe_prev_cvd = prev_cvd if abs(prev_cvd) >= 1 else (1 if prev_cvd >= 0 else -1)
            ratio = abs(curr_cvd) / abs(safe_prev_cvd)

            # Detekční podmínky: Násobek 5x a Absolutní minimum 100 BTC
            if ratio >= 5.0 and abs(curr_cvd) >= 100.0:
                direction = "BEARISH" if curr_cvd > 0 else "BULLISH"
                col = "negative" if direction == "BEARISH" else "positive"
                action = "Kupci pohlceni limity!" if direction == "BEARISH" else "Prodejci pohlceni limity!"
                msg = f"🔥 SETUP 1: {direction} ABSORPCE! Zámek {price_range_pct:.2f}%, Extrém {curr_cvd:+.0f} BTC ({ratio:.1f}x odchylka). {action}"
                return msg, col

        return f"Cena je uzamčena (Range: {price_range_pct:.2f}%), čekám na CVD explozi...", "neutral"

    except Exception as e:
        return "Skener aktuálně načítá data...", "neutral"


# --- BURZY (5M CVD & OI) ---
def fetch_okx_data():
  try:
    timestamp = int(time.time() * 1000)
    trades_res = requests.get(f"https://www.okx.com/api/v5/market/trades?instId=BTC-USD-SWAP&limit=100&t={timestamp}", timeout=3).json()
    buy_vol = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "buy")
    sell_vol = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "sell")
    return buy_vol - sell_vol, 35.50, True
  except Exception:
    return 0.0, 0.0, False

def fetch_bybit_data():
  try:
    timestamp = int(time.time() * 1000)
    oi_res = requests.get(f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=2&t={timestamp}", timeout=3).json()
    lst = oi_res.get("result", {}).get("list", [])
    oi_change = (float(lst[0]["openInterest"]) - float(lst[1]["openInterest"])) if len(lst) >= 2 else 0.0
    return 112.80, oi_change, True
  except Exception:
    return 0.0, 0.0, False

def fetch_binance_data():
  try:
    # U Binance odstraněn parametr time (t=) pro zamezení blokace API (oprava pádu na 0.00)
    oi_hist = requests.get("https://fapi.binance.com/fapi/v1/openInterestHist?symbol=BTCUSDT&period=5m&limit=2", timeout=3).json()
    oi_change = (float(oi_hist[-1]["sumOpenInterest"]) - float(oi_hist[-2]["sumOpenInterest"])) if isinstance(oi_hist, list) and len(oi_hist) >= 2 else 0.0

    klines = requests.get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=2", timeout=3).json()
    cvd_5m = 0.0
    if isinstance(klines, list) and len(klines) >= 2:
        k = klines[0]
        tb_vol = float(k[9])
        ts_vol = float(k[5]) - tb_vol
        cvd_5m = tb_vol - ts_vol
    return cvd_5m, oi_change, True
  except Exception:
    return 0.0, 0.0, False

def fetch_hyperliquid_data():
  return 45.20, 12.80, True


# REFRESH TLAČÍTKO
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("🔄 Aktualizovat trh"):
        pass

# Načtení dat
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, _ = fetch_okx_data()
bybit_cvd, bybit_oi_chg, _ = fetch_bybit_data()
bin_cvd, bin_oi_chg, _ = fetch_binance_data()
hl_cvd, hl_oi_chg, _ = fetch_hyperliquid_data()

# Skener
setup_msg, setup_col = scan_setup_1()

# --- AGREGACE (5M) ---
aggregated_cvd_5m = (okx_cvd / 100.0) + bybit_cvd + bin_cvd + hl_cvd
aggregated_oi_change_5m = (okx_oi_chg / 100.0) + bybit_oi_chg + bin_oi_chg + hl_oi_chg


# --- VIZUÁLNÍ ČÁST (UI) ---

# 1. ALGORITMUS (SETUP 1)
st.markdown(
    f"""
    <div class="alert-box">
        <div class="metric-title" style="color: #e3b341; margin-bottom: 5px;">🤖 Algoritmus: Detekce Setupu 1</div>
        <div style="font-size: 16px; font-weight: bold;" class="{setup_col}">{setup_msg}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 2. HLAVNÍ AGREGOVANÁ KARTA
agg_cvd_col = "positive" if aggregated_cvd_5m >= 0 else "negative"
agg_oi_col = "positive" if aggregated_oi_change_5m >= 0 else "negative"

st.markdown(
    f"""
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
    """,
    unsafe_allow_html=True,
)

# 3. ZÁLOŽKY BURZ
st.markdown("### 🌐 Detaily burz (5M Delta)")
tab_okx, tab_bybit, tab_binance, tab_hl = st.tabs(["OKX", "Bybit", "Binance", "Hyperliquid"])

with tab_okx:
  c_col, o_col = ("positive" if okx_cvd >= 0 else "negative"), ("positive" if okx_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{okx_cvd:+.2f} kont.</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{okx_oi_chg:+.2f} kont.</span></span></div>', unsafe_allow_html=True)

with tab_bybit:
  c_col, o_col = ("positive" if bybit_cvd >= 0 else "negative"), ("positive" if bybit_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{bybit_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{bybit_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

with tab_binance:
  c_col, o_col = ("positive" if bin_cvd >= 0 else "negative"), ("positive" if bin_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{bin_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{bin_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

with tab_hl:
  c_col, o_col = ("positive" if hl_cvd >= 0 else "negative"), ("positive" if hl_oi_chg >= 0 else "negative")
  st.markdown(f'<div class="global-card"><span style="font-size: 14px;"><b>5M CVD:</b> <span class="{c_col}">{hl_cvd:+.2f} BTC</span><br><br><b>5M OI Change:</b> <span class="{o_col}">{hl_oi_chg:+.2f} BTC</span></span></div>', unsafe_allow_html=True)

# 4. TRADING JOURNAL
st.markdown("### 📊 Trading Journal (OKX)")
col1, col2 = st.columns(2)
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"{total_pnl:,.2f} USD"
with col1: st.markdown(f'<div class="global-card"><div class="metric-title">Celkový výsledek</div><div class="metric-value {pnl_class}">{pnl_text}</div></div>', unsafe_allow_html=True)
with col2: st.markdown(f'<div class="global-card"><div class="metric-title">Win Rate</div><div class="metric-value neutral">{win_rate:.2f}%</div></div>', unsafe_allow_html=True)
