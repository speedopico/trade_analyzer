import streamlit as st
import pandas as pd
import yfinance as yf
import ccxt
import requests

# 1. PAGE SETUP
st.set_page_config(page_title="Terminal Pro Analyzer", layout="centered")

# Custom CSS for a professional dark terminal theme
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #2465ff; color: white; font-weight: bold; }
    .report-container { background-color: #1e1e1e; padding: 20px; border-radius: 5px; line-height: 1.6; color: #e0e0e0; font-family: monospace; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIC ENGINE
def get_data(symbol, asset_type):
    if asset_type == "Crypto":
        symbol = f"{symbol}/USD" if "/" not in symbol else symbol
        exchange = ccxt.coinbase()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=250)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
    else:
        df = yf.download(symbol, period="2y", interval="1d", threads=False)
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        df['close'] = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Volume": "volume"})

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df.dropna(), symbol

# 3. MAIN INTERFACE
st.title("Terminal Analysis")

col1, col2 = st.columns(2)
with col1:
    account_size = st.number_input("Account Balance ($)", value=10000, step=100)
with col2:
    risk_percent = st.slider("Risk Per Trade (%)", 0.1, 5.0, 1.0, step=0.1)

col_a, col_b = st.columns([3, 1])
with col_a:
    symbol_input = st.text_input("Enter Ticker", "BTC").upper().strip()
with col_b:
    asset_class = st.selectbox("Asset Type", ["Stock", "Crypto"])

# 4. ANALYSIS EXECUTION
if st.button("GENERATE TRADE REPORT"):
    with st.spinner("Analyzing Market Structure..."):
        try:
            df, final_symbol = get_data(symbol_input, asset_class)
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
            stop_dist = price - safety_stop
            pos_size = risk_amount / stop_dist if stop_dist > 0 else 0
            pos_value = pos_size * price

            target_price = ema_200 if mean_reversion_candidate else resistance
            total_potential_profit = pos_size * (target_price - price)
            potential_pct = ((target_price - price) / price) * 100

            def green(t): return f"<span style='color: #00ff00;'>{t}</span>"
            def red(t): return f"<span style='color: #ff4b4b;'>{t}</span>"

            report = '<div class="report-container">'
            
            # 1 & 2: Header
            spot_val = green(f"${price:,.2f}") if price > ema_200 else red(f"${price:,.2f}")
            report += f"1. Ticker: {final_symbol} | Spot: {spot_val}<br>"
            report += f"2. SR Levels: [S: ${support:,.2f} | R: ${resistance:,.2f}]<br>"
            report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>"

            # 3. Technical Notation
            regime = green("Bullish") if price > ema_200 else red("Bearish")
            report += f"3. TECHNICAL NOTATION<br>Regime: {regime} (vs 200 EMA)<br>"
            report += f"Structure: {'Consolidation' if range_width < 5 else 'Wide Range'}<br><br>"

            # 4. Trend Dynamics
            d_color = green if ema_dist > 0 else red
            report += f"4. TREND DYNAMICS<br>EMA distance: {d_color(f'{ema_dist:.2f}%')}<br>"
            report += f"Mean price (200 EMA): ${ema_200:,.2f}<br><br>"

            # 5. Price Action
            vol_txt = "Surge" if vol_ratio > 1.5 else "Normal"
            report += f"5. PRICE ACTION<br>Momentum: RSI {rsi:.1f}<br>Volume Trend: {vol_txt} ({vol_ratio:.2f}x)<br><br>"

            # 6. Risk Management
            report += f"6. RISK MANAGEMENT<br>Risk Amount: {red(f'${risk_amount:,.2f}')} ({risk_percent}%)<br>"
            report += f"Safety Stop (2x ATR): {red(f'${safety_stop:,.2f}')}<br>"
            report += f"Position Size: {green(f'{pos_size:.4f} units')} (~${pos_value:,.2f})<br><br>"

            # 7. Strategy Conclusion & Alerts
            report += "7. STRATEGY CONCLUSION<br>"
            alerts = []
            if abs(ema_dist) > 50: alerts.append(red("VOLATILITY ALERT: Price extremely extended from Mean!"))
            if total_potential_profit < risk_amount and total_potential_profit > 0: alerts.append(red("POOR VALUE: Potential reward is less than the risk."))
            if price >= resistance and vol_ratio > 1.2: alerts.append(green("BULLISH BREAKOUT: Price clearing resistance on high volume!"))
            if 60 <= rsi <= 70: alerts.append(green("TREND STRENGTH: Strong momentum with room to run."))

            if price < ema_200:
                if mean_reversion_candidate: report += f"Action: {green('Speculative Long')} (Mean Reversion Play)<br>"
                else: report += red("Action: Avoid - Market structure is broken<br>")
            elif (target_price - price) / (price - support) >= 2.0 and rsi < 55:
                report += green("Action: High Conviction Long<br>")
            else: report += "Action: Neutral/Monitor<br>"
            
            if alerts: report += "<br>".join(alerts) + "<br>"
            
            # 8. Quick Summary
            report += "<br>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br><br>"
            report += "8. QUICK SUMMARY<br>"
            report += f"• Position Size: {green(f'{pos_size:.4f} units')}<br>"
            report += f"• Risk Amount:   {red(f'${risk_amount:,.2f}')}<br>"
            if total_potential_profit > 0:
                report += f"• Potential Gain: {green(f'${total_potential_profit:,.2f}')}<br>"
                report += f"• R/R Ratio:     {green(f'1 : {total_potential_profit/risk_amount:.2f}')}<br>"
                report += f"• Price Target:  ${target_price:,.2f} ({potential_pct:.2f}%)<br>"
            else: report += f"• Price Target:  ${target_price:,.2f} (Target below entry)<br>"
            report += f"• Safety Stop:   ${safety_stop:,.2f}<br>"

            report += "</div>"
            st.markdown(report, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Execution Error: {str(e)}")