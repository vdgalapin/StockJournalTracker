from flask import Flask, request, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), 'database.db')

@app.route('/')
def hello():
    return "Hello, World!"

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

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)




