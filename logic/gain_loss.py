import sqlite3
from datetime import datetime

def fetch_trades():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stocks ORDER BY date ASC')
    rows = cursor.fetchall()
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
            
            same_ticker_buys = [b for b in buy_queue if buy['ticker'] == trade]
            for buy in same_ticker_buys:
                if sell_qty <= 0:
                    break

                # Check how much we can match
                matched = min(quantity_to_sell, buy['qty'])

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
                'price': price_to_sell,
                'gain': gain,
                'date': trade['date'],
            })
        return results
    