import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "mprs_workshop.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # feedback table with advanced fields
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept TEXT,
            target_dept TEXT,
            category TEXT,
            tag TEXT,
            content TEXT,
            situation TEXT,
            impact TEXT,
            severity INTEGER DEFAULT 1,
            effort INTEGER DEFAULT 1,
            likes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add missing columns if exists
    c.execute("PRAGMA table_info(feedback)")
    cols = [row[1] for row in c.fetchall()]
    new_cols = {
        "tag": "TEXT",
        "situation": "TEXT",
        "impact": "TEXT",
        "severity": "INTEGER DEFAULT 1",
        "effort": "INTEGER DEFAULT 1",
        "likes": "INTEGER DEFAULT 0"
    }
    for col, ctype in new_cols.items():
        if col not in cols:
            c.execute(f"ALTER TABLE feedback ADD COLUMN {col} {ctype}")

    # --- AI Suggestions table ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            votes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def add_ai_suggestion(title, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO ai_suggestions (title, content) VALUES (?, ?)", (title, content))
    conn.commit()
    conn.close()

def vote_ai_suggestion(suggestion_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE ai_suggestions SET votes = votes + 1 WHERE id = ?", (suggestion_id,))
    conn.commit()
    conn.close()

def get_ai_suggestions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, content, votes FROM ai_suggestions ORDER BY votes DESC, created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def clear_ai_suggestions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ai_suggestions")
    conn.commit()
    conn.close()

def add_feedback(dept, target_dept, category, content, tag="", situation="", impact="", severity=1, effort=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO feedback (dept, target_dept, category, content, tag, situation, impact, severity, effort) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (dept, target_dept, category, content, tag, situation, impact, severity, effort))
    conn.commit()
    conn.close()

def add_vote(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE feedback SET likes = likes + 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_all_feedback():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, dept, target_dept, category, tag, content, situation, impact, severity, effort, likes, created_at FROM feedback ORDER BY likes DESC, created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def clear_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()
