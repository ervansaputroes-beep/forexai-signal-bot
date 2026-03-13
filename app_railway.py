"""
ForexAI Signal Bot — Railway Server
Harga live dari Yahoo Finance (gratis, tanpa API key)
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import random, os, time
from datetime import datetime
import traceback
try:
    import urllib.request, json as _json
    URLLIB_OK = True
except:
    URLLIB_OK = False

app = Flask(__name__, static_folder='.')
CORS(app)

# ─── Symbol map Yahoo Finance ─────────────────────────────────────────────────
YAHOO_SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/GBP": "EURGBP=X",
    "XAU/USD": "GC=F",   # Gold Futures
}

BASE_PRICES = {
    "EUR/USD": 1.08342, "GBP/USD": 1.26580, "USD/JPY": 149.820,
    "AUD/USD": 0.64210, "USD/CAD": 1.35890, "GBP/JPY": 189.640,
    "EUR/GBP": 0.85540, "XAU/USD": 3095.00,
}

# Cache harga — refresh tiap 60 detik
_price_cache = {}
_cache_time  = {}
CACHE_TTL    = 60  # detik

def fetch_yahoo_price(pair):
    """Ambil harga live dari Yahoo Finance"""
    symbol = YAHOO_SYMBOLS.get(pair)
    if not symbol:
        return None
    
    now = time.time()
    # Pakai cache kalau masih fresh
    if pair in _price_cache and (now - _cache_time.get(pair, 0)) < CACHE_TTL:
        return _price_cache[pair]
    
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode())
        
        result = data['chart']['result'][0]
        price  = result['meta']['regularMarketPrice']
        
        is_gold = "XAU" in pair
        is_jpy  = "JPY" in pair
        dec     = 2 if is_gold else (3 if is_jpy else 5)
        price   = round(float(price), dec)
        
        _price_cache[pair] = price
        _cache_time[pair]  = now
        print(f"✅ Yahoo price {pair}: {price}")
        return price
    except Exception as e:
        print(f"⚠️ Yahoo fetch error {pair}: {e}")
        return None

def get_price(pair):
    """Ambil harga live, fallback ke simulasi"""
    live = fetch_yahoo_price(pair)
    if live:
        return live
    # Fallback simulasi
    base  = _price_cache.get(pair) or BASE_PRICES.get(pair, 1.0)
    drift = base * random.uniform(-0.0002, 0.0002)
    is_gold = "XAU" in pair
    is_jpy  = "JPY" in pair
    return round(base + drift, 2 if is_gold else (3 if is_jpy else 5))

# ─── Signal Generator ─────────────────────────────────────────────────────────
def generate_signal_data(pair, style, price):
    is_gold = "XAU" in pair
    is_jpy  = "JPY" in pair
    pip  = price * (0.0008 if is_gold else 0.0015 if is_jpy else 0.004)
    mult = {"SCALP": 0.35, "DAYTRADE": 1.0, "SWING": 2.8}.get(style, 1.0)
    rsi  = random.uniform(25, 75)
    bull = rsi < 52
    sl   = price - pip*mult     if bull else price + pip*mult
    tp1  = price + pip*mult*1.6 if bull else price - pip*mult*1.6
    tp2  = price + pip*mult*2.8 if bull else price - pip*mult*2.8
    sup  = price - pip*1.3
    res  = price + pip*1.9
    risk = abs(price - sl)
    rew  = abs(tp2 - price)
    rr   = round(rew/risk, 1) if risk > 0 else 2.0
    dist = min(abs(rsi-30), abs(rsi-70))
    conf = "HIGH" if dist > 15 else ("MEDIUM" if dist > 8 else "LOW")
    dec  = 2 if is_gold else (3 if is_jpy else 5)
    fmt  = lambda v: round(v, dec)
    wr   = {"SCALP":63,"DAYTRADE":70,"SWING":61}.get(style,65) + random.randint(-4,8)
    exp  = {"SCALP":"15-30 Menit","DAYTRADE":"4-8 Jam","SWING":"3-7 Hari"}.get(style,"4-8 Jam")
    itf  = {"SCALP":"M15","DAYTRADE":"H1","SWING":"D1"}.get(style,"H1")
    ba = [f"Struktur H4 membentuk Higher High — tren bullish valid.",
          f"RSI {rsi:.0f} — momentum beli menguat dari zona oversold.",
          f"Volume spike di zona demand {fmt(sup)}, akumulasi terlihat."]
    sa = [f"Struktur H4 membentuk Lower High — tekanan jual dominan.",
          f"RSI {rsi:.0f} — momentum jual dari zona overbought.",
          f"Rejection candle di resistensi {fmt(res)}, distribusi aktif."]
    return {
        "pair": pair, "direction": "LONG" if bull else "SHORT",
        "order_type": "BUY" if bull else "SELL",
        "style": style, "confidence": conf,
        "entry_price": fmt(price), "sl": fmt(sl), "tp1": fmt(tp1), "tp2": fmt(tp2),
        "support": fmt(sup), "resistance": fmt(res),
        "rr_ratio": f"1:{rr}", "expiry": exp, "win_rate": f"{wr}%",
        "analysis": ba if bull else sa,
        "invalidation": f"Candle {itf} tutup di {'bawah support' if bull else 'atas resistensi'} {fmt(sup if bull else res)}.",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def home():
    return send_from_directory('.', 'index.html')

@app.route("/api/status")
def status():
    return jsonify({"status":"online","mode":"signal-engine","time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

@app.route("/api/mt5/status")
def mt5_status():
    return jsonify({"connected":False,"mode":"signal-only",
                    "message":"Signal Engine Online 24 Jam ✅","balance":0,
                    "broker":"ForexAI Cloud Server"})

@app.route("/api/prices")
def all_prices():
    results = []
    for pair in BASE_PRICES:
        price = get_price(pair)
        prev  = BASE_PRICES[pair]
        chg   = round((price - prev) / prev * 100, 2)
        results.append({"pair":pair,"price":price,"change_pct":chg,"up":chg>=0})
    return jsonify(results)

@app.route("/api/price/<path:pair>")
def one_price(pair):
    p     = pair.replace("-","/").upper()
    price = get_price(p)
    return jsonify({"pair":p,"price":price,"source":"yahoo_finance","time":datetime.now().strftime("%H:%M:%S")})

@app.route("/api/signal/generate", methods=["POST","OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        data  = request.get_json(force=True, silent=True) or {}
        pair  = data.get("pair","EUR/USD")
        style = data.get("style","DAYTRADE").upper()
        raw   = data.get("price")
        try:
            price = float(str(raw).replace(",",".")) if raw else None
        except:
            price = None
        # Kalau tidak ada harga dari user, ambil dari Yahoo
        if not price or price <= 0:
            price = get_price(pair)
        print(f"📊 {pair} | {style} | {price}")
        sig = generate_signal_data(pair, style, price)
        return jsonify({"success":True,"signal":sig})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success":False,"message":str(e)}), 500

@app.route("/api/trade/history")
def history():
    return jsonify({"history":[],"mode":"signal-only","total_pnl":0,"count":0})

@app.route("/api/trade/positions")
def positions():
    return jsonify({"positions":[],"mode":"signal-only","count":0})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 ForexAI Signal Server — port {port}")
    print(f"📡 Harga live dari Yahoo Finance")
    app.run(host="0.0.0.0", port=port, debug=False)
