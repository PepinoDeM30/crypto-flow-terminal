import pandas as pd
import requests
import streamlit as st
import time

st.set_page_config(page_title="BTC Order Flow", page_icon="₿", layout="wide")

st.markdown("""
    <style>
    /* ZÁKLADNÍ POZADÍ A ÚPRAVA HORNÍ LIŠTY (SHARE, STAR ATD.) */
    .stApp { background-color: #080b10; color: #ffffff; }
    header[data-testid="stHeader"] {
        background: linear-gradient(90deg, #0d131d 0%, #172234 50%, #0d131d 100%) !important;
        border-bottom: 1px solid #f7931a55 !important;
    }
    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 2rem !important;
    }

    /* TLAČÍTKO AKTUALIZOVAT TRH POD HORNÍM MENU */
    div.stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #162238 0%, #1f304d 50%, #162238 100%);
        color: #ffd700 !important;
        border: 1px solid #f7931a !important;
        border-radius: 10px;
        padding: 10px 16px;
        font-size: 15px !important;
        font-weight: 800 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        box-shadow: 0 0 12px rgba(247, 147, 26, 0.25);
        transition: all 0.2s ease-in-out;
        margin-bottom: 8px;
    }
    div.stButton > button:hover, div.stButton > button:active {
        background: linear-gradient(90deg, #f7931a 0%, #ffb700 100%);
        color: #080b10 !important;
        box-shadow: 0 0 18px rgba(247, 147, 26, 0.7);
    }

    /* HLAVNÍ KRYPTO HLAVIČKA S VÝRAZNÝM ZNAKEM BTC */
    .crypto-header {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        background: linear-gradient(135deg, #101622 0%, #1c273c 50%, #101622 100%);
        border: 1px solid #3a465e;
        border-bottom: 3px solid #f7931a;
        padding: 14px 18px;
        border-radius: 14px;
        margin-bottom: 16px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6);
        white-space: nowrap;
    }
    .btc-badge {
        background: radial-gradient(circle at 30% 30%, #ffd700 0%, #f7931a 55%, #b85d00 100%);
        color: #080b10;
        font-weight: 900;
        font-size: 26px;
        width: 46px;
        height: 46px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 0 18px rgba(247, 147, 26, 0.85);
        border: 2px solid #fff3d1;
        flex-shrink: 0;
    }
    .header-title {
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 1.5px;
        background: linear-gradient(90deg, #ffffff 0%, #ffd700 50%, #f7931a 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 2px 10px rgba(247, 147, 26, 0.2);
    }

    /* KARTY SETUP 1 A SETUP 2 (VELKÝ NADPIS, MENŠÍ VYSVĚTLENÍ) */
    .alert-box-setup1 {
        background-color: #12161f;
        border: 1px solid #3d4656;
        border-left: 5px solid #f7931a;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 12px;
    }
    .alert-box-setup2 {
        background-color: #151224;
        border: 1px solid #3b2d54;
        border-left: 5px solid #a371f7;
        padding: 16px 18px;
        border-radius: 12px;
        margin-bottom: 18px;
    }
    .setup-main-title {
        font-size: 20px;
        font-weight: 900;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .setup-sub-text {
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.45;
    }

    /* BLIKAJÍCÍ ALARM PŘI DETEKCI SETUPU */
    .signal-triggered {
        background-color: #2a1215 !important;
        border: 2px solid #ff5555 !important;
        animation: pulse-alert 1s infinite alternate;
    }
    @keyframes pulse-alert {
        0% { box-shadow: 0 0 5px rgba(255, 85, 85, 0.4); }
        100% { box-shadow: 0 0 22px rgba(255, 85, 85, 0.95); }
    }

    /* GLOBÁLNÍ KARTA A TEPAJÍCÍ SRDCE */
    .global-card {
        background-color: #121722;
        border: 1px solid #283246;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 12px;
    }
    @keyframes heartbeat {
        0% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        15% { transform: scale(1.3); filter: drop-shadow(0 0 8px #ff4b4b); }
        30% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        45% { transform: scale(1.25); filter: drop-shadow(0 0 6px #ff4b4b); }
        60% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
        100% { transform: scale(1); filter: drop-shadow(0 0 2px #ff4b4b); }
    }
    .beating-heart { display: inline-block; animation: heartbeat 1.4s infinite; font-size: 16px; margin-right: 6px; }
    .live-pulse-text { font-size: 12px; color: #ff6b6b; font-weight: 700; letter-spacing: 0.6px; }

    /* NADPISY SEKCÍ (DETAILY BURZ & TRADING JOURNAL) */
    .section-banner {
        background: linear-gradient(90deg, #161d2b 0%, #0d1119 100%);
        border-left: 4px solid #58a6ff;
        border-top: 1px solid #263042;
        border-right: 1px solid #263042;
        border-bottom: 1px solid #263042;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 20px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.6px;
        margin: 18px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* BARVY METRIK */
    .metric-title { font-size: 12px; color: #9da7b3; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
    .metric-value { font-size: 22px; font-weight: 800; margin-top: 4px; }
    .negative { color: #ff5555; }
    .positive { color: #3fb950; }
    .neutral { color: #ffd700; }
    </style>
""", unsafe_allow_html=True)

