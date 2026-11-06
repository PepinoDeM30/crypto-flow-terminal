# --- ALGORITMUS SETUP 1 (ABSORPCE) - POUZE FUTURES ---
def scan_setup_1():
    try:
        # Striktně Binance FUTURES API
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=5", headers=headers, timeout=4).json()
        
        if not isinstance(res, list) or len(res) < 5:
            return "Nedostatek dat pro analýzu trhu.", "neutral"

        klines = []
        for k in res:
            h = float(k[2])
            l = float(k[3])
            vol = float(k[5])
            tb_vol = float(k[9])  # Taker Buy Volume (Futures)
            ts_vol = vol - tb_vol # Taker Sell Volume (Futures)
            cvd = tb_vol - ts_vol # CVD delta svíčky
            klines.append({"h": h, "l": l, "cvd": cvd})

        # Sledované okno: Poslední 3 svíčky
        window = klines[2:5]
        hh = max(k["h"] for k in window)
        ll = min(k["l"] for k in window)
        
        if ll == 0:
            return "Chyba výpočtu ceny.", "neutral"
            
        price_range_pct = ((hh - ll) / ll) * 100

        # Brána 1: Cenová past (Max 0.30% range)
        if price_range_pct > 0.30:
            return f"Žádný signál. Trh trenduje / není uzamčen (Range: {price_range_pct:.2f}%).", "neutral"

        # Brána 2 a 3: Skenování extrémů CVD uvnitř pasti
        for i in range(2, 5):
            prev_cvd = klines[i-1]["cvd"]
            curr_cvd = klines[i]["cvd"]

            safe_prev_cvd = prev_cvd if abs(prev_cvd) >= 1 else (1 if prev_cvd >= 0 else -1)
            ratio = abs(curr_cvd) / abs(safe_prev_cvd)

            # Pojistka 100 BTC pro Futures
            if ratio >= 5.0 and abs(curr_cvd) >= 100.0:
                direction = "BEARISH" if curr_cvd > 0 else "BULLISH"
                col = "negative" if direction == "BEARISH" else "positive"
                action = "Kupci absorbováni!" if direction == "BEARISH" else "Prodejci absorbováni!"
                return f"🔥 SETUP 1: {direction} ABSORPCE! Zámek {price_range_pct:.2f}%, CVD {curr_cvd:+.0f} BTC ({ratio:.1f}x). {action}", col

        return f"Cena je uzamčena (Range: {price_range_pct:.2f}%), čekám na CVD explozi...", "neutral"

    except Exception:
        return "API Binance Futures je momentálně nedostupné (blokace serveru).", "neutral"


# --- BURZY (5M CVD & OI) - POUZE FUTURES ---
def fetch_binance_data():
  try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    # Striktně Binance Futures OI
    oi_url = "https://fapi.binance.com/fapi/v1/openInterestHist?symbol=BTCUSDT&period=5m&limit=2"
    oi_hist = requests.get(oi_url, headers=headers, timeout=3).json()
    oi_change = 0.0
    if isinstance(oi_hist, list) and len(oi_hist) >= 2:
      oi_change = float(oi_hist[-1]["sumOpenInterest"]) - float(oi_hist[-2]["sumOpenInterest"])

    # Striktně Binance Futures CVD
    klines_url = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=2"
    klines = requests.get(klines_url, headers=headers, timeout=3).json()
    cvd_5m = 0.0
    if isinstance(klines, list) and len(klines) >= 2:
        k = klines[0]
        tb_vol = float(k[9])
        ts_vol = float(k[5]) - tb_vol
        cvd_5m = tb_vol - ts_vol
        
    return cvd_5m, oi_change, True
  except Exception:
    return 0.0, 0.0, False
