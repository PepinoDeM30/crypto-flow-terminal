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
    .neutral {
      color: #e3b341;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ Global Crypto Flow")
st.write("Přehled výkonu účtu & živý order flow.")

# --- SEKCE 1: VÝKON ÚČTU Z GOOGLE SHEETS ---
st.markdown("### 📊 Trading Journal (OKX)")

col1, col2 = st.columns(2)

with col1:
  st.markdown(
      """
        <div class="global-card">
            <div class="metric-title">Celkový výsledek (vč. fees)</div>
            <div class="metric-value negative">-$37.77 USD</div>
        </div>
        """,
      unsafe_allow_html=True,
  )

with col2:
  st.markdown(
      """
        <div class="global-card">
            <div class="metric-title">Win Rate</div>
            <div class="metric-value neutral">36.84%</div>
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

