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
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 13px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: bold;
        color: #58a6ff;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("⚡ Global Crypto Flow")
st.write("Agregovaný přehled order flow z OKX a Bybitu v reálném čase.")

# Jednotný hlavní globální panel optimalizovaný na výšku pro mobil
st.markdown(
    """
    <div class="global-card">
        <div class="metric-title">Sledovaný trh</div>
        <div class="metric-value">BTC / USDT (Globální souhrn)</div>
        <hr style="border-color: #30363d; margin: 15px 0;">
        <b>Aggregated CVD:</b> <span style="color: #e3b341;">Čeká se na připojení...</span><br><br>
        <b>Detekce akce:</b> <span style="color: #8b949e;">Sleduje se absorpce / exhaustion</span><br><br>
        <b>Stav serveru:</b> <span style="color: #2ea043;">● Připraveno na data (OKX + Bybit)</span>
    </div>
    """,
    unsafe_allow_html=True,
)
