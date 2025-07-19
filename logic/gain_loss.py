import sqlite3
from datetime import datetime

def fetch_trades(ticker=None, month=None, start_date=None, end_date=None, user_id=None):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = 'SELECT * FROM stocks WHERE 1=1'
    params = []

    if ticker:
        query += ' AND ticker = ?'
        params.append(ticker)
    
    if month:
        query += ' AND strftime("%Y-%m", date) = ?'
        params.append(month)
    
    if start_date:
        query += ' AND date >= ?'
        params.append(datetime.strptime(start_date, '%Y-%m-%d').date())

    if end_date:
        query += ' AND date <= ?'
        params.append(datetime.strptime(end_date, '%Y-%m-%d').date())

    query += ' AND user_id = ?'
    params.append(user_id)
    query += ' ORDER BY date ASC'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]

""" Calculate the gain (FIFO)"""
def calculate_gain(trades):
    buy_queue = []
    results = []

    for trade in trades:
        if trade['action'] == 'BUY':
            buy_queue.append({
                'ticker': trade['ticker'],
                'quantity': trade['quantity'],
                'price': trade['price'],
                'date': trade['date'],
            })
        elif trade['action'] == 'SELL':
            quantity_to_sell = int(trade['quantity'])
            price_to_sell = float(trade['price'])
            cost_basis = 0
            matched_quantity = 0
            
            same_ticker_buys = [b for b in buy_queue if b['ticker'] == trade['ticker']]
            for buy in same_ticker_buys:
                if quantity_to_sell <= 0:
                    break

                # Check how much we can match
                matched = min(quantity_to_sell, buy['quantity'])

                # This is the total cost made in this bought stock 
                cost_basis += matched * buy['price']

                # We will the substract the quantity we are selling from whichever has the least quantity
                quantity_to_sell -= matched

                # Then add the quantity to sell to the total matched quantity
                matched_quantity += matched

               # We will substract the quantity we sold to the current buy queue
                buy['quantity'] -= matched

                if buy['quantity'] == 0:
                    buy_queue.remove(buy)

            if quantity_to_sell > 0:
                raise ValueError(f"Not enough shares to sell for {trade['ticker']} on {trade['date']}.")
                
            if matched_quantity == 0:       
                raise ValueError(f"No matching buy trades found for {trade['ticker']} on {trade['date']}.")
            

            proceeds = matched_quantity * price_to_sell
            gain = proceeds - cost_basis    
            results.append({
                'ticker': trade['ticker'],
                'quantity': matched_quantity,
                'price_bought': round(cost_basis / matched_quantity, 2),
                'price_sold': round(price_to_sell, 2),
                'gain': (f"-${abs(gain):,.2f}" if gain < 0 else f"${gain:,.2f}").replace(",", ""),
                'date': trade['date'],
                'time': trade['time'],
                'notes': trade.get('notes', '')
            })
    return results
    