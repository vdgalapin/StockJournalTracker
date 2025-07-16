from flask import Flask, redirect, request, g, render_template, make_response, url_for
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
        
        time = request.form.get('time')
        if time:    
            try:
                datetime.strptime(time, "%H%M")
            except ValueError:
                return render_template('add_trade.html', error="Invalid time format. Use HHMM.")
        
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
            
            # Total bought BEFORE OR AT the current trade's datetime
            c.execute('''
                SELECT COALESCE(SUM(quantity), 0)
                FROM stocks
                WHERE ticker = ?
                AND action = "BUY"
                AND date <= ? 
                AND time <= ?
            ''', (ticker, date, time))
            total_bought = c.fetchone()[0]

            # Total sold BEFORE the current trade's datetime
            c.execute('''
                SELECT COALESCE(SUM(quantity), 0)
                FROM stocks
                WHERE ticker = ?
                AND action = "SELL"
                AND date <= ?
                AND time <= ?
            ''', (ticker, date, time))
        
            total_sold = c.fetchone()[0]

            # Validate: new sell should not exceed total bought so far
            if int(total_sold) + int(quantity) > int(total_bought):
                conn.close()
                return render_template('add_trade.html', error="Cannot sell more than " + str(int(total_bought) - int(total_sold)) + " shares of " + ticker + " stocks.")

        
        c.execute('INSERT INTO stocks (date, time, ticker, action, quantity, price, notes) VALUES (?, ?, ?, ?, ?, ?, ?)', (date, time, ticker, action, quantity, price, notes))
        conn.commit()
        conn.close()
        return render_template('/add_trade', success="Trade added successfully! (" + ticker + " " + action + " " + quantity + " shares at $" + price + ")")
    
    return render_template('add_trade.html')

@app.route('/delete_trade', methods=['GET', 'POST'])
def delete_trade():
    """Delete a stock entry from the database."""
    if request.method == 'POST':
        
        stock_id = request.form.get('stock_id')
        
        if stock_id:
            db = get_db()
            message = validate_delete_trade(stock_id)
            print("Validation message:", message)
            if message == "success":
                db.execute('DELETE FROM stocks WHERE id = ?', (stock_id,))
                db.commit()
                message = "Trade deleted successfully."
        else:
            message = "No stock ID provided for deletion."
    
    ticker = request.args.get('ticker')
    month = request.args.get('month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    stocks = fetch_trades(ticker, month, start_date, end_date)
    return render_template('delete_trade.html', stocks=stocks, message=message if 'message' in locals() else None)

def validate_delete_trade(stock_id):
    print("Validating delete trade for stock_id:", stock_id)
    c = get_db().cursor()
    c.execute('SELECT ticker, action, quantity, date, time FROM stocks WHERE id = ?', (stock_id,))
    row = c.fetchone()

    if not row:
        message = "Trade not found."
        return  message

    ticker, action, quantity, date, time = row
    # Fetch relevant buy/sell totals
    if action == 'BUY':
        # Check total sold after this buy
        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'SELL'
            AND (date < ? OR (date = ? AND time < ?))
        ''', (ticker, date, date, time))
        future_sells = c.fetchone()[0]

        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'BUY'
            AND (date < ? OR (date = ? AND time <= ?))
            AND id != ?
        ''', (ticker, date, date, time, stock_id))
        past_buys_excluding_this = c.fetchone()[0]

        if future_sells > past_buys_excluding_this - int(quantity):
            c.close()
            return "Cannot delete this BUY — future SELLs would now exceed total BUYs."
        else:
            print("Future sells:", future_sells, "Past buys excluding this:", past_buys_excluding_this)

    
    c.close()
    return "success"

@app.route('/edit_trade', methods=['GET', 'POST'])
def edit_trade():
    error = request.args.get('message')
    """Edit a stock entry from the database."""
    if request.method == 'POST':
        
        stock_id = request.form.get('stock_id')
        
        if stock_id:
            db = get_db().cursor()
            db.execute('SELECT id FROM stocks WHERE id = ?', (stock_id,))
            row = db.fetchone()

            if not row:
                error = "Trade not found 2."
            else:
                return redirect(url_for('editing_trade', stock_id=stock_id))           
        else:
            error = "No stock ID provided for Edit."
    

    ticker = request.args.get('ticker')
    month = request.args.get('month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    

    stocks = fetch_trades(ticker, month, start_date, end_date)
    return render_template('edit_trade.html', stocks=stocks, error=error if 'error' in locals() else None)

@app.route('/editing_trade', methods=['POST', 'GET'])
def editing_trade():
    error = ""
    stock_id = request.args.get('stock_id')
    if request.method == 'POST':
        """Update an existing stock entry in the database."""
        stock_id = request.form.get('stock_id')

        date = request.form.get('date')
        if not validate_date(date):
            error = "Invalid date format. Use YYYY-MM-DD."

        time = request.form.get('time')
        if time:
            try:
                datetime.strptime(time, "%H%M")
            except ValueError:
                error = "Invalid time format. Use HHMM."
            
        ticker = request.form.get('ticker').upper()
        if not validate_stock_symbol(ticker):
            error = "Invalid stock symbol."

        action = request.form.get('action').upper()
        if action not in ['BUY', 'SELL']:
            error = "Action must be either BUY or SELL."

        quantity = request.form.get('quantity')
        if not quantity.isdigit() or int(quantity) <= 0:
            error = "Quantity must be a positive integer."

        price = request.form.get('price')
        if not validate_price(price):
            error = "Price must be a positive number."

        notes = request.form.get('notes', '')
        
        if error:
            return render_template('editing_trade.html', error=error, stock_id=stock_id, ticker=ticker, action=action, 
            quantity=quantity, date=date, time=time, price=price, notes=notes)
        
        else:
            validation_message = validate_edit_trade(stock_id, quantity, date, time)
            if validation_message != "success":
                error = validation_message
            else:    
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('UPDATE stocks SET date = ?, time = ?, action = ?, quantity = ?, price = ?, notes = ?  WHERE id = ?', (date, time, action, quantity, price, notes, stock_id))

                conn.commit()
                conn.close()

                error="Trade updated successfully! (" + ticker + " " + action + " " + quantity + " shares at $" + price + ")"
                
                return redirect(url_for('edit_trade', message=error))

   
    db = get_db().cursor()
    db.execute('SELECT ticker, action, quantity, date, time, price, notes FROM stocks WHERE id = ?', (stock_id,))
    row = db.fetchone()
    if not row:
        error = "Trade not found."
        return redirect(url_for('edit_trade', error=error))
    ticker, action, quantity, date, time, price, notes = row
    return render_template('editing_trade.html', error=error if 'error' in locals() else None, stock_id=stock_id, ticker=ticker, action=action, quantity=quantity, date=date, time=time, price=price, notes=notes) 

def validate_edit_trade(stock_id, quantity_to_update, date_to_update, time_to_update):
    print("Validating edit trade for stock_id:", stock_id)
    c = get_db().cursor()
    c.execute('SELECT ticker, action FROM stocks WHERE id = ?', (stock_id,))
    row = c.fetchone()

    if not row:
        message = "Trade not found."
        return  message

    ticker, action = row
    # Fetch relevant buy/sell totals
    if action == 'BUY':
        # Check total sold after this buy
        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'SELL'
            AND (date < ? OR (date = ? AND time <= ?))
        ''', (ticker, date_to_update, date_to_update, time_to_update))
        future_sells = c.fetchone()[0]
        print("Future sells:", future_sells)
        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'BUY'
            AND (date < ? OR (date = ? AND time <= ?))
            AND id != ?
        ''', (ticker, date_to_update, date_to_update, time_to_update, stock_id))
        past_buys_excluding_this = c.fetchone()[0]
        print("Past buys excluding this:", past_buys_excluding_this)
        if future_sells > past_buys_excluding_this + int(quantity_to_update):
            c.close()
            return "Cannot edit this BUY — future SELLs would now exceed total BUYs."
        else:
            print("Future sells:", future_sells, "Past buys excluding this:", past_buys_excluding_this)

    elif action == 'SELL':

        c.execute('SELECT ticker, action, quantity, date, time FROM stocks WHERE id = ?', (stock_id,))
        row = c.fetchone()
        # Check total sold including this trade
        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'SELL'
            AND (date < ? OR (date = ? AND time < ?))
            AND id != ?
        ''', (ticker, date_to_update, date_to_update, time_to_update, stock_id))
        past_sells = c.fetchone()[0]

        c.execute('''
            SELECT COALESCE(SUM(quantity), 0)
            FROM stocks
            WHERE ticker = ?
            AND action = 'BUY'
            AND (date < ? OR (date = ? AND time <= ?))
        ''', (ticker, date_to_update, date_to_update, time_to_update))
        total_buys = c.fetchone()[0]

        if past_sells + int(quantity_to_update) > total_buys:
            c.close()
            return "Cannot edit this SELL — it would exceed total BUYs."
        else:
            print("Past sells:", past_sells, "Total buys:", total_buys)
            
    c.close()
    return "success"

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
    output.append(['Date', 'Time', 'Ticker', 'Quantity', 'Price Bought', 'Price Sold', 'Gain', 'Notes'])
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
    output.append(['Sell Date', 'Time', 'Ticker', 'Disallowed Loss', 'Matched Buy Date'])  
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




