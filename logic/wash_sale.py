from datetime import timedelta, datetime

def detect_wash_sale(trades):
    trades = sorted(trades, key=lambda x: (x['ticker'], x['date']) )
    flagged_trades = []

    for i, trade in enumerate(trades):
        # If it's not a sell action, skip it    
        if trade['action'] != 'SELL':
            continue
        
        # Get the sell date in YYYYMMDD and price
        sell_date = datetime.strptime(trade['date'], '%Y-%m-%d')
        sell_prce = float(trade['price'])
        sell_quantity = int(trade['quantity'])

        # Find the original buy trades for the same ticker
        prior_buys = [t for t in trades[:i] if t['action'] == 'BUY' and t['ticker'] == trade['ticker']]
        if not prior_buys:
            continue

        # The original cost of the stock bought
        cost_basis = float(prior_buys[-1]['price'])
        gain = (sell_prce - cost_basis) * sell_quantity

        if gain >= 0:
            continue # not a lost so not a wash sale

        date_start = sell_date - timedelta(days=30)
        date_end = sell_date + timedelta(days=30)

        future_buys = [t for t in trades if t['action'] == 'BUY' and t['ticker'] == trade['ticker']]
        for b in future_buys:
            buy_date = datetime.strptime(b['date'], '%Y-%m-%d')
            if date_start <= buy_date <= date_end:
                flagged_trades.append({
                    'sell_date': trade['date'],
                    'ticker': trade['ticker'],
                    'disallowed_loss': abs(gain),
                    'matched_buy_date': b['date'],
                })
                break
    return flagged_trades
