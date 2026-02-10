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
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest['volume'] / avg_vol
            p_gain, p_loss = resistance - price, price - support
            rr_ratio = p_gain / p_loss if p_loss > 0 else 0

            # Price Display
            st.metric(f"{final_symbol} Current Price", f"${price:,.2f}")
            
            tab1, tab2 = st.tabs(["Analysis Report", "Market Data"])
            
            with tab1:
                # SECTION 1: TECHNICAL NOTATION
                st.markdown("---")
                st.markdown("<h3 style='color: #2465ff; text-transform: uppercase;'>Technical Notation</h3>", unsafe_allow_html=True)
                
                with st.container():
                    c1, c2 = st.columns(2)
                    with c1:
                        regime_color = "#00ff00" if price > ema_200 else "#ff4b4b"
                        st.markdown(f"**REGIME:** <span style='color: {regime_color}; font-weight: bold;'>{ 'BULLISH' if price > ema_200 else 'BEARISH' }</span>", unsafe_allow_html=True)
                        st.markdown(f"**STRUCTURE:** `{ 'CONSOLIDATION' if range_width < 5 else 'WIDE RANGE' }`", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"**RANGE WIDTH:** `{range_width:.2f}%`", unsafe_allow_html=True)
                        st.markdown(f"**SR LEVELS:** `${support:,.2f}` | `${resistance:,.2f}`", unsafe_allow_html=True)

                # SECTION 2: PRICE ACTION
                st.markdown("<h3 style='color: #00e5ff; text-transform: uppercase;'>Price Action</h3>", unsafe_allow_html=True)
                with st.container():
                    c1, c2 = st.columns(2)
                    with c1:
                        rsi_color = "#ff4b4b" if rsi > 70 or rsi < 30 else "#00ff00"
                        st.markdown(f"**MOMENTUM:** RSI IS <span style='color: {rsi_color}; font-weight: bold;'>{rsi:.1f}</span>", unsafe_allow_html=True)
                    with c2:
                        vol_color = "#00e5ff" if vol_ratio > 1.5 else "#e0e0e0"
                        st.markdown(f"**VOLUME:** <span style='color: {vol_color}; font-weight: bold;'>{ 'SPIKE DETECTED' if vol_ratio > 1.5 else 'NORMAL' }</span>", unsafe_allow_html=True)

                # SECTION 3: RISK ASSESSMENT
                st.markdown("<h3 style='color: #ffaa00; text-transform: uppercase;'>Risk Assessment</h3>", unsafe_allow_html=True)
                with st.container():
                    st.markdown(f"**RR RATIO:** `1 : {rr_ratio:.2f}`")
                    if rr_ratio < 1.0:
                        st.warning(f"NEGATIVE RR: Risking ${p_loss:,.2f} to make ${p_gain:,.2f}")
                    elif rr_ratio >= 2.0:
                        st.success(f"EXCELLENT RR: Reward exceeds risk by 2x")
                    
                    st.markdown(f"**STOP LOSS NOTE:** Noise Floor at :red[`${(price - (atr*2)):,.2f}`]")
                
                # FINAL STRATEGY CONCLUSION
                st.divider()
                if price > ema_200:
                    if rr_ratio >= 2.0 and rsi < 55:
                        st.success("STRATEGY: HIGH CONVICTION LONG")
                    elif rr_ratio < 1.0:
                        st.info("STRATEGY: PATIENCE - WAIT FOR MEAN REVERSION")
                    else:
                        st.info("STRATEGY: MEDIOCRE SETUP")
                else:
                    st.error("STRATEGY: AVOID - MARKET STRUCTURE BROKEN")

            with tab2:
                st.subheader("Recent Price History")
                st.dataframe(df[['open', 'high', 'low', 'close', 'rsi']].tail(10), use_container_width=True)

        except Exception as e:
            st.error(f"Analysis Failed: {str(e)}")