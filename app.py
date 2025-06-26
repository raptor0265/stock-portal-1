from flask import Flask, render_template, request, redirect, session
import sqlite3
import yfinance as yf

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# -------------------------------
# INIT DBs
# -------------------------------
def init_user_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

def init_stock_db():
    conn = sqlite3.connect('top_stocks.db')
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
    symbols = {
        "TCS.NS": "TCS",
        "INFY.NS": "INFOSYS LIMITED",
        "RELIANCE.NS": "RELIANCE",
        "HDFCBANK.NS": "HDFC BANK",
        "ICICIBANK.NS": "ICICI BANK",
        "ITC.NS": "ITC LTD",
        "LT.NS": "L&T",
        "HINDUNILVR.NS": "HINDUSTAN UNILEVER",
        "SBIN.NS": "SBI",
        "KOTAKBANK.NS": "KOTAK BANK"
    }

    stocks_data = []

    for symbol, name in symbols.items():
        try:
            data = yf.download(symbol, period="6mo", interval="1d", progress=False)
            if data.empty:
                continue
            start_price = data['Close'][0]
            end_price = data['Close'][-1]
            roi = ((end_price - start_price) / start_price) * 100

            stocks_data.append({
                "symbol": symbol.replace(".NS", ""),
                "name": name,
                "price": round(end_price, 2),
                "sector": "N/A",
                "market_cap": "N/A",
                "roi": round(roi, 2),
                "pe_ratio": 0
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            continue

    # Sort and save top 10
    top10 = sorted(stocks_data, key=lambda x: x['roi'], reverse=True)[:10]

    conn = sqlite3.connect('top_stocks.db')
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
        conn = sqlite3.connect('users.db')
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
        conn = sqlite3.connect('users.db')
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

    conn = sqlite3.connect('top_stocks.db')
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

    conn = sqlite3.connect('top_stocks.db')
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

    conn = sqlite3.connect('top_stocks.db')
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
    conn = sqlite3.connect('top_stocks.db')
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

# Initialize DBs and auto-refresh top 10 stocks
init_user_db()
init_stock_db()
update_top10_stocks()  # auto-refresh top stocks on startup

if __name__ == '__main__':
    # For deployment, you might want to bind to 0.0.0.0 and port from env var
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
