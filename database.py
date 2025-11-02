import sqlite3
from datetime import datetime, timedelta

# Connect to SQLite database
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    description TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS rsvps (
    user_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    UNIQUE(user_id, event_id)
)
""")
conn.commit()

# ---------------------------
# EVENT FUNCTIONS
# ---------------------------
async def create_event(name, date, time, description):
    cursor.execute("INSERT INTO events (name, d
