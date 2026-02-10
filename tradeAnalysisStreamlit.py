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
    with st.spinner("Processing data..."):
        try:
            df, final_symbol = get_data(symbol_input, asset_class)
            
            latest = df.iloc[-1]
            price = float(latest['close'])
            rsi = float(latest['rsi'])
            ema_200 = float(latest['ema_200'])
            atr = float(latest['atr'])
            support = float(df['low'].rolling(20).min().iloc[-1])
            resistance = float(df['high'].rolling(20).max().iloc[-1])
            
            range_width = ((resistance - support) / support) * 100
            volatility_pct = (atr / price) * 100
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest['volume'] / avg_vol
            p_gain, p_loss = resistance - price, price - support
            rr_ratio = p_gain / p_loss if p_loss > 0 else 0

            # UI Metrics
            st.metric(f"{final_symbol} Price", f"${price:,.2f}")
            
            tab1, tab2 = st.tabs(["Analysis Report", "Market Data"])
            
            with tab1:
                st.markdown("### Technical Notation")
                col_a, col_b = st.columns(2)
                col_a.write(f"**Regime:** {'Bullish' if price > ema_200 else 'Bearish'}")
                col_b.write(f"**Structure:** {'Consolidation' if range_width < 5 else 'Wide Range'}")
                st.write(f"**SR Levels:** Support ${support:,.2f} | Resistance ${resistance:,.2f}")
                st.write(f"**Range Width:** {range_width:.2f}%")

                st.markdown("### Price Action")
                st.write(f"**Momentum:** RSI is {rsi:.1f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})")
                st.write(f"**Volume:** {'Spike Detected' if vol_ratio > 1.5 else 'Normal participation'}")

                st.markdown("### Risk Assessment")
                st.write(f"**RR Ratio:** 1 : {rr_ratio:.2f}")
                
                if rr_ratio < 1.0:
                    st.error(f"Negative RR: Risking ${p_loss:,.2f} to make ${p_gain:,.2f}")
                elif rr_ratio >= 2.0:
                    st.success(f"Excellent RR: Reward exceeds risk by 2x or more")

                st.write(f"**Stop Loss Note:** Noise Floor at ${(price - (atr*2)):,.2f}")
                
                # Final Strategy Conclusion
                st.divider()
                if price > ema_200:
                    if rr_ratio >= 2.0 and rsi < 55:
                        st.success("Strategy: High Conviction Long")
                    elif rr_ratio < 1.0:
                        st.info("Strategy: Patience - Wait for Mean Reversion")
                    else:
                        st.info("Strategy: Mediocre Setup")
                else:
                    st.error("Strategy: Avoid - Market structure broken")

            with tab2:
                st.write("Recent Price History")
                st.dataframe(df[['open', 'high', 'low', 'close', 'rsi']].tail(10))

        except Exception as e:
            st.error(f"Error: {str(e)}")