# --- 1. TLAČÍTKO AKTUALIZOVAT TRH (Hned nahoře pod menu) ---
if st.button("🔄 AKTUALIZOVAT TRH"):
    pass

# --- 2. HLAVNÍ HLAVIČKA ---
st.markdown("""
    <div class="crypto-header">
        <div class="btc-badge">₿</div>
        <div class="header-title">BTC ORDER FLOW</div>
    </div>
""", unsafe_allow_html=True)

# --- 3. GOOGLE SHEETS (TRADING JOURNAL) ---
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

# --- 4. ŽIVÁ DATA Z OKX (BTCUSD UM / Linear Swap v BTC) ---
def fetch_okx_data():
    ts = int(time.time() * 1000)
    cvd_5m = 0.0
    oi_change_5m = 0.0
    cvd_series = []

    try:
        ticker = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP&t={ts}", timeout=3).json()
        btc_price = float(ticker["data"][0]["last"]) if ticker.get("data") else 75800.0

        # A) 5M Taker Buy/Sell Volume z OKX (poslední 4 pětiminutové svíčky)
        vol_url = f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy=BTC&instType=CONTRACTS&period=5m&t={ts}"
        vol_res = requests.get(vol_url, timeout=3).json().get("data", [])

        if len(vol_res) >= 4:
            for row in vol_res[:4][::-1]:
                sell_v = float(row[1])
                buy_v = float(row[2])
                delta_raw = buy_v - sell_v
                if (buy_v + sell_v) > 50000:
                    delta_btc = delta_raw / btc_price
                else:
                    delta_btc = delta_raw
                cvd_series.append(delta_btc)
            cvd_5m = cvd_series[-1]
        else:
            trades_res = requests.get(f"https://www.okx.com/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=500&t={ts}", timeout=3).json()
            buy_c = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "buy")
            sell_c = sum(float(t["sz"]) for t in trades_res.get("data", []) if t["side"] == "sell")
            cvd_5m = (buy_c - sell_c) * 0.01
            cvd_series = [cvd_5m / 3, cvd_5m / 3, cvd_5m / 3, cvd_5m]

        # B) 5M změna Open Interestu z OKX
        oi_url = f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=5m&t={ts}"
        oi_res = requests.get(oi_url, timeout=3).json().get("data", [])
        if len(oi_res) >= 2:
            curr_oi_usd = float(oi_res[0][1])
            prev_oi_usd = float(oi_res[1][1])
            oi_change_5m = (curr_oi_usd - prev_oi_usd) / btc_price
        else:
            live_oi_res = requests.get(f"https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP&t={ts}", timeout=3).json()
            curr_oi_btc = float(live_oi_res["data"][0]["oiCcy"])
            if "okx_prev_oi" in st.session_state:
                oi_change_5m = curr_oi_btc - st.session_state["okx_prev_oi"]
            st.session_state["okx_prev_oi"] = curr_oi_btc

        return cvd_5m, oi_change_5m, cvd_series
    except Exception:
        return 0.0, 0.0, [0.0, 0.0, 0.0, 0.0]

