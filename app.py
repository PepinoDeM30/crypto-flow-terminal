import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Crypto Flow Terminal", page_icon="⚡", layout="wide"
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .global-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 12px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        font-size: 20px;
        font-weight: bold;
        margin-top: 5px;
    }
    .negative {
      color: #f85149;
    }
    .positive {
      color: #3fb950;
    }
    .neutral {
      color: #e3b341;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ Global Crypto Flow")
st.write("Přehled výkonu účtu & živý order flow.")


# --- 1. FUNKCE PRO GOOGLE SHEETS (JÚRNAL) ---
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
      win_rate = (
          (winning_trades / total_trades) * 100 if total_trades > 0 else 0
      )

      if total_trades > 0:
        return total_pnl, win_rate
  except Exception as e:
    pass
  return -37.77, 36.84


# --- 2. FUNKCE PRO ŽIVÁ DATA Z OKX (BTCUSD UM / BTC-USD-SWAP) ---
@st.cache_data(ttl=10)
def fetch_okx_market_data():
  try:
    # Open Interest pro BTC-USD-SWAP (Coin-margined / UM)
    oi_url = (
        "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USD-SWAP"
    )
    oi_res = requests.get(oi_url, timeout=3).json()
    oi_val = float(oi_res["data"][0]["oi"])

    # Recent Trades pro výpočet krátkodobého CVD
    trades_url = (
        "https://www.okx.com/api/v5/market/trades?instId=BTC-USD-SWAP&limit=100"
    )
    trades_res = requests.get(trades_url, timeout=3).json()

    buy_vol = 0
    sell_vol = 0
    for t in trades_res.get("data", []):
      sz = float(t["sz"])
      if t["side"] == "buy":
        buy_vol += sz
      else:
        sell_vol += sz

    cvd_delta = buy_vol - sell_vol
    return oi_val, cvd_delta, True
  except Exception:
    return 0.0, 0.0, False


# Načtení dat
total_pnl, win_rate = load_trading_data()
okx_oi, okx_cvd, okx_success = fetch_okx_market_data()

# --- SEKCE 1: VÝKON ÚČTU ---
st.markdown("### 📊 Trading Journal (OKX)")
col1, col2 = st.columns(2)

with col1:
  pnl_class = "negative" if total_pnl < 0 else "positive"
  pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"{total_pnl:,.2f} USD"
  st.markdown(
      f"""
        <div class="global-card">
            <div class="metric-title">Celkový výsledek (vč. fees)</div>
            <div class="metric-value {pnl_class}">{pnl_text}</div>
        </div>
        """,
      unsafe_allow_html=True,
  )

with col2:
  wr_text = f"{win_rate:.2f}%"
  st.markdown(
      f"""
        <div class="global-card">
            <div class="metric-title">Win Rate</div>
            <div class="metric-value neutral">{wr_text}</div>
        </div>
        """,
      unsafe_allow_html=True,
  )

# --- SEKCE 2: ŽIVÁ DATA OKX (BTCUSD UM) ---
st.markdown("### ⚡ OKX Live Order Flow")

if okx_success:
  cvd_color = "positive" if okx_cvd >= 0 else "negative"
  cvd_text = f"+{okx_cvd:.2f} contracts" if okx_cvd >= 0 else f"{okx_cvd:.2f} contracts"
  oi_text = f"{okx_oi:,.0f} kont."
  server_status = '<span style="color: #2ea043;">● OKX Live (BTCUSD UM)</span>'
else:
  cvd_color = "neutral"
  cvd_text = "Načítání..."
  oi_text = "Načítání..."
  server_status = '<span style="color: #e3b341;">● Čeká se na data burzy</span>'

st.markdown(
    f"""
    <div class="global-card">
        <div class="metric-title">Sledovaný trh (OKX)</div>
        <div class="metric-value" style="color: #58a6ff;">BTCUSD UM (Coin-Margined)</div>
        <hr style="border-color: #30363d; margin: 12px 0;">
        <span style="font-size: 14px;">
        <b>Krátkodobé CVD (Delta):</b> <span class="{cvd_color}">{cvd_text}</span><br><br>
        <b>Open Interest (OI):</b> <span style="color: #ffffff;">{oi_text}</span><br><br>
        <b>Stav serveru:</b> {server_status}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


