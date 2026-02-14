import streamlit as st
import pandas as pd
import yfinance as yf
import ccxt
from edgar import Company

# 1. PAGE SETUP
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

# 2. DATA ENGINE
def get_data(symbol, asset_type):
    if asset_type == "Crypto":
        symbol = f"{symbol}/USD" if "/" not in symbol else symbol
        exchange = ccxt.coinbase()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=250)
        if not ohlcv:
            return pd.DataFrame(), symbol
        df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
    else:
        df = yf.download(symbol, period="2y", interval="1d", threads=False)
        if df.empty:
            return pd.DataFrame(), symbol
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df["close"] = df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Volume":"volume"})

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss))
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df.dropna(), symbol

# 3. FUNDAMENTALS (EDGAR)
@st.cache_data(show_spinner=False)
def get_income_statement(ticker):
    try:
        company = Company(ticker)
        income = company.financials.income_statement.annual
        if income is None or income.empty:
            income = company.financials.income_statement.quarterly
        if income is None or income.empty:
            return None

        latest = income.iloc[-1]
        revenue = latest.get("Revenues")
        gross = latest.get("GrossProfit")
        operating = latest.get("OperatingIncome")
        net = latest.get("NetIncomeLoss")

        if not revenue or revenue == 0:
            return None

        return {
            "revenue": revenue,
            "gross": gross,
            "operating": operating,
            "net": net,
            "gross_margin": gross / revenue if gross else None,
            "operating_margin": operating / revenue if operating else None,
            "net_margin": net / revenue if net else None
        }
    except Exception:
        return None

# 4. UI
st.title("Terminal Analysis")

c1, c2 = st.columns(2)
with c1:
    account_size = st.number_input("Balance", value=10000)
with c2:
    risk_percent = st.slider("Risk %", 0.1, 5.0, 1.0, step=0.1)

c3, c4 = st.columns([2,1])
with c3:
    symbol_input = st.text_input("Ticker", "AAPL").upper().strip()
with c4:
    asset_class = st.selectbox("Type", ["Stock", "Crypto"])

# 5. EXECUTION
if st.button("GENERATE TRADE REPORT"):
    df, final_symbol = get_data(symbol_input, asset_class)

    if df.empty:
        st.error("No market data available.")
    else:
        latest = df.iloc[-1]
        price = latest["close"]
        ema_200 = latest["ema_200"]
        rsi = latest["rsi"]
        atr = latest["atr"]

        support = df["low"].rolling(20).min().iloc[-1]
        resistance = df["high"].rolling(20).max().iloc[-1]

        risk_amount = account_size * (risk_percent / 100)
        stop = price - (atr * 2)
        stop_dist = max(0.01, price - stop)
        pos_size = risk_amount / stop_dist

        report = "<div class='terminal-output'>"
        report += f"1. PRICE<br>Spot: ${price:,.2f} | EMA200: ${ema_200:,.2f}<br><br>"
        report += f"2. LEVELS<br>Support: ${support:,.2f} | Resistance: ${resistance:,.2f}<br><br>"
        report += f"3. MOMENTUM<br>RSI: {rsi:.1f} | ATR: {atr:.2f}<br><br>"

        # FUNDAMENTAL ANALYSIS
        if asset_class == "Stock":
            pnl = get_income_statement(symbol_input)
            report += "4. FUNDAMENTALS (EDGAR)<br>"

            if pnl:
                def pct(x): return "N/A" if x is None else f"{x*100:.1f}%"
                def bil(x): return f"${x/1e9:,.2f}B"

                report += f"Revenue: {bil(pnl['revenue'])}<br>"
                report += f"Gross Margin: {pct(pnl['gross_margin'])}<br>"
                report += f"Operating Margin: {pct(pnl['operating_margin'])}<br>"
                report += f"Net Margin: {pct(pnl['net_margin'])}<br>"

                weak_fundamentals = (
                    (pnl["net"] is not None and pnl["net"] < 0) or
                    (pnl["operating_margin"] is not None and pnl["operating_margin"] < 0)
                )

                report += "<br>Fundamental Regime: "
                report += "WEAK ⚠️<br><br>" if weak_fundamentals else "HEALTHY ✅<br><br>"
            else:
                report += "No reliable filing data<br><br>"

        report += f"5. RISK<br>Position Size: {pos_size:.2f} units<br>"
        report += f"Risk: ${risk_amount:,.2f} | Stop: ${stop:,.2f}<br>"

        report += "</div>"
        st.markdown(report, unsafe_allow_html=True)