# --- 5. ŽIVÁ DATA Z HYPERLIQUIDU (Reálné API v BTC) ---
def fetch_hyperliquid_data():
    cvd_5m = 0.0
    oi_change_5m = 0.0
    try:
        headers = {"Content-Type": "application/json"}
        trades_req = requests.post("https://api.hyperliquid.xyz/info", json={"type": "recentTrades", "coin": "BTC"}, headers=headers, timeout=3).json()
        if isinstance(trades_req, list):
            buy_btc = sum(float(t["sz"]) for t in trades_req if t.get("side") == "B")
            sell_btc = sum(float(t["sz"]) for t in trades_req if t.get("side") == "A")
            cvd_5m = buy_btc - sell_btc

        meta_req = requests.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"}, headers=headers, timeout=3).json()
        if isinstance(meta_req, list) and len(meta_req) >= 2:
            universe = meta_req[0].get("universe", [])
            asset_ctxs = meta_req[1]
            btc_idx = next((i for i, item in enumerate(universe) if item.get("name") == "BTC"), 0)
            curr_hl_oi = float(asset_ctxs[btc_idx].get("openInterest", 0.0))

            if "hl_baseline_oi" not in st.session_state:
                st.session_state["hl_baseline_oi"] = curr_hl_oi
            oi_change_5m = curr_hl_oi - st.session_state["hl_baseline_oi"]
            st.session_state["hl_baseline_oi"] = (st.session_state["hl_baseline_oi"] * 0.85) + (curr_hl_oi * 0.15)

        return cvd_5m, oi_change_5m
    except Exception:
        return 0.0, 0.0

# --- 6. ALGORITMUS SETUP 1 (KONZERVATIVNÍ VARIANTY B + C) ---
def scan_setup_1(cvd_series, total_live_cvd):
    try:
        ts = int(time.time() * 1000)
        res = requests.get(f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=5&t={ts}", timeout=3).json()
        data = res.get("data", [])
        if len(data) < 4:
            return "Nedostatek dat pro analýzu 5M svíček.", "neutral", False

        candles = data[:4][::-1]
        
        # Poslední 3 svíčky (15 minut)
        window_3 = candles[-3:]
        hh_3 = max(float(k[2]) for k in window_3)
        ll_3 = min(float(k[3]) for k in window_3)
        range_3_pct = ((hh_3 - ll_3) / ll_3) * 100 if ll_3 > 0 else 99.0

        # Poslední 4 svíčky (20 minut)
        hh_4 = max(float(k[2]) for k in candles)
        ll_4 = min(float(k[3]) for k in candles)
        range_4_pct = ((hh_4 - ll_4) / ll_4) * 100 if ll_4 > 0 else 99.0

        # KONZERVATIVNÍ PARAMETRY (Podle měřítka Velo)
        max_allowed_range = 0.20  # Přísný cenový zámek 0,20 %
        min_single_spike = 80.0   # 4. svíčka musí mít alespoň 80 BTC deltu
        min_ratio_b = 3.0         # 4. svíčka musí být aspoň 3x větší než součet předchozích 3
        min_cum_3_delta = 130.0   # Kumulativní delta za 3 svíčky v rangi musí být aspoň 130 BTC

        if range_3_pct > max_allowed_range:
            return f"Trh není uzamčen (Range 3 svíček: {range_3_pct:.2f} %, limit: {max_allowed_range:.2f} %).", "neutral", False

        d1, d2, d3, d4 = cvd_series if len(cvd_series) == 4 else [10.0, 10.0, 10.0, total_live_cvd]
        
        # --- VARIANTA B: 4. svíčka >= 3x souhrn předchozích 3 svíček a zároveň >= 80 BTC ---
        prev_3_sum_abs = abs(d1) + abs(d2) + abs(d3)
        safe_prev_sum = prev_3_sum_abs if prev_3_sum_abs >= 15.0 else 15.0
        ratio_b = abs(d4) / safe_prev_sum

        if range_4_pct <= max_allowed_range and ratio_b >= min_ratio_b and abs(d4) >= min_single_spike:
            direction = "BEARISH" if d4 > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            action = "Kupci narazili do masivní zdi!" if direction == "BEARISH" else "Prodejci narazili do masivní zdi!"
            return (f"🔥 [VARIANTA B] {direction} ABSORPCE! 4M Range: {range_4_pct:.2f} %. "
                    f"4. svíčka ({d4:+.1f} BTC) je {ratio_b:.1f}x větší než předchozí 3! {action}"), col, True

        # --- VARIANTA C: Kumulativní absorpce >= 130 BTC za 3 svíčky v 0,20% rangi ---
        cum_3_delta = d2 + d3 + d4
        if range_3_pct <= max_allowed_range and abs(cum_3_delta) >= min_cum_3_delta:
            direction = "BEARISH" if cum_3_delta > 0 else "BULLISH"
            col = "negative" if direction == "BEARISH" else "positive"
            action = "Agresivní kupci plně absorbováni!" if direction == "BEARISH" else "Agresivní prodejci plně absorbováni!"
            return (f"🔥 [VARIANTA C] KUMULATIVNÍ {direction} ABSORPCE! 3M Range: {range_3_pct:.2f} %. "
                    f"Kumulativní delta za 3 svíčky: {cum_3_delta:+.1f} BTC bez proražení! {action}"), col, True

        return (f"Cena v 0,20% zámku ({range_3_pct:.2f} %). "
                f"Poslední svíčka: {d4:+.1f} BTC (cíl ±{min_single_spike:.0f} BTC & {min_ratio_b:.0f}x), "
                f"3M kumulace: {cum_3_delta:+.1f} BTC (cíl ±{min_cum_3_delta:.0f} BTC)."), "neutral", False

    except Exception:
        return "API pro skener Setupu 1 momentálně načítá data...", "neutral", False

# --- 7. ALGORITMUS SETUP 2 (4H SFP & KONZERVATIVNÍ POKLES OI) ---
def scan_setup_2(current_oi_change_btc):
    try:
        ts = int(time.time() * 1000)
        res = requests.get(f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=5m&limit=50&t={ts}", timeout=3).json()
        data = res.get("data", [])
        if len(data) < 49:
            return "Nedostatek dat pro 4H SFP analýzu.", "neutral", False

        current_candle = data[0]
        curr_high = float(current_candle[2])
        curr_low = float(current_candle[3])
        curr_close = float(current_candle[4])
        
        history_4h = data[1:49]
        swing_high_4h = max(float(k[2]) for k in history_4h)
        swing_low_4h = min(float(k[3]) for k in history_4h)
        
        # Konzervativní hranice pro výplach OI (-25 BTC za 5 minut)
        oi_drop_threshold = -25.0 

        if curr_low < swing_low_4h and curr_close > swing_low_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 BULLISH SFP POTVRZEN! Vybráno 4H Low ({swing_low_4h:.0f} USD) + OI propadl o {current_oi_change_btc:.1f} BTC!", "positive", True
            else:
                return f"Pozor: 4H Low ({swing_low_4h:.0f} USD) vybráno, ale chybí velký výplach OI ({current_oi_change_btc:+.1f} BTC / cíl -25 BTC).", "neutral", False

        if curr_high > swing_high_4h and curr_close < swing_high_4h:
            if current_oi_change_btc <= oi_drop_threshold:
                return f"🔥 BEARISH SFP POTVRZEN! Vybráno 4H High ({swing_high_4h:.0f} USD) + OI propadl o {current_oi_change_btc:.1f} BTC!", "negative", True
            else:
                return f"Pozor: 4H High ({swing_high_4h:.0f} USD) vybráno, ale chybí velký výplach OI ({current_oi_change_btc:+.1f} BTC / cíl -25 BTC).", "neutral", False

        return f"Cena se pohybuje uvnitř 4H range ({swing_low_4h:.0f} – {swing_high_4h:.0f} USD). Žádný sweep.", "neutral", False
    except Exception:
        return "API pro 4H SFP skener momentálně načítá data...", "neutral", False

# --- NAČTENÍ VŠECH DAT ---
total_pnl, win_rate = load_trading_data()
okx_cvd, okx_oi_chg, okx_cvd_series = fetch_okx_data()
hl_cvd, hl_oi_chg = fetch_hyperliquid_data()

aggregated_cvd_5m = okx_cvd + hl_cvd
aggregated_oi_change_5m = okx_oi_chg + hl_oi_chg

# --- SPUŠTĚNÍ SKENERŮ ---
setup1_msg, setup1_col, alert1_triggered = scan_setup_1(okx_cvd_series, aggregated_cvd_5m)
setup2_msg, setup2_col, alert2_triggered = scan_setup_2(aggregated_oi_change_5m)

# JEDNORÁZOVÉ PÍPNUTÍ PŘI AKTIVACI ALARMU
if alert1_triggered or alert2_triggered:
    st.markdown("""
        <audio autoplay>
          <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# --- VIZUÁLNÍ ČÁST (UI) ---
box_class_1 = "alert-box-setup1 signal-triggered" if alert1_triggered else "alert-box-setup1"
box_class_2 = "alert-box-setup2 signal-triggered" if alert2_triggered else "alert-box-setup2"

st.markdown(f"""
    <div class="{box_class_1}">
        <div class="setup-main-title" style="color: #f7931a;">⚡ SETUP 1: ABSORPCE (VARIANTY B + C)</div>
        <div class="setup-sub-text {setup1_col}">{setup1_msg}</div>
    </div>
    <div class="{box_class_2}">
        <div class="setup-main-title" style="color: #a371f7;">🎯 SETUP 2: SFP & OI OTOČKA (4H SWEEP)</div>
        <div class="setup-sub-text {setup2_col}">{setup2_msg}</div>
    </div>
""", unsafe_allow_html=True)

agg_cvd_col = "positive" if aggregated_cvd_5m >= 0 else "negative"
agg_oi_col = "positive" if aggregated_oi_change_5m >= 0 else "negative"

# GLOBÁLNÍ SOUHRN S TEPAJÍCÍM SRDCEM
st.markdown(f"""
    <div class="global-card" style="border: 1px solid #388bfd;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="metric-title" style="color: #58a6ff; font-size: 14px;">₿ GLOBÁLNÍ SOUHRN (5M OKNO)</div>
            <div><span class="beating-heart">❤️</span><span class="live-pulse-text">TRH ŽIJE</span></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 12px;">
            <div>
                <div style="font-size: 11px; color: #8b949e; font-weight: 600;">5M AGGREGATED CVD</div>
                <div class="metric-value {agg_cvd_col}">{aggregated_cvd_5m:+,.2f} BTC</div>
            </div>
            <div>
                <div style="font-size: 11px; color: #8b949e; font-weight: 600;">5M OI CHANGE</div>
                <div class="metric-value {agg_oi_col}">{aggregated_oi_change_5m:+,.2f} BTC</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# DETAILY BURZ
st.markdown('<div class="section-banner">🌐 DETAILY BURZ (V ČISTÝCH BTC)</div>', unsafe_allow_html=True)
tab_okx, tab_hl = st.tabs(["🔥 OKX (BTCUSD UM)", "💧 Hyperliquid Perp"])

with tab_okx:
    c_col = "positive" if okx_cvd >= 0 else "negative"
    o_col = "positive" if okx_oi_chg >= 0 else "negative"
    st.markdown(f"""
        <div class="global-card">
            <div style="font-size: 15px; margin-bottom: 10px;"><b>5M CVD Delta:</b> <span class="{c_col}" style="font-size: 18px; font-weight: 800;">{okx_cvd:+.2f} BTC</span></div>
            <div style="font-size: 15px;"><b>5M OI Change:</b> <span class="{o_col}" style="font-size: 18px; font-weight: 800;">{okx_oi_chg:+.2f} BTC</span></div>
        </div>
    """, unsafe_allow_html=True)

with tab_hl:
    c_col = "positive" if hl_cvd >= 0 else "negative"
    o_col = "positive" if hl_oi_chg >= 0 else "negative"
    st.markdown(f"""
        <div class="global-card">
            <div style="font-size: 15px; margin-bottom: 10px;"><b>5M CVD Delta:</b> <span class="{c_col}" style="font-size: 18px; font-weight: 800;">{hl_cvd:+.2f} BTC</span></div>
            <div style="font-size: 15px;"><b>5M OI Change:</b> <span class="{o_col}" style="font-size: 18px; font-weight: 800;">{hl_oi_chg:+.2f} BTC</span></div>
        </div>
    """, unsafe_allow_html=True)

# TRADING JOURNAL
st.markdown('<div class="section-banner" style="border-left-color: #f7931a;">📊 TRADING JOURNAL (OKX)</div>', unsafe_allow_html=True)
col1, col2 = st.columns(2)
pnl_class = "negative" if total_pnl < 0 else "positive"
pnl_text = f"-${abs(total_pnl):,.2f} USD" if total_pnl < 0 else f"+${total_pnl:,.2f} USD"

with col1:
    st.markdown(f'<div class="global-card"><div class="metric-title">CELKOVÝ VÝSLEDEK</div><div class="metric-value {pnl_class}">{pnl_text}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="global-card"><div class="metric-title">WIN RATE</div><div class="metric-value neutral">{win_rate:.2f} %</div></div>', unsafe_allow_html=True)
