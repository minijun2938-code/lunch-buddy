import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "mprs_workshop.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept TEXT,
            target_dept TEXT,
            category TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add target_dept if not exists
    c.execute("PRAGMA table_info(feedback)")
    cols = [row[1] for row in c.fetchall()]
    if "target_dept" not in cols:
        c.execute("ALTER TABLE feedback ADD COLUMN target_dept TEXT DEFAULT 'All'")
    
    conn.commit()
    conn.close()

def add_feedback(dept, target_dept, category, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO feedback (dept, target_dept, category, content) VALUES (?, ?, ?, ?)", (dept, target_dept, category, content))
    conn.commit()
    conn.close()

def get_all_feedback():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT dept, target_dept, category, content, created_at FROM feedback ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def clear_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()
