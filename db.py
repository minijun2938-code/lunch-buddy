import os
import sqlite3
import datetime

DB_NAME = os.path.join(os.path.dirname(__file__), "lunch_mate.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users table
    c.execute(
        '''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  telegram_chat_id TEXT)'''
    )

    # Daily Status table (Unique constraint on date+user_id to prevent duplicates)
    c.execute(
        '''CREATE TABLE IF NOT EXISTS daily_status
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT,
                  user_id INTEGER,
                  status TEXT,
                  UNIQUE(date, user_id))'''
    )

    # Requests table
    # status: pending | accepted | declined | cancelled
    c.execute(
        '''CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user_id INTEGER,
                  to_user_id INTEGER,
                  date TEXT,
                  status TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
    )

    # Prevent duplicate "pending" requests between same pair on same date.
    c.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_unique_pair_day
           ON requests(date, from_user_id, to_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_requests_to_day
           ON requests(date, to_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_requests_from_day
           ON requests(date, from_user_id)"""
    )

    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)

def register_user(username, chat_id=None):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, telegram_chat_id) VALUES (?, ?)",
            (username, chat_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Already exists
    finally:
        conn.close()


def update_user_chat_id(user_id, chat_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET telegram_chat_id=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()

def get_user(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, username, telegram_chat_id FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, username, telegram_chat_id FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_status(user_id, status):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    # Insert or Replace (Upsert logic for SQLite)
    c.execute("INSERT OR REPLACE INTO daily_status (id, date, user_id, status) VALUES ((SELECT id FROM daily_status WHERE date=? AND user_id=?), ?, ?, ?)", 
              (today, user_id, today, user_id, status))
    conn.commit()
    conn.close()

def get_all_statuses():
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    # Get all users and their status for today (LEFT JOIN to show users who haven't set status yet)
    c.execute("""
        SELECT u.user_id, u.username, COALESCE(ds.status, 'Not Set') as status, u.telegram_chat_id
        FROM users u
        LEFT JOIN daily_status ds ON u.user_id = ds.user_id AND ds.date = ?
    """, (today,))
    results = c.fetchall()
    conn.close()
    return results

def create_request(from_user_id, to_user_id):
    """Create a lunch invite request for today.

    Returns: request_id (int) on success, None on duplicate.
    """
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO requests (from_user_id, to_user_id, date, status) VALUES (?, ?, ?, 'pending')",
            (from_user_id, to_user_id, today),
        )
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_request_status(request_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()


def cancel_request(request_id):
    update_request_status(request_id, "cancelled")


def get_pending_request_between(from_user_id, to_user_id):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, status
        FROM requests
        WHERE date=? AND from_user_id=? AND to_user_id=?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, from_user_id, to_user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def list_incoming_requests(user_id):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id, r.from_user_id, u.username, r.status, r.timestamp
        FROM requests r
        JOIN users u ON u.user_id = r.from_user_id
        WHERE r.date=? AND r.to_user_id=?
        ORDER BY r.timestamp DESC
        """,
        (today, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def list_outgoing_requests(user_id):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id, r.to_user_id, u.username, r.status, r.timestamp
        FROM requests r
        JOIN users u ON u.user_id = r.to_user_id
        WHERE r.date=? AND r.from_user_id=?
        ORDER BY r.timestamp DESC
        """,
        (today, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows
