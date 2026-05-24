import ccxt
import pandas as pd
import requests
import time
from datetime import datetime
import os

WEBHOOK_URL = "https://discord.com/api/webhooks/1507873992885666012/hbwHomkZwq9CyaLF94Ocw4hioDx0uy9nfDErmPw2r9BJoj2hLmww9ZV6HwhN6_nyQM12"
COINS = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "ZEC": "ZEC/USDT",
    "SOL": "SOL/USDT",
    "BNB": "BNB/USDT",
}

exchange = ccxt.kucoin()


def send_discord(coin, data):
    try:
        color = 3066993 if data["signal"] == "BUY" else 15158332
        emoji = "🟢" if data["signal"] == "BUY" else "🔴"
        embed = {
            "embeds": [{
                "title": f"{emoji} {coin}/USDT — {data['signal']} SIGNAL",
                "color": color,
                "fields": [
                    {"name": "📊 Signal",    "value": f"**{data['signal']}**", "inline": True},
                    {"name": "💰 Price",     "value": f"`{data['entry']}`",    "inline": True},
                    {"name": "⚖️ R:R",       "value": "1 : 3",                "inline": True},
                    {"name": "🎯 TP 1",      "value": f"`{data['tp1']}`",      "inline": True},
                    {"name": "🎯 TP 2",      "value": f"`{data['tp2']}`",      "inline": True},
                    {"name": "🎯 TP 3",      "value": f"`{data['tp3']}`",      "inline": True},
                    {"name": "🛑 Stop Loss", "value": f"`{data['sl']}`",       "inline": True},
                    {"name": "📈 RSI",       "value": f"{data['rsi']}",        "inline": True},
                    {"name": "⏰ Time",      "value": f"{data['time']}",       "inline": True},
                    {"name": "Score",
                     "value": f"🟢 BUY: {data['buy_score']}/8  |  🔴 SELL: {data['sell_score']}/8",
                     "inline": False},
                ],
                "footer": {"text": "Crypto Signal Bot — by Claude"}
            }]
        }
        r = requests.post(WEBHOOK_URL, json=embed, timeout=30)
        if r.status_code == 204:
            print(f"✅ Signal bheja: {coin} {data['signal']}")
        else:
            print(f"❌ Discord error: {r.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")


def get_ohlcv(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, "4h", limit=100)
        df = pd.DataFrame(
            ohlcv,
            columns=["time", "open", "high", "low", "close", "volume"]
        )
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        return df
    except Exception as e:
        print(f"❌ Data error {symbol}: {e}")
        return None


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(series):
    ema12  = calculate_ema(series, 12)
    ema26  = calculate_ema(series, 26)
    macd   = ema12 - ema26
    signal = calculate_ema(macd, 9)
    return macd, signal


def calculate_bb(series, period=20, mult=2.0):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + mult * std, sma, sma - mult * std


def calculate_supertrend(df, period=10, factor=3.0):
    hl2       = (df["high"] + df["low"]) / 2
    atr       = (df["high"] - df["low"]).rolling(period).mean()
    upper     = hl2 + factor * atr
    lower     = hl2 - factor * atr
    direction = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction


def analyze_signal(symbol):
    df = get_ohlcv(symbol)
    if df is None or len(df) < 50:
        return None

    close   = df["close"]
    high    = df["high"]
    low     = df["low"]
    volume  = df["volume"]

    ema9    = calculate_ema(close, 9)
    ema21   = calculate_ema(close, 21)
    ema50   = calculate_ema(close, 50)
    rsi     = calculate_rsi(close)
    macd, macd_sig        = calculate_macd(close)
    bb_up, bb_mid, bb_low = calculate_bb(close)
    st_dir  = calculate_supertrend(df)
    avg_vol = volume.rolling(20).mean()

    c    = float(close.iloc[-1])
    e9   = float(ema9.iloc[-1])
    e21  = float(ema21.iloc[-1])
    e50  = float(ema50.iloc[-1])
    r    = float(rsi.iloc[-1])
    m    = float(macd.iloc[-1])
    ms   = float(macd_sig.iloc[-1])
    bbu  = float(bb_up.iloc[-1])
    bbl  = float(bb_low.iloc[-1])
    st   = int(st_dir.iloc[-1])
    vol  = float(volume.iloc[-1])
    avol = float(avg_vol.iloc[-1])
    ph   = float(high.iloc[-10:].max())
    pl   = float(low.iloc[-10:].min())
    atr  = float((high - low).rolling(14).mean().iloc[-1])

    b1 = e9 > e21 and e21 > e50
    b2 = float(ema9.iloc[-2]) < float(ema21.iloc[-2]) and e9 > e21
    b3 = 50 < r < 70
    b4 = m > ms
    b5 = vol > avol * 1.5
    b6 = c > ph
    b7 = st == 1
    b8 = c < bbl
    buy_score = sum([b1, b2, b3, b4, b5, b6, b7, b8])

    s1 = e9 < e21 and e21 < e50
    s2 = float(ema9.iloc[-2]) > float(ema21.iloc[-2]) and e9 < e21
    s3 = 30 < r < 50
    s4 = m < ms
    s5 = vol > avol * 1.5
    s6 = c < pl
    s7 = st == -1
    s8 = c > bbu
    sell_score = sum([s1, s2, s3, s4, s5, s6, s7, s8])

    strong_buy  = b6 and b5 and b4 and b7 and r > 45
    strong_sell = s6 and s5 and s4 and s7 and r < 55

    if buy_score >= 5 or strong_buy:
        signal = "BUY"
    elif sell_score >= 5 or strong_sell:
        signal = "SELL"
    else:
        signal = "WAIT"

    if signal == "BUY":
        tp1 = round(c + atr * 1.5, 2)
        tp2 = round(c + atr * 3.0, 2)
        tp3 = round(c + atr * 5.0, 2)
        sl  = round(c - atr * 1.5, 2)
    elif signal == "SELL":
        tp1 = round(c - atr * 1.5, 2)
        tp2 = round(c - atr * 3.0, 2)
        tp3 = round(c - atr * 5.0, 2)
        sl  = round(c + atr * 1.5, 2)
    else:
        tp1 = tp2 = tp3 = sl = "--"

    return {
        "signal":     signal,
        "entry":      round(c, 2),
        "tp1":        tp1,
        "tp2":        tp2,
        "tp3":        tp3,
        "sl":         sl,
        "rsi":        round(r, 1),
        "buy_score":  buy_score,
        "sell_score": sell_score,
        "time":       datetime.now().strftime("%H:%M %d-%b"),
    }


def main():
    print("=" * 40)
    print("  CRYPTO SIGNAL BOT — KuCoin")
    print(f"  {datetime.now().strftime('%H:%M %d-%b')}")
    print("=" * 40)

    # Test message
    requests.post(WEBHOOK_URL, json={
        "content": "🤖 **Bot Start Ho Gaya — KuCoin API**"
    }, timeout=30)

    while True:
        print(f"\n🔍 Scan: {datetime.now().strftime('%H:%M')}")
        for coin, symbol in COINS.items():
            print(f"{coin} check ho raha hai...")
            data = analyze_signal(symbol)
            if not data:
                print(f"❌ {coin}: Data nahi mila")
                continue
            print(
                f"✅ {coin}: {data['signal']} | "
                f"Price: {data['entry']} | "
                f"BUY: {data['buy_score']}/8 | "
                f"SELL: {data['sell_score']}/8"
            )
            if data["signal"] != "WAIT":
                send_discord(coin, data)
            time.sleep(2)

        print("⏳ Agla scan 4 ghante baad...")
        time.sleep(14400)


if __name__ == "__main__":
    main()
