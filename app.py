from flask import Flask, render_template, request, redirect, session
import sqlite3
import yfinance as yf
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# -------------------------------
# Absolute DB paths
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DB = os.path.join(BASE_DIR, 'users.db')
STOCK_DB = os.path.join(BASE_DIR, 'top_stocks.db')

# -------------------------------
# INIT DBs
# -------------------------------
def init_user_db():
    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

def init_stock_db():
    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS top10 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        name TEXT,
        price REAL,
        sector TEXT,
        market_cap TEXT,
        roi REAL,
        pe_ratio REAL
    )''')
    conn.commit()
    conn.close()

def update_top10_stocks():
    symbols = ["TCS.NS", "INFY.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
               "ITC.NS", "LT.NS", "HINDUNILVR.NS", "SBIN.NS", "KOTAKBANK.NS"]
    stocks_data = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            roi = info.get("returnOnEquity", 0) * 100
            stocks_data.append({
                "symbol": symbol.replace(".NS", ""),
                "name": info.get("shortName", symbol),
                "price": info.get("currentPrice", 0),
                "sector": info.get("sector", "N/A"),
                "market_cap": info.get("marketCap", 0),
                "roi": round(roi, 2),
                "pe_ratio": info.get("trailingPE", 0)
            })
        except:
            continue

    top10 = sorted(stocks_data, key=lambda x: x['roi'], reverse=True)[:10]

    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM top10")
    for s in top10:
        cur.execute('''INSERT INTO top10 (symbol, name, price, sector, market_cap, roi, pe_ratio)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (s['symbol'], s['name'], s['price'], s['sector'], s['market_cap'], s['roi'], s['pe_ratio']))
    conn.commit()
    conn.close()

# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = sqlite3.connect(USER_DB)
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (u, p))
            conn.commit()
        except:
            return "User already exists."
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p))
        if cur.fetchone():
            session['username'] = u
            return redirect('/dashboard')
        return "Invalid login"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM top10")
    rows = cur.fetchall()
    conn.close()

    stocks = [{
        "symbol": r[1], "name": r[2], "price": r[3],
        "sector": r[4], "market_cap": r[5],
        "roi": r[6], "pe_ratio": r[7]
    } for r in rows]

    return render_template('dashboard.html', username=session['username'], stocks=stocks)

@app.route('/refresh')
def refresh():
    update_top10_stocks()
    return redirect('/dashboard')

@app.route('/calculate', methods=['POST'])
def calculate():
    symbol = request.form['symbol']
    amount = float(request.form['amount'])

    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute("SELECT roi FROM top10 WHERE symbol=?", (symbol,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return redirect('/dashboard')

    roi = row[0] / 100
    growth = {}
    for year in range(1, 11):
        future = round(amount * ((1 + roi) ** year), 2)
        growth[year] = future

    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM top10")
    rows = cur.fetchall()
    conn.close()

    stocks = [{
        "symbol": r[1], "name": r[2], "price": r[3],
        "sector": r[4], "market_cap": r[5],
        "roi": r[6], "pe_ratio": r[7]
    } for r in rows]

    return render_template('dashboard.html', username=session['username'], stocks=stocks,
                           investment={'symbol': symbol, 'amount': amount, 'growth': growth})

@app.route('/sip', methods=['GET', 'POST'])
def sip():
    conn = sqlite3.connect(STOCK_DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM top10")
    rows = cur.fetchall()
    conn.close()

    stocks = [{
        "symbol": r[1], "name": r[2], "price": r[3],
        "sector": r[4], "market_cap": r[5],
        "roi": r[6], "pe_ratio": r[7]
    } for r in rows]

    if request.method == 'POST':
        symbol = request.form['symbol']
        monthly = float(request.form['monthly'])
        years = int(request.form['years'])

        roi = next((s['roi'] for s in stocks if s['symbol'] == symbol), 0) / 100
        values = []
        for year in range(1, years + 1):
            n = year * 12
            rate = roi / 12
            future = monthly * (((1 + rate) ** n - 1) * (1 + rate)) / rate
            values.append(round(future, 2))

        result = {
            'symbol': symbol,
            'total': round(monthly * years * 12, 2),
            'final': round(values[-1], 2),
            'labels': list(range(1, years + 1)),
            'data': values
        }
        return render_template('sip.html', stocks=stocks, result=result)

    return render_template('sip.html', stocks=stocks)

# Initialize DBs and update on server restart (optional)
init_user_db()
init_stock_db()
update_top10_stocks()  # <- Uncomment if you want to update on server restart

if __name__ == '__main__':
    app.run(debug=True)
