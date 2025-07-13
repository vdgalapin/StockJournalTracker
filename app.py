from flask import Flask, redirect, request, g, render_template, make_response
from datetime import date, datetime
from logic.gain_loss import calculate_gain, fetch_trades
from logic.wash_sale import detect_wash_sale    
import yfinance as yf
import csv
import sqlite3
import os

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), 'database.db')

@app.route('/')
def hello():
    return render_template('index.html')

def get_db():
    """Connect to the database and return the connection."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # Enable row factory for dict-like access
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close the database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()
        
def init_db():
    """Initialize the database with the schema."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.executescript(f.read())
    db.commit()
    
@app.route('/stocks')
def get_stocks():
    """Retrieve all stocks from the database."""
    db = get_db()
    cursor = db.execute('SELECT * FROM stocks')
    stocks = cursor.fetchall()
    return {'stocks': [dict(stock) for stock in stocks]}

@app.route('/add_trade', methods=['GET', 'POST'])
def add_stock():
    """Add a new stock entry to the database."""
    if request.method == 'POST':
        date = request.form.get('date')
        if not validate_date(date):
            return render_template('add_trade.html', error="Invalid date format. Use YYYY-MM-DD.")
        ticker = request.form.get('ticker').upper()
        if not validate_stock_symbol(ticker):
            return render_template('add_trade.html', error="Invalid stock symbol.")
        action = request.form.get('action').upper()
        if action not in ['BUY', 'SELL']:
            return render_template('add_trade.html', error="Action must be either BUY or SELL.")
        quantity = request.form.get('quantity')
        if not quantity.isdigit() or int(quantity) <= 0:
            return render_template('add_trade.html', error="Quantity must be a positive integer.")
        price = request.form.get('price')
        if not validate_price(price):
            return render_template('add_trade.html', error="Price must be a positive number.")
        notes = request.form.get('notes', '')
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        if action == 'SELL':
            c.execute('SELECT sum(quantity) FROM stocks WHERE ticker = ? and action ="BUY"', (ticker,))
            total_bought = c.fetchone()[0] or 0

            c.execute('SELECT sum(quantity) FROM stocks WHERE ticker = ? and action ="SELL"', (ticker,))
            total_sold = c.fetchone()[0] or 0

            if int(total_sold) + int(quantity) >= int(total_bought):
                conn.close()
                return render_template('add_trade.html', error="Cannot sell more than you have bought.")
        
        c.execute('INSERT INTO stocks (date, ticker, action, quantity, price, notes) VALUES (?, ?, ?, ?, ?, ?)', 
                  (date, ticker, action, quantity, price, notes))
        conn.commit()
        conn.close()
        return redirect('/add_trade')
    
    return render_template('add_trade.html')


@app.route('/stocks/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    """Delete a stock entry from the database."""
    db = get_db()
    db.execute('DELETE FROM stocks WHERE id = ?', (stock_id,))
    db.commit()
    return {'status': 'success'}, 204

@app.route('/stocks/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id):
    """Update an existing stock entry in the database."""
    db = get_db()
    data = request.json
    db.execute('UPDATE stocks SET date = ?, ticker = ?, action = ?, quantity = ?, price = ?, notes = ? WHERE id = ?',
               (data['date'], data['ticker'], data['action'], data['quantity'], data['price'], data.get('notes', ''), stock_id))
    db.commit()
    return {'status': 'success'}, 200

"""Make sure the stock symbols are valid."""
def validate_stock_symbol(symbol):
    try:
        data = yf.Ticker(symbol).info
        return data and 'regularMarketPrice' in data
    except:
        return False
    
"""Make sure the date is valid."""
def validate_date(date_str):
    try:
        # Convert to datetime object
        trade_date = datetime.strptime(date_str, "%Y-%m-%d")

        # Now it's safe to compare
        return trade_date <= datetime.today()
    except ValueError:
        return False

""" Make sure the price is a valid number."""
def validate_price(price):
    try:
        price = float(price)
        return price > 0
    except ValueError:
        return False
    
# Display results on a new page
@app.route('/report')
def report():
    ticker = request.args.get('ticker')
    month = request.args.get('month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    trades = fetch_trades(ticker, month, start_date, end_date)
    gains = calculate_gain(trades)
    wash_sales = detect_wash_sale(trades)
    return render_template('report.html', gains=gains, wash_sales=wash_sales)

# Export the report as a CSV file
@app.route('/export')
def export_report():
    ticker = request.args.get('ticker')
    month = request.args.get('month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    trades = fetch_trades(ticker, month, start_date, end_date)
    gains = calculate_gain(trades)
    wash_sales = detect_wash_sale(trades)

    # Create a CSV response
    output = []
    output.append(['Date', 'Ticker', 'Quantity', 'Price Bought', 'Price Sold', 'Gain', 'Notes'])
    for row in gains:
        output.append([
            row['date'],
            row['ticker'],
            row['quantity'],
            f"{row['price_bought']:.2f}",
            f"{row['price_sold']:.2f}",
            row['gain'],
            row['notes']
        ])

    output.append([])
    output.append(['Sell Date', 'Ticker', 'Disallowed Loss', 'Matched Buy Date'])  
    for sale in wash_sales:
        output.append([
            sale['sell_date'],
            sale['ticker'],
            f"{sale['disallowed_loss']:.2f}",
            sale['matched_buy_date']
        ])
    
    # Convert to CSV format
    si = ""
    for row in output:
        si += ','.join(map(str, row)) + '\n'
    
    response = make_response(si)
    response.headers['Content-Disposition'] = 'attachment; filename=report.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)




