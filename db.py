import os
import sqlite3
import datetime
import hashlib
import secrets

DB_NAME = os.path.join(os.path.dirname(__file__), "lunch_mate.db")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_pin(employee_id: str, pin: str, salt_hex: str) -> str:
    # pin is 4-digit numeric string
    return _sha256_hex(f"{employee_id}:{pin}:{salt_hex}".encode("utf-8"))

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users table (supports simple migrations)
    # NOTE: username is NOT unique (names can duplicate). employee_id is unique.
    c.execute(
        '''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  telegram_chat_id TEXT,
                  team TEXT,
                  mbti TEXT,
                  age INTEGER,
                  years INTEGER,
                  employee_id TEXT,
                  pin_salt TEXT,
                  pin_hash TEXT)'''
    )

    # Migrations for older DBs
    c.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in c.fetchall()}
    wanted = {
        "team": "TEXT",
        "mbti": "TEXT",
        "age": "INTEGER",
        "years": "INTEGER",
        "employee_id": "TEXT",
        "pin_salt": "TEXT",
        "pin_hash": "TEXT",
    }
    for col, col_type in wanted.items():
        if col not in existing_cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    # If an older DB was created with UNIQUE(username), rebuild users table to drop it.
    c.execute("PRAGMA index_list(users)")
    idxs = c.fetchall()  # (seq, name, unique, origin, partial)
    has_unique_username = False
    for _seq, name, unique, *_rest in idxs:
        if not unique:
            continue
        c.execute(f"PRAGMA index_info({name})")
        cols = [r[2] for r in c.fetchall()]  # (seqno, cid, name)
        if cols == ["username"]:
            has_unique_username = True
            break

    if has_unique_username:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS users_new
                     (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT,
                      telegram_chat_id TEXT,
                      team TEXT,
                      mbti TEXT,
                      age INTEGER,
                      years INTEGER,
                      employee_id TEXT,
                      pin_salt TEXT,
                      pin_hash TEXT)'''
        )
        c.execute(
            """
            INSERT INTO users_new (user_id, username, telegram_chat_id, team, mbti, age, years, employee_id, pin_salt, pin_hash)
            SELECT user_id, username, telegram_chat_id, team, mbti, age, years, employee_id, pin_salt, pin_hash
            FROM users
            """
        )
        c.execute("DROP TABLE users")
        c.execute("ALTER TABLE users_new RENAME TO users")

    # Unique employee id (login id)
    c.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_id
           ON users(employee_id)"""
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

    # Hosting groups ("우리쪽에 합류하실분?")
    c.execute(
        '''CREATE TABLE IF NOT EXISTS lunch_groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT,
                  host_user_id INTEGER,
                  member_names TEXT,
                  seats_left INTEGER,
                  menu TEXT,
                  UNIQUE(date, host_user_id))'''
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_groups_day
           ON lunch_groups(date)"""
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

def register_user(
    *,
    username: str,
    team: str,
    mbti: str,
    age: int,
    years: int,
    employee_id: str,
    pin: str,
    chat_id: str | None = None,
) -> tuple[bool, str | None]:
    """Register a new user.

    Returns: (ok, error_message)
    """
    employee_id = (employee_id or "").strip().lower()

    # employee id rule: 2 lowercase letters + 5 digits
    import re

    if not re.fullmatch(r"[a-z]{2}\d{5}", employee_id):
        return False, "사번은 영문자 2개 + 숫자 5개 형식이어야 합니다. (예: sl55555)"

    if not (pin.isdigit() and len(pin) == 4):
        return False, "비밀번호(PIN)는 숫자 4자리여야 합니다."

    salt = secrets.token_hex(16)
    pin_hash = _hash_pin(employee_id, pin, salt)

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT INTO users (username, team, mbti, age, years, employee_id, pin_salt, pin_hash, telegram_chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, team, mbti, int(age), int(years), employee_id, salt, pin_hash, chat_id),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 사번(employee_id)입니다."
    finally:
        conn.close()


def verify_login(employee_id: str, pin: str) -> tuple[bool, tuple | None]:
    """Returns (ok, user_row)."""
    employee_id = (employee_id or "").strip().lower()
    user = get_user_by_employee_id(employee_id)
    if not user:
        return False, None

    user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, salt, pin_hash = user
    if not (pin.isdigit() and len(pin) == 4):
        return False, None

    if _hash_pin(emp_id or employee_id, pin, salt or "") != (pin_hash or ""):
        return False, None

    return True, user


def update_user_chat_id(user_id, chat_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET telegram_chat_id=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()
    conn.close()


def set_planning(user_id: int):
    update_status(user_id, "Planning")

def get_user_by_employee_id(employee_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id, username, telegram_chat_id, team, mbti, age, years, employee_id, pin_salt, pin_hash
        FROM users
        WHERE employee_id=?
        """,
        (employee_id,),
    )
    user = c.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id, username, telegram_chat_id, team, mbti, age, years, employee_id, pin_salt, pin_hash
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    )
    user = c.fetchone()
    conn.close()
    return user

def update_status(user_id, status):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO daily_status (id, date, user_id, status) VALUES ((SELECT id FROM daily_status WHERE date=? AND user_id=?), ?, ?, ?)",
        (today, user_id, today, user_id, status),
    )
    conn.commit()
    conn.close()


def upsert_group(host_user_id: int, member_names: str, seats_left: int, menu: str):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO lunch_groups (id, date, host_user_id, member_names, seats_left, menu)
        VALUES ((SELECT id FROM lunch_groups WHERE date=? AND host_user_id=?), ?, ?, ?, ?, ?)
        """,
        (today, host_user_id, today, host_user_id, member_names, int(seats_left), menu),
    )
    conn.commit()
    conn.close()


def get_groups_today():
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu
        FROM lunch_groups g
        JOIN users u ON u.user_id = g.host_user_id
        WHERE g.date=?
        ORDER BY g.id DESC
        """,
        (today,),
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_statuses():
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT u.user_id, u.username, COALESCE(ds.status, 'Not Set') as status, u.telegram_chat_id
        FROM users u
        LEFT JOIN daily_status ds ON u.user_id = ds.user_id AND ds.date = ?
        """,
        (today,),
    )
    results = c.fetchall()
    conn.close()
    return results

def create_request(from_user_id, to_user_id):
    """Create a lunch invite request for today.

    Side effect (per spec): both requester and receiver become "Planning" automatically.

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
        req_id = c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

    # Update statuses (separate connections) so we don't keep the request transaction open
    set_planning(from_user_id)
    set_planning(to_user_id)
    return req_id


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
