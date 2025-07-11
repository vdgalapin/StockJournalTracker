from flask import Flask, request, g, render_template
from datetime import date, datetime
from logic.gain_loss import calculate_gain, fetch_trades
from logic.wash_sale import detect_wash_sale    
import yfinance as yf
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

@app.route('/stocks', methods=['POST'])
def add_stock():
    """Add a new stock entry to the database."""
    db = get_db()
    data = request.json
    db.execute('INSERT INTO stocks (date, ticker, action, quantity, price, notes) VALUES (?, ?, ?, ?, ?, ?)',
               (data['date'], data['ticker'], data['action'], data['quantity'], data['price'], data.get('notes', '')))
    db.commit()
    return {'status': 'success'}, 201

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
        datetime.strptime(date_str, '%Y-%m-%d')
        return date <= datetime.today() 
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
    trades = fetch_trades()
    gains = calculate_gain(trades)
    wash_sales = detect_wash_sale(trades)
    return render_template('report.html', gains=gains, wash_sales=wash_sales)


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)




