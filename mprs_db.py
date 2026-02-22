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

    # --- App state (shared flags across users) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # --- Consolidated TODOs & voting ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS todo_items (
            todo_key TEXT PRIMARY KEY,
            group_title TEXT,
            todo_text TEXT,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS todo_votes (
            todo_key TEXT,
            voter_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(todo_key, voter_id)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_todo_votes_todo_key ON todo_votes(todo_key)")

    # --- Action canvas items (workshop outcomes) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER,
            author_id TEXT,
            category TEXT,
            from_dept TEXT,
            to_dept TEXT,
            summary TEXT,
            votes INTEGER DEFAULT 0,
            proposal TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration for older DBs: add missing columns if needed
    c.execute("PRAGMA table_info(action_items)")
    a_cols = [row[1] for row in c.fetchall()]
    if "proposal" not in a_cols:
        c.execute("ALTER TABLE action_items ADD COLUMN proposal TEXT")
    if "author_id" not in a_cols:
        c.execute("ALTER TABLE action_items ADD COLUMN author_id TEXT")

    c.execute("CREATE INDEX IF NOT EXISTS idx_action_items_feedback_id ON action_items(feedback_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_action_items_author_id ON action_items(author_id)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uidx_action_items_feedback_author ON action_items(feedback_id, author_id)")
    
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


# --- TODO items & votes ---
def clear_todos(keep_votes: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not keep_votes:
        c.execute("DELETE FROM todo_votes")
    c.execute("DELETE FROM todo_items")
    conn.commit()
    conn.close()


def upsert_todo_item(todo_key: str, group_title: str, todo_text: str, order_index: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO todo_items(todo_key, group_title, todo_text, order_index)
        VALUES(?,?,?,?)
        ON CONFLICT(todo_key) DO UPDATE SET group_title=excluded.group_title, todo_text=excluded.todo_text, order_index=excluded.order_index
        """,
        (todo_key, group_title, todo_text, order_index),
    )
    conn.commit()
    conn.close()


def get_todo_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT todo_key, group_title, todo_text, order_index
        FROM todo_items
        ORDER BY order_index ASC
        """
    )
    rows = c.fetchall()
    conn.close()
    return rows


def vote_todo(todo_key: str, voter_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO todo_votes(todo_key, voter_id) VALUES(?,?)", (todo_key, voter_id))
    conn.commit()
    conn.close()


def has_voted_todo(todo_key: str, voter_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM todo_votes WHERE todo_key=? AND voter_id=?", (todo_key, voter_id))
    row = c.fetchone()
    conn.close()
    return bool(row)


def get_todo_vote_counts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT todo_key, COUNT(*) FROM todo_votes GROUP BY todo_key")
    rows = c.fetchall()
    conn.close()
    return {k: v for k, v in rows}

# --- Shared app state helpers ---
def set_state(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO app_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    conn.commit()
    conn.close()

def get_state(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM app_state WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

# --- Action canvas helpers ---
def upsert_action_item(
    feedback_id: int,
    author_id: str,
    category: str,
    from_dept: str,
    to_dept: str,
    summary: str,
    votes: int,
    proposal: str = "",
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 1 feedback x 1 author -> 1 action item row
    c.execute("SELECT id FROM action_items WHERE feedback_id = ? AND author_id = ?", (feedback_id, author_id))
    row = c.fetchone()
    if row:
        c.execute(
            """
            UPDATE action_items
            SET category=?, from_dept=?, to_dept=?, summary=?, votes=?, proposal=?
            WHERE feedback_id=? AND author_id=?
        """,
            (category, from_dept, to_dept, summary, votes, proposal, feedback_id, author_id),
        )
    else:
        c.execute(
            """
            INSERT INTO action_items(feedback_id, author_id, category, from_dept, to_dept, summary, votes, proposal)
            VALUES(?,?,?,?,?,?,?,?)
        """,
            (feedback_id, author_id, category, from_dept, to_dept, summary, votes, proposal),
        )
    conn.commit()
    conn.close()

def get_action_items(author_id: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if author_id:
        c.execute(
            """
            SELECT feedback_id, author_id, category, from_dept, to_dept, summary, votes, proposal, created_at
            FROM action_items
            WHERE author_id = ?
            ORDER BY votes DESC, created_at DESC
        """,
            (author_id,),
        )
    else:
        c.execute(
            """
            SELECT feedback_id, author_id, category, from_dept, to_dept, summary, votes, proposal, created_at
            FROM action_items
            ORDER BY votes DESC, created_at DESC
        """
        )
    rows = c.fetchall()
    conn.close()
    return rows

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


def clear_action_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM action_items")
    conn.commit()
    conn.close()
