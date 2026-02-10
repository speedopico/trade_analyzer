import streamlit as st
import pandas as pd
import yfinance as yf
import ccxt
import requests # Add this at the top

def get_data(symbol, asset_type):
    # Create a session with a browser-like header
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    if asset_type == "Crypto":
        # ... (keep your CCXT crypto code the same)
        pass 
    else:
        # Pass the session to yfinance
        df = yf.download(symbol, period="2y", interval="1d", session=session, threads=False)
        # ... (rest of your logic)

# 1. Page Setup
st.set_page_config(page_title="Trader Analyzer", layout="centered")

# Custom CSS for a professional dark terminal theme
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #2465ff; color: white; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #00e5ff !important; }
    .report-section { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("Trader Analyzer Pro")

# 2. Input Section
with st.container():
    col1, col2 = st.columns([2, 1])
    with col1:
        symbol_input = st.text_input("Ticker Symbol", value="BTC").upper().strip()
    with col2:
        asset_class = st.selectbox("Type", ["Stock", "Crypto"])

# 3. Logic Engine
def get_data(symbol, asset_type):
    if asset_type == "Crypto":
        symbol = f"{symbol}/USD" if "/" not in symbol else symbol
        exchange = ccxt.coinbase()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=250)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
    else:
        df = yf.download(symbol, period="2y", interval="1d")
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        df['close'] = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Volume": "volume"})

    # Indicator Calculations
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df.dropna(), symbol

# 4. Analysis Execution
if st.button("GENERATE TRADE REPORT"):
    with st.spinner("Fetching Market Data..."):
        try:
            df, final_symbol = get_data(symbol_input, asset_class)
            
            # Logic calculations
            latest = df.iloc[-1]
            price = float(latest['close'])
            rsi = float(latest['rsi'])
            ema_200 = float(latest['ema_200'])
            atr = float(latest['atr'])
            support = float(df['low'].rolling(20).min().iloc[-1])
            resistance = float(df['high'].rolling(20).max().iloc[-1])
            
            # --- CALCULATE TREND STRENGTH ---
            ema_dist = ((price - ema_200) / ema_200) * 100
            # If positive, we are X% above. If negative, we are X% below.
            # Mean Reversion Logic
            # Triggered if we are more than 20% below the EMA (oversold bounce potential)
            mean_reversion_candidate = ema_dist < -20 and rsi < 30
            
            range_width = ((resistance - support) / support) * 100
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest['volume'] / avg_vol
            p_gain, p_loss = resistance - price, price - support
            rr_ratio = p_gain / p_loss if p_loss > 0 else 0

            # --- STYLE HELPERS ---
            def green(text): return f"<span style='color: #00ff00;'>{text}</span>"
            def red(text): return f"<span style='color: #ff4b4b;'>{text}</span>"

            # --- 1. INITIALIZE REPORT CONTAINER ---
            report = '<div style="font-family: monospace; background-color: #1e1e1e; padding: 20px; border-radius: 5px; line-height: 1.6; color: #e0e0e0;">'

            # --- 2. HEADER SECTION ---
            spot_val = green(f"${price:,.2f}") if price > ema_200 else red(f"${price:,.2f}")
            report += f"Ticker: {final_symbol} | Spot: {spot_val}<br>"
            report += f"SR Levels: [S: ${support:,.2f} | R: ${resistance:,.2f}]<br>"
            report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>"

            # --- 3. TECHNICAL NOTATION ---
            regime_status = green("Bullish") if price > ema_200 else red("Bearish")
            report += "TECHNICAL NOTATION<br>"
            report += f"Regime: {regime_status} (vs 200 EMA)<br>"
            report += f"Structure: {'Consolidation' if range_width < 5 else 'Wide Range'}<br><br>"

            # --- 4. TREND DYNAMICS ---
            dist_color = green if ema_dist > 0 else red
            report += "TREND DYNAMICS<br>"
            report += f"EMA distance: {dist_color(f'{ema_dist:.2f}%')}<br>"
            report += f"Mean price (200 EMA): {green(f'${ema_200:,.2f}') if price < ema_200 else red(f'${ema_200:,.2f}')}<br>"
            
            if mean_reversion_candidate:
                report += f"Alert: {green('Extreme extension detected')} - mean reversion likely<br>"
                report += f"Target: Potential bounce toward ${ema_200:,.2f}<br>"
            elif abs(ema_dist) > 15:
                report += f"Note: {red('Extended')} from average price<br>"
            else:
                report += "Note: Price is near the mean<br>"
            report += "<br>"

            # --- 5. PRICE ACTION ---
            rsi_val = red(f"{rsi:.1f}") if rsi > 70 or rsi < 30 else green(f"{rsi:.1f}")
            report += "PRICE ACTION<br>"
            report += f"Momentum: RSI is {rsi_val}<br>"
            report += f"Volume: {'Spike detected' if vol_ratio > 1.5 else 'Normal participation'}<br><br>"

            # --- 6. RISK MANAGEMENT ---
            rr_val = green(f"1 : {rr_ratio:.2f}") if rr_ratio >= 2.0 else red(f"1 : {rr_ratio:.2f}")
            risk_text = red(f"${p_loss:,.2f}")
            reward_text = green(f"${p_gain:,.2f}")
            
            # Calculate a 2x ATR Stop Loss
            safety_stop = price - (atr * 2)
            
            report += "RISK MANAGEMENT<br>"
            report += f"R/R ratio: {rr_val}<br>"
            report += f"Risk: {risk_text} | Reward: {reward_text}<br>"
            report += f"Safety stop (2x ATR): {red(f'${safety_stop:,.2f}')}<br><br>"

            # --- 7. STRATEGY CONCLUSION ---
            report += "STRATEGY CONCLUSION<br>"
            if price < ema_200:
                if mean_reversion_candidate:
                    report += f"Action: {green('Speculative Long')} (Mean Reversion Play)<br>"
                    report += f"Exit if price drops below {red(f'${safety_stop:,.2f}')}"
                else:
                    report += red("Action: Avoid - Market structure is broken")
            elif rr_ratio >= 2.0 and rsi < 55:
                report += green("Action: High Conviction Long")
            elif rr_ratio < 1.0:
                report += red("Action: Patience - Wait for a deeper dip")
            else:
                report += "Action: Mediocre setup - No clear edge"

            # --- 8. CLOSE AND RENDER ---
            report += "</div>"
            st.markdown(report, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Execution Error: {str(e)}")