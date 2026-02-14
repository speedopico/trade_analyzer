import streamlit as st
import pandas as pd
import yfinance as yf
import ccxt

# 1. COMPACT PAGE SETUP
st.set_page_config(page_title="Terminal Pro", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    h1 { font-size: 1.1rem !important; margin-bottom: 0px !important; }
    .stButton>button { height: 2.2em !important; font-size: 0.85rem !important; background-color: #2465ff; color: white; border-radius: 4px; margin-top: 10px; }
    div[data-testid="stNumberInput"], div[data-testid="stSlider"], div[data-testid="stTextInput"], div[data-testid="stSelectbox"] {
        margin-bottom: -15px !important;
    }
    .terminal-output { 
        background-color: #161b22; 
        padding: 12px; 
        border-radius: 4px; 
        border: 1px solid #30363d;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        line-height: 1.3;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIC ENGINE
def get_data(symbol, asset_type):
    if asset_type == "Crypto":
        symbol = f"{symbol}/USD" if "/" not in symbol else symbol
        exchange = ccxt.coinbase()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=250)
        if not ohlcv: return pd.DataFrame(), symbol
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
    else:
        df = yf.download(symbol, period="2y", interval="1d", threads=False)
        if df.empty: return pd.DataFrame(), symbol
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        df['close'] = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Volume": "volume"})

    # Check for empty df before moving to technicals
    if df.empty: return df, symbol

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df.dropna(), symbol

# 3. INTERFACE
st.title("Terminal Analysis")

col1, col2 = st.columns(2)
with col1: account_size = st.number_input("Balance", value=10000)
with col2: risk_percent = st.slider("Risk %", 0.1, 5.0, 1.0, step=0.1)

col_a, col_b = st.columns([2, 1])
with col_a: symbol_input = st.text_input("Ticker", "BTC").upper().strip()
with col_b: asset_class = st.selectbox("Type", ["Stock", "Crypto"])

# 4. EXECUTION
if st.button("GENERATE TRADE REPORT"):
    try:
        df, final_symbol = get_data(symbol_input, asset_class)
        
        # Check if data was actually returned
        if df.empty:
            st.error(f"No data found for {symbol_input}. Check the ticker symbol.")
        else:
            latest = df.iloc[-1]
            price, rsi, ema_200, atr = float(latest['close']), float(latest['rsi']), float(latest['ema_200']), float(latest['atr'])
            support = float(df['low'].rolling(20).min().iloc[-1])
            resistance = float(df['high'].rolling(20).max().iloc[-1])
            
            ema_dist = ((price - ema_200) / ema_200) * 100
            mean_reversion_candidate = ema_dist < -20 and rsi < 30
            range_width = ((resistance - support) / support) * 100
            vol_ratio = latest['volume'] / df['volume'].rolling(20).mean().iloc[-1]
            
            risk_amount = account_size * (risk_percent / 100)
            safety_stop = price - (atr * 2)
            # Use max(0.01, ...) to prevent division by zero errors
            stop_dist = max(0.01, price - safety_stop)
            pos_size = risk_amount / stop_dist
            pos_value = pos_size * price

            target_price = ema_200 if mean_reversion_candidate else resistance
            total_profit = pos_size * (target_price - price)
            potential_pct = ((target_price - price) / price) * 100

            def green(t): return f"<span style='color: #00ff00;'>{t}</span>"
            def red(t): return f"<span style='color: #ff4b4b;'>{t}</span>"

            report = '<div class="terminal-output">'
            report += f"1. Ticker: {final_symbol} | Spot: {green(f'${price:,.2f}') if price > ema_200 else red(f'${price:,.2f}')}<br>"
            report += f"2. SR Levels: [S: ${support:,.2f} | R: ${resistance:,.2f}]<br><br>"

            regime = green("Bullish") if price > ema_200 else red("Bearish")
            report += f"3. TECHNICAL NOTATION<br>Regime: {regime} | Structure: {'Range' if range_width < 5 else 'Wide Range'}<br><br>"

            d_color = green if ema_dist > 0 else red
            report += f"4. TREND DYNAMICS<br>EMA distance: {d_color(f'{ema_dist:.2f}%')} | Mean: ${ema_200:,.2f}<br><br>"

            vol_txt = "Surge" if vol_ratio > 1.5 else "Normal"
            report += f"5. PRICE ACTION<br>RSI: {rsi:.1f} | Volume: {vol_txt} ({vol_ratio:.2f}x)<br><br>"

            report += f"6. RISK MANAGEMENT<br>Risk: {red(f'${risk_amount:,.2f}')} ({risk_percent}%) | Stop: {red(f'${safety_stop:,.2f}')}<br>"
            report += f"Position: {green(f'{pos_size:.4f} units')} (~${pos_value:,.2f})<br><br>"

            alerts = []
            is_bullish_regime = price > ema_200
            is_pullback = 30 < rsi < 45
            is_oversold = rsi <= 30
            good_rr = (total_profit / risk_amount) >= 2.0

            if is_bullish_regime:
                if is_pullback and good_rr: action = green("BUY: Pullback in Uptrend")
                elif price >= resistance and vol_ratio > 1.3: action = green("BUY: Momentum Breakout")
                elif rsi > 70: action = red("REDUCE: Overbought / Profit Taking")
                else: action = "Monitor: Trend is Healthy"
            else:
                if mean_reversion_candidate: action = green("SPECULATIVE BUY: Deep Value Reversal")
                elif rsi < 20: action = "Monitor: Extreme Washout (Wait for Hook)"
                else: action = red("AVOID: Downtrend/Weakness")

            report += f"7. STRATEGY: {action}<br>"
            if ema_dist > 40: report += f"{red('!! DANGER: Too Extended to Swing !!')}<br>"
            if vol_ratio > 2.0 and rsi > 60: report += f"{red('!! CAUTION: Potential Blow-off Top !!')}<br>"
            if is_oversold and vol_ratio > 1.5: report += f"{green('!! OPPORTUNITY: Floor Forming !!')}<br>"
            if total_profit < risk_amount and total_profit > 0: report += f"{red('!! POOR VALUE: Reward < Risk !!')}<br>"
            report += "<br>"

            report += f"8. QUICK SUMMARY<br>"
            report += f"• Position: {green(f'{pos_size:.4f} units')}<br>"
            report += f"• Risk/Gain: {red(f'${risk_amount:,.2f}')} / {green(f'${total_profit:,.2f}')}<br>"
            if total_profit > 0:
                report += f"• R/R Ratio: {green(f'1 : {total_profit/risk_amount:.2f}')} | Target: {potential_pct:.1f}%<br>"
            report += f"• Target: ${target_price:,.2f} | Stop: ${safety_stop:,.2f}"

            report += "</div>"
            st.markdown(report, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Execution Error: {str(e)}")