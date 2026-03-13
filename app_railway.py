"""
ForexAI Signal Bot — Railway Server
Signal engine online 24 jam
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import random, os
from datetime import datetime
import traceback

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/api/*": {"origins": "*"}})

BASE_PRICES = {
    "EUR/USD": 1.08342, "GBP/USD": 1.26580, "USD/JPY": 149.820,
    "AUD/USD": 0.64210, "USD/CAD": 1.35890, "GBP/JPY": 189.640,
    "EUR/GBP": 0.85540, "XAU/USD": 3150.00,
}
_price_state = {k: v for k, v in BASE_PRICES.items()}

def get_sim_price(pair):
    base  = _price_state.get(pair, 1.0)
    drift = base * random.uniform(-0.0003, 0.0003)
    new   = round(base + drift, 2 if "XAU" in pair else (3 if "JPY" in pair else 5))
    _price_state[pair] = new
    return new

def generate_signal_data(pair, style, price):
    is_gold = "XAU" in pair
    is_jpy  = "JPY" in pair
    pip  = price * (0.0008 if is_gold else 0.0015 if is_jpy else 0.004)
    mult = {"SCALP": 0.35, "DAYTRADE": 1.0, "SWING": 2.8}.get(style, 1.0)
    rsi  = random.uniform(25, 75)
    bull = rsi < 52
    sl   = price - pip*mult   if bull else price + pip*mult
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
    return jsonify([{"pair":p,"price":get_sim_price(p),
                     "change_pct":round(random.uniform(-0.4,0.5),2),
                     "up":random.choice([True,False])} for p in BASE_PRICES])

@app.route("/api/price/<path:pair>")
def one_price(pair):
    p = pair.replace("-","/").upper()
    return jsonify({"pair":p,"price":get_sim_price(p),"source":"simulation","time":datetime.now().strftime("%H:%M:%S")})

@app.route("/api/signal/generate", methods=["POST","OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        data  = request.get_json(force=True, silent=True) or {}
        pair  = data.get("pair","EUR/USD")
        style = data.get("style","DAYTRADE").upper()
        raw   = data.get("price")
        try:    price = float(str(raw).replace(",",".")) if raw else get_sim_price(pair)
        except: price = get_sim_price(pair)
        print(f"📊 {pair} | {style} | {price}")
        sig = generate_signal_data(pair, style, price)
        print(f"✅ {sig['direction']} Entry:{sig['entry_price']} SL:{sig['sl']} TP2:{sig['tp2']}")
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
    app.run(host="0.0.0.0", port=port, debug=False)
