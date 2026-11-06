import pandas as pd
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


# --- FUNKCE PRO STAŽENÍ A VÝPOČET DAT Z GOOGLE SHEETS ---
@st.cache_data(ttl=60)  # Data se kešují na 60 vteřin pro rychlost
def load_trading_data():
  try:
    sheet_id = "1nyV3Xa0BNX-DVLkkbd-wshjuHzPcjOVw3jr6O3BjxCw"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    df = pd.read_csv(csv_url)

    # Obchody začínají od řádku 16 (index 16 v pandas)
    trades_df = df.iloc[16:].copy()
    trades_df.columns = [
        "Datum",
        "Pair",
        "LongShort",
        "Risk",
        "Exit",
        "Vysledek",
        "Fees",
        "NaN",
    ]
    trades_df = trades_df.dropna(subset=["Datum"])

    # Převod na čísla
    trades_df["Vysledek"] = pd.to_numeric(trades_df["Vysledek"], errors="coerce")
    trades_df = trades_df.dropna(subset=["Vysledek"])

    total_pnl = trades_df["Vysledek"].sum()
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df["Vysledek"] > 0])
    win_rate = (
        (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    )

    return total_pnl, win_rate, True
  except Exception as e:
    return 0.0, 0.0, False


# Načteme data
total_pnl, win_rate, success = load_trading_data()

# --- SEKCE 1: VÝKON ÚČTU Z GOOGLE SHEETS ---
st.markdown("### 📊 Trading Journal (OKX)")

col1, col2 = st.columns(2)

with col1:
  if success:
    pnl_class = "negative" if total_pnl < 0 else "positive"
    pnl_text = f"{total_pnl:,.2f} USD"
    if total_pnl < 0:
      pnl_text = f"-${abs(total_pnl):,.2f} USD"
  else:
    pnl_text = "Chyba načítání"
    pnl_class = "neutral"

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
  wr_text = f"{win_rate:.2f}%" if success else "0.00%"
  st.markdown(
      f"""
        <div class="global-card">
            <div class="metric-title">Win Rate</div>
            <div class="metric-value neutral">{wr_text}</div>
        </div>
        """,
      unsafe_allow_html=True,
  )

# --- SEKCE 2: HLAVNÍ GLOBÁLNÍ PANEL (OKX + BYBIT) ---
st.markdown(
    """
    <div class="global-card">
        <div class="metric-title">Sledovaný trh (OKX + Bybit)</div>
        <div class="metric-value" style="color: #58a6ff;">BTC / USDT (Globální souhrn)</div>
        <hr style="border-color: #30363d; margin: 12px 0;">
        <span style="font-size: 14px;">
        <b>Aggregated CVD:</b> <span style="color: #e3b341;">Čeká se na data...</span><br><br>
        <b>Detekce akce:</b> <span style="color: #8b949e;">Sleduje se absorpce / exhaustion</span><br><br>
        <b>Stav serveru:</b> <span style="color: #2ea043;">● Systém online (Připraveno)</span>
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


