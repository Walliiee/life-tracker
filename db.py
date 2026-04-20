import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'life-tracker.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH):
        conn = get_db()
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())
        conn.close()