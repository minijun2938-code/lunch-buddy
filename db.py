import os
import sqlite3
import datetime
from datetime import timezone, timedelta
import hashlib
import secrets

DB_NAME = os.path.join(os.path.dirname(__file__), "lunch_mate.db")


def kst_today() -> datetime.date:
    """Return today's date in Asia/Seoul (KST), independent of server timezone."""
    return (datetime.datetime.now(timezone.utc) + timedelta(hours=9)).date()


def kst_today_iso() -> str:
    return kst_today().isoformat()


def kst_now_str() -> str:
    """KST timestamp string for display/storage."""
    return (datetime.datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


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
                  english_name TEXT,
                  telegram_chat_id TEXT,
                  team TEXT,
                  role TEXT,
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
        "english_name": "TEXT",
        "team": "TEXT",
        "role": "TEXT",
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

    # Daily Status table (meal-aware)
    # meal: lunch | dinner
    # kind: (dinner only) 'meal' | 'drink'
    # We migrate legacy daily_status(date,user_id,status) -> daily_status(date,meal,user_id,status,kind)
    c.execute("PRAGMA table_info(daily_status)")
    ds_cols = {row[1] for row in c.fetchall()}
    if "meal" not in ds_cols:
        # Legacy schema → rebuild
        c.execute(
            '''CREATE TABLE IF NOT EXISTS daily_status_new
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      user_id INTEGER,
                      status TEXT,
                      kind TEXT,
                      UNIQUE(date, meal, user_id))'''
        )
        # Copy legacy rows as lunch
        try:
            c.execute(
                "INSERT INTO daily_status_new(date, meal, user_id, status, kind) SELECT date, 'lunch', user_id, status, NULL FROM daily_status"
            )
        except Exception:
            pass
        try:
            c.execute("DROP TABLE daily_status")
        except Exception:
            pass
        c.execute("ALTER TABLE daily_status_new RENAME TO daily_status")
    else:
        # Current/partial schema: ensure kind exists
        if "kind" not in ds_cols:
            c.execute("ALTER TABLE daily_status ADD COLUMN kind TEXT")
        # Ensure unique index (best-effort; table already has constraint)
        c.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_status_unique
               ON daily_status(date, meal, user_id)"""
        )

    # Hosting groups (meal-aware)
    # kind: (dinner only) 'meal' | 'drink'
    c.execute("PRAGMA table_info(lunch_groups)")
    gcols = {row[1] for row in c.fetchall()}
    if not gcols:
        # fresh db
        c.execute(
            '''CREATE TABLE IF NOT EXISTS lunch_groups
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      member_names TEXT,
                      member_user_ids TEXT,
                      seats_left INTEGER,
                      menu TEXT,
                      payer_name TEXT,
                      kind TEXT,
                      UNIQUE(date, meal, host_user_id))'''
        )
    elif "meal" not in gcols:
        # Legacy schema → rebuild with meal
        c.execute(
            '''CREATE TABLE IF NOT EXISTS lunch_groups_new
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      member_names TEXT,
                      member_user_ids TEXT,
                      seats_left INTEGER,
                      menu TEXT,
                      payer_name TEXT,
                      kind TEXT,
                      UNIQUE(date, meal, host_user_id))'''
        )
        try:
            c.execute(
                """
                INSERT INTO lunch_groups_new(date, meal, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name, kind)
                SELECT date, 'lunch', host_user_id, member_names, member_user_ids, seats_left, menu, payer_name, NULL
                FROM lunch_groups
                """
            )
        except Exception:
            pass
        try:
            c.execute("DROP TABLE lunch_groups")
        except Exception:
            pass
        c.execute("ALTER TABLE lunch_groups_new RENAME TO lunch_groups")
        gcols = {"date","meal","host_user_id","member_names","member_user_ids","seats_left","menu","payer_name","kind"}
    else:
        # Ensure missing columns
        if "member_user_ids" not in gcols:
            c.execute("ALTER TABLE lunch_groups ADD COLUMN member_user_ids TEXT")
        if "payer_name" not in gcols:
            c.execute("ALTER TABLE lunch_groups ADD COLUMN payer_name TEXT")
        if "kind" not in gcols:
            c.execute("ALTER TABLE lunch_groups ADD COLUMN kind TEXT")

    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_groups_day
           ON lunch_groups(date, meal)"""
    )

    # Normalized group members (meal-aware)
    c.execute("PRAGMA table_info(group_members)")
    gmcols = {row[1] for row in c.fetchall()}
    if not gmcols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS group_members
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      user_id INTEGER,
                      UNIQUE(date, meal, host_user_id, user_id))'''
        )
    elif "meal" not in gmcols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS group_members_new
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      user_id INTEGER,
                      UNIQUE(date, meal, host_user_id, user_id))'''
        )
        try:
            c.execute("INSERT INTO group_members_new(date, meal, host_user_id, user_id) SELECT date, 'lunch', host_user_id, user_id FROM group_members")
        except Exception:
            pass
        try:
            c.execute("DROP TABLE group_members")
        except Exception:
            pass
        c.execute("ALTER TABLE group_members_new RENAME TO group_members")

    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_group_members_day_host
           ON group_members(date, meal, host_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_group_members_day_user
           ON group_members(date, meal, user_id)"""
    )

    # Auth sessions (remember login across refresh)
    c.execute(
        '''CREATE TABLE IF NOT EXISTS auth_sessions
                 (token TEXT PRIMARY KEY,
                  user_id INTEGER,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)'''
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
           ON auth_sessions(user_id)"""
    )

    # Requests table (meal-aware)
    # status: pending | accepted | declined | cancelled
    # kind: (dinner only) 'meal' | 'drink'
    c.execute("PRAGMA table_info(requests)")
    rcols = {row[1] for row in c.fetchall()}
    if not rcols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS requests
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      from_user_id INTEGER,
                      to_user_id INTEGER,
                      group_host_user_id INTEGER,
                      date TEXT,
                      meal TEXT,
                      status TEXT,
                      kind TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
        )
    elif "meal" not in rcols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS requests_new
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      from_user_id INTEGER,
                      to_user_id INTEGER,
                      group_host_user_id INTEGER,
                      date TEXT,
                      meal TEXT,
                      status TEXT,
                      kind TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
        )
        try:
            c.execute(
                """
                INSERT INTO requests_new(id, from_user_id, to_user_id, group_host_user_id, date, meal, status, kind, timestamp)
                SELECT id, from_user_id, to_user_id, group_host_user_id, date, 'lunch', status, NULL, timestamp
                FROM requests
                """
            )
        except Exception:
            pass
        try:
            c.execute("DROP TABLE requests")
        except Exception:
            pass
        c.execute("ALTER TABLE requests_new RENAME TO requests")
        rcols = {"id","from_user_id","to_user_id","group_host_user_id","date","meal","status","kind","timestamp"}
    else:
        if "kind" not in rcols:
            c.execute("ALTER TABLE requests ADD COLUMN kind TEXT")


    # Group chat (meal-aware, members-only)
    c.execute("PRAGMA table_info(group_chat)")
    gccols = {row[1] for row in c.fetchall()}
    if not gccols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS group_chat
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      user_id INTEGER,
                      username TEXT,
                      message TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
        )
    elif "meal" not in gccols:
        c.execute(
            '''CREATE TABLE IF NOT EXISTS group_chat_new
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      meal TEXT,
                      host_user_id INTEGER,
                      user_id INTEGER,
                      username TEXT,
                      message TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
        )
        try:
            c.execute(
                """
                INSERT INTO group_chat_new(id, date, meal, host_user_id, user_id, username, message, timestamp)
                SELECT id, date, 'lunch', host_user_id, user_id, username, message, timestamp
                FROM group_chat
                """
            )
        except Exception:
            pass
        try:
            c.execute("DROP TABLE group_chat")
        except Exception:
            pass
        c.execute("ALTER TABLE group_chat_new RENAME TO group_chat")

    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_group_chat_day_host
           ON group_chat(date, meal, host_user_id, timestamp)"""
    )

    # Migration: add group_host_user_id if missing
    c.execute("PRAGMA table_info(requests)")
    rcols = {row[1] for row in c.fetchall()}
    if "group_host_user_id" not in rcols:
        c.execute("ALTER TABLE requests ADD COLUMN group_host_user_id INTEGER")

    # Allow multiple invites per day (for clean re-invites after cancel).
    # Keep a non-unique index for fast lookup.
    try:
        c.execute("DROP INDEX IF EXISTS idx_requests_unique_pair_day")
    except Exception:
        pass
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_requests_pair_day
           ON requests(date, meal, from_user_id, to_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_requests_to_day
           ON requests(date, meal, to_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_requests_from_day
           ON requests(date, meal, from_user_id)"""
    )

    # Friends table (Private Mode)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER,
            target_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(requester_id, target_id)
        )
        """
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_friends_target_status
           ON friends(target_id, status)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_friends_requester_status
           ON friends(requester_id, status)"""
    )

    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_NAME)


def reset_all_data():
    """Delete ALL app data (users + history). Keeps tables."""
    conn = get_connection()
    c = conn.cursor()
    # order matters due to references
    for tbl in [
        "friends",
        "requests",
        "auth_sessions",
        "group_members",
        "lunch_groups",
        "daily_status",
        "users",
    ]:
        try:
            c.execute(f"DELETE FROM {tbl}")
        except Exception:
            pass
    conn.commit()
    try:
        c.execute("VACUUM")
        conn.commit()
    except Exception:
        pass
    conn.close()


def reset_today_data():
    """Delete today's requests/status/groups for a clean test run (KST-based).

    To handle timezone drift (server UTC vs users KST), we clear a small window around
    both KST-today and UTC-today.

    NOTE: users table is untouched.
    """
    base_kst = kst_today()
    base_utc = datetime.datetime.now(timezone.utc).date()

    date_set = set()
    for base in (base_kst, base_utc):
        for d in (-1, 0, 1):
            date_set.add((base + datetime.timedelta(days=d)).isoformat())

    conn = get_connection()
    c = conn.cursor()
    for ds in sorted(date_set):
        c.execute("DELETE FROM requests WHERE date=?", (ds,))
        c.execute("DELETE FROM daily_status WHERE date=?", (ds,))
        c.execute("DELETE FROM group_members WHERE date=?", (ds,))
        c.execute("DELETE FROM lunch_groups WHERE date=?", (ds,))
    conn.commit()
    conn.close()

def register_user(
    *,
    username: str,
    english_name: str,
    team: str,
    role: str,
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
            INSERT INTO users (username, english_name, team, role, mbti, age, years, employee_id, pin_salt, pin_hash, telegram_chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, (english_name or "").strip(), team, role, mbti, int(age), int(years), employee_id, salt, pin_hash, chat_id),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 사번(employee_id)입니다."
    finally:
        conn.close()


def update_user_profile(
    *,
    user_id: int,
    username: str,
    english_name: str,
    team: str,
    years: int,
) -> tuple[bool, str | None]:
    """Update basic profile fields (employee_id excluded)."""
    try:
        years = int(years)
        if years < 0 or years > 60:
            return False, "연차 값이 올바르지 않습니다."
    except Exception:
        return False, "연차 값이 올바르지 않습니다."

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET username=?, english_name=?, team=?, years=? WHERE user_id=?",
        (
            (username or "").strip(),
            (english_name or "").strip(),
            (team or "").strip(),
            years,
            int(user_id),
        ),
    )
    conn.commit()
    conn.close()
    return True, None


def verify_login(employee_id: str, pin: str) -> tuple[bool, tuple | None]:
    """PIN-based login (4 digits). Returns (ok, user_row)."""
    employee_id = (employee_id or "").strip().lower()
    user = get_user_by_employee_id(employee_id)
    if not user:
        return False, None

    user_id, username, english_name, telegram_chat_id, team, role, mbti, age, years, emp_id, salt, pin_hash = user
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


def update_user_chat_id_by_employee_id(employee_id: str, chat_id: str) -> tuple[bool, str | None]:
    employee_id = (employee_id or "").strip().lower()
    if not employee_id:
        return False, "employee_id가 비어있습니다."
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET telegram_chat_id=? WHERE employee_id=?", (str(chat_id), employee_id))
    conn.commit()
    ok = c.rowcount > 0
    conn.close()
    return (ok, None if ok else "해당 사번 사용자를 찾지 못했어요.")


def set_planning(user_id: int, *, meal: str = "lunch"):
    update_status(user_id, "Planning", meal=_norm_meal(meal))


def has_accepted_today(user_id: int, *, meal: str = "lunch") -> bool:
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT 1
        FROM requests
        WHERE date=? AND meal=? AND status='accepted' AND (from_user_id=? OR to_user_id=?)
        LIMIT 1
        """,
        (today, meal, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def reconcile_user_today(user_id: int, *, meal: str = "lunch"):
    """Make Booked highest priority if any accepted invite exists today (per meal)."""
    meal = _norm_meal(meal)
    if has_accepted_today(user_id, meal=meal) and get_status_today(user_id, meal=meal) != "Booked":
        update_status(user_id, "Booked", meal=meal)

def get_user_by_employee_id(employee_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id, username, english_name, telegram_chat_id, team, role, mbti, age, years, employee_id, pin_salt, pin_hash
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
        SELECT user_id, username, english_name, telegram_chat_id, team, role, mbti, age, years, employee_id, pin_salt, pin_hash
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    )
    user = c.fetchone()
    conn.close()
    return user


def format_name(username: str, english_name: str | None) -> str:
    username = (username or "").strip()
    en = (english_name or "").strip()
    return f"{username} ({en})" if en else username


def get_display_name(user_id: int) -> str:
    """Format: {팀명} {이름 (영어이름)} {직급}.

    Defensive cleanup:
    - If username/team accidentally contains a leading numeric prefix (e.g., "1 김희준"), strip it.
    """
    u = get_user_by_id(int(user_id))
    if not u:
        return str(user_id)

    _uid, username, english_name, _chat, team, role, *_rest = u

    import re

    def _strip_leading_number(s: str | None) -> str:
        s = (s or "").strip()
        # "1 김희준" or "1. 김희준" or "[1] 김희준"
        s = re.sub(r"^(\[?\(?\d+\]?\)?\.?\s+)", "", s)
        return s.strip()

    team = _strip_leading_number(team)
    username = _strip_leading_number(username)
    english_name = (english_name or "").strip()

    name = format_name(username, english_name)
    mapped = "PM" if role == "팀원" else "리더"  # 팀장/임원 포함
    parts = [p for p in [team, name, mapped] if p]
    return " ".join(parts) if parts else name

def clear_status_today(user_id: int, *, meal: str = "lunch", clear_hosting: bool = True):
    """Remove today's status row so UI shows 'Not Set' (per meal).

    If clear_hosting=True, also remove the user's hosting listing for today+meal.
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM daily_status WHERE date=? AND meal=? AND user_id=?", (today, meal, user_id))
    conn.commit()
    conn.close()

    if clear_hosting:
        try:
            delete_group(user_id, meal=meal)
        except Exception:
            pass


def update_status(user_id, status, *, meal: str = "lunch", kind: str | None = None, force: bool = False):
    """Set today's status (per meal).

    - meal: lunch | dinner
    - kind: (dinner only) 'meal' | 'drink'

    Rule: Booked is terminal for the day (cannot be downgraded) unless force=True.
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    kind = _norm_kind(kind)

    current = get_status_today(user_id, meal=meal)
    if (not force) and current == "Booked" and status not in ("Booked",):
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO daily_status (id, date, meal, user_id, status, kind)
        VALUES ((SELECT id FROM daily_status WHERE date=? AND meal=? AND user_id=?), ?, ?, ?, ?, ?)
        """,
        (today, meal, user_id, today, meal, user_id, status, kind),
    )
    conn.commit()
    conn.close()

    # If user explicitly sets to Free/Planning/Not Set, remove their hosting listing.
    # But do NOT delete hosting just because they became Booked.
    if status in ("Free", "Planning", "Not Set"):
        delete_group(user_id, meal=meal)


def delete_group(host_user_id: int, *, meal: str = "lunch"):
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_user_id))
    conn.commit()
    conn.close()


def upsert_group(
    host_user_id: int,
    member_names: str,
    seats_left: int,
    menu: str,
    payer_name: str | None = None,
    *,
    meal: str = "lunch",
    kind: str | None = None,
):
    """Upsert today's hosting group (per meal).

    kind: (dinner only) 'meal' | 'drink'
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    kind = _norm_kind(kind)

    conn = get_connection()
    c = conn.cursor()

    member_names = member_names or ""
    member_user_ids = str(host_user_id)

    c.execute(
        """
        INSERT OR REPLACE INTO lunch_groups (id, date, meal, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name, kind)
        VALUES ((SELECT id FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?), ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today,
            meal,
            host_user_id,
            today,
            meal,
            host_user_id,
            member_names,
            member_user_ids,
            int(seats_left),
            menu,
            payer_name or "",
            kind,
        ),
    )

    # Ensure host is in normalized members
    try:
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_user_id, host_user_id),
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


def get_groups_today(*, meal: str = "lunch", viewer_friends_ids: list[int] | None = None):
    """Return today's hosting groups for a meal.
    If viewer_friends_ids is provided, only show groups hosted by those friends.
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()

    query = """
        SELECT g.id, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name, g.kind
        FROM lunch_groups g
        JOIN users u ON u.user_id = g.host_user_id
        WHERE g.date=? AND g.meal=?
    """
    params = [today, meal]

    if viewer_friends_ids is not None:
        # Private mode filter
        if not viewer_friends_ids:
            conn.close()
            return []
        placeholders = ",".join(["?"] * len(viewer_friends_ids))
        query += f" AND g.host_user_id IN ({placeholders})"
        params.extend(viewer_friends_ids)

    query += " ORDER BY g.id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_group_by_host_on_date(host_user_id: int, date_str: str, *, meal: str = "lunch"):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.date, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name, g.kind
        FROM lunch_groups g
        JOIN users u ON u.user_id = g.host_user_id
        WHERE g.date=? AND g.meal=? AND g.host_user_id=?
        LIMIT 1
        """,
        (date_str, meal, host_user_id),
    )
    row = c.fetchone()

    # Defensive: ensure host is always a member (prevents chat/cancel issues)
    if row:
        try:
            c.execute(
                "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
                (date_str, meal, int(host_user_id), int(host_user_id)),
            )
            conn.commit()
        except Exception:
            pass

    conn.close()
    return row


def update_group_menu_payer(host_user_id: int, date_str: str, menu: str | None, payer_name: str | None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE lunch_groups SET menu=?, payer_name=? WHERE date=? AND host_user_id=?",
        (menu or "", payer_name or "", date_str, host_user_id),
    )
    conn.commit()
    conn.close()


def get_group_by_host_today(host_user_id: int, *, meal: str = "lunch"):
    return get_group_by_host_on_date(host_user_id, kst_today_iso(), meal=meal)


def ensure_member_in_group(host_user_id: int, user_id: int, date_str: str, *, meal: str = "lunch"):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
        (date_str, meal, host_user_id, user_id),
    )
    conn.commit()
    conn.close()


def ensure_fixed_group_today(host_user_id: int, *, meal: str = "lunch", kind: str | None = None):
    """Ensure a non-recruiting group exists (seats_left=0) for the host today."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    kind = _norm_kind(kind)
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO lunch_groups(date, meal, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name, kind) VALUES (?,?,?,?,?,?,?,?,?)",
            (today, meal, host_user_id, "", "", 0, "", "", kind),
        )
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_user_id, host_user_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_member_fixed_group(host_user_id: int, member_user_id: int, member_name: str, *, meal: str = "lunch") -> tuple[bool, str | None]:
    """Add member to host's fixed group (no seats decrement)."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    member_name = (member_name or "").strip()
    if not member_name:
        return False, "member_name이 비어있습니다."

    ensure_fixed_group_today(host_user_id, meal=meal)

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_user_id, member_user_id),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        _rebuild_group_legacy_fields(host_user_id, today, meal=meal)
    except Exception:
        pass

    return True, None


def accept_group_join(host_user_id: int, member_user_id: int, member_name: str, *, meal: str = "lunch") -> tuple[bool, str | None]:
    """Accept a join by ensuring membership + decrementing seats_left + syncing display fields."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    member_name = (member_name or "").strip()
    if not member_name:
        return False, "member_name이 비어있습니다."

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT seats_left FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?",
            (today, meal, host_user_id),
        )
        row = c.fetchone()
        if not row:
            return False, "모집글을 찾지 못했어요."

        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_user_id, host_user_id),
        )
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_user_id, member_user_id),
        )

        c.execute(
            "UPDATE lunch_groups SET seats_left = seats_left - 1 WHERE date=? AND meal=? AND host_user_id=? AND seats_left > 0",
            (today, meal, host_user_id),
        )
        if c.rowcount == 0:
            return False, "남은 자리가 없어요."

        conn.commit()
    finally:
        conn.close()

    try:
        _rebuild_group_legacy_fields(host_user_id, today, meal=meal)
    except Exception:
        pass

    return True, None


def add_member_to_group(host_user_id: int, member_user_id: int, member_name: str) -> tuple[bool, str | None]:
    """Append member to today's host group and decrement seats_left (atomic-ish).

    Uses normalized group_members + keeps legacy CSV fields in sync for display.
    """
    today = kst_today_iso()
    member_name = (member_name or "").strip()
    if not member_name:
        return False, "member_name이 비어있습니다."

    conn = get_connection()
    c = conn.cursor()
    try:
        # Ensure group exists
        c.execute(
            "SELECT member_names, member_user_ids, seats_left FROM lunch_groups WHERE date=? AND host_user_id=?",
            (today, host_user_id),
        )
        row = c.fetchone()
        if not row:
            return False, "모집글을 찾지 못했어요."

        member_names, member_user_ids, seats_left = row
        seats_left = int(seats_left) if seats_left is not None else 0

        # Already member?
        c.execute(
            "SELECT 1 FROM group_members WHERE date=? AND host_user_id=? AND user_id=?",
            (today, host_user_id, member_user_id),
        )
        if c.fetchone():
            return True, None

        if seats_left <= 0:
            return False, "남은 자리가 없어요."

        # Ensure host is in normalized members
        try:
            c.execute(
                "INSERT OR IGNORE INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
                (today, host_user_id, host_user_id),
            )
        except Exception:
            pass

        # Insert membership
        try:
            c.execute(
                "INSERT INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
                (today, host_user_id, member_user_id),
            )
        except sqlite3.IntegrityError:
            return True, None

        # Decrement seats
        c.execute(
            "UPDATE lunch_groups SET seats_left = seats_left - 1 WHERE date=? AND host_user_id=? AND seats_left > 0",
            (today, host_user_id),
        )
        if c.rowcount == 0:
            return False, "남은 자리가 없어요."

        # Sync legacy display fields
        ids = [x.strip() for x in (member_user_ids or "").split(",") if x.strip()]
        names = [n.strip() for n in (member_names or "").split(",") if n.strip()]
        if str(member_user_id) not in ids:
            ids.append(str(member_user_id))
            names.append(member_name)

        new_member_names = ", ".join(names)
        new_member_user_ids = ",".join(ids)
        c.execute(
            "UPDATE lunch_groups SET member_names=?, member_user_ids=? WHERE date=? AND host_user_id=?",
            (new_member_names, new_member_user_ids, today, host_user_id),
        )

        conn.commit()
        return True, None
    finally:
        conn.close()


def set_booked_for_group(host_user_id: int, *, meal: str = "lunch"):
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM group_members WHERE date=? AND meal=? AND host_user_id=?",
        (today, meal, host_user_id),
    )
    ids = [r[0] for r in c.fetchall()]
    conn.close()

    for uid in ids:
        try:
            update_status(int(uid), "Booked", meal=meal)
            cancel_pending_requests_for_user(int(uid), meal=meal)
        except Exception:
            continue


def get_groups_for_user_today(user_id: int, *, meal: str = "lunch"):
    """Groups where user_id is a member (normalized group_members)."""
    today = kst_today_iso()
    return get_groups_for_user_on_date(user_id, today, meal=meal)


def get_groups_for_user_on_date(user_id: int, date_str: str, *, meal: str = "lunch"):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.date, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name, g.kind
        FROM group_members gm
        JOIN lunch_groups g ON g.date = gm.date AND g.meal = gm.meal AND g.host_user_id = gm.host_user_id
        JOIN users u ON u.user_id = g.host_user_id
        WHERE gm.date=? AND gm.meal=? AND gm.user_id=?
        ORDER BY g.id DESC
        """,
        (date_str, meal, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def is_member_of_group(host_user_id: int, user_id: int, date_str: str, *, meal: str = "lunch") -> bool:
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM group_members WHERE date=? AND meal=? AND host_user_id=? AND user_id=? LIMIT 1",
        (date_str, meal, host_user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def list_group_members(host_user_id: int, date_str: str, *, meal: str = "lunch"):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT u.user_id, u.username, u.english_name
        FROM group_members gm
        JOIN users u ON u.user_id = gm.user_id
        WHERE gm.date=? AND gm.meal=? AND gm.host_user_id=?
        ORDER BY u.username
        """,
        (date_str, meal, host_user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def _rebuild_group_legacy_fields(host_user_id: int, date_str: str, *, meal: str = "lunch"):
    """Keep lunch_groups.member_names/member_user_ids in sync from normalized members."""
    meal = _norm_meal(meal)
    members = list_group_members(host_user_id, date_str, meal=meal)
    member_names = ", ".join([format_name(name, en) for _uid, name, en in members])
    member_user_ids = ",".join([str(uid) for uid, _name, _en in members])

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE lunch_groups SET member_names=?, member_user_ids=? WHERE date=? AND meal=? AND host_user_id=?",
        (member_names, member_user_ids, date_str, meal, host_user_id),
    )
    conn.commit()
    conn.close()


def _auto_cancel_group_if_single(host_user_id: int, date_str: str, *, meal: str = "lunch"):
    """If only one member remains, dissolve the group and clear remaining member status (per meal)."""
    meal = _norm_meal(meal)
    members = list_group_members(host_user_id, date_str, meal=meal)
    if len(members) != 1:
        return

    remaining_uid, _remaining_name, _remaining_en = members[0]

    try:
        cancel_accepted_for_users([int(remaining_uid)], meal=meal)
    except Exception:
        pass

    try:
        clear_status_today(int(remaining_uid), meal=meal)
    except Exception:
        pass

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM group_members WHERE date=? AND meal=? AND host_user_id=?", (date_str, meal, host_user_id))
    c.execute("DELETE FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?", (date_str, meal, host_user_id))
    conn.commit()
    conn.close()


def remove_member_from_group(host_user_id: int, user_id: int, date_str: str, *, meal: str = "lunch") -> tuple[bool, str | None]:
    """Remove a member from a host group and increment seats_left (per meal)."""
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM group_members WHERE date=? AND meal=? AND host_user_id=? AND user_id=?",
        (date_str, meal, host_user_id, user_id),
    )
    removed = c.rowcount > 0
    if not removed:
        conn.close()
        return False, "멤버가 그룹에 없어요."

    c.execute(
        "UPDATE lunch_groups SET seats_left = seats_left + 1 WHERE date=? AND meal=? AND host_user_id=?",
        (date_str, meal, host_user_id),
    )
    conn.commit()
    conn.close()

    _rebuild_group_legacy_fields(host_user_id, date_str, meal=meal)
    _auto_cancel_group_if_single(host_user_id, date_str, meal=meal)
    return True, None


def cancel_accepted_for_users(user_ids: list[int], *, meal: str = "lunch"):
    """Cancel today's accepted requests for the given users (per meal)."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    for uid in user_ids:
        c.execute(
            """
            UPDATE requests
            SET status='cancelled'
            WHERE date=? AND meal=? AND status='accepted' AND (from_user_id=? OR to_user_id=?)
            """,
            (today, meal, uid, uid),
        )
    conn.commit()
    conn.close()


def get_accepted_partners_today(user_id: int, *, meal: str = "lunch"):
    """For 1:1 accepted invites (no group), return the other user(s)."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END AS other_id,
               u.username
        FROM requests r
        JOIN users u ON u.user_id = (CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END)
        WHERE r.date=? AND r.meal=? AND r.status='accepted' AND r.group_host_user_id IS NULL
          AND (r.from_user_id=? OR r.to_user_id=?)
        """,
        (user_id, user_id, today, meal, user_id, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_latest_accepted_group_host_today(user_id: int, *, meal: str = "lunch") -> int | None:
    """If user accepted/joined a group today, return group_host_user_id."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT group_host_user_id
        FROM requests
        WHERE date=? AND meal=? AND status='accepted' AND group_host_user_id IS NOT NULL
          AND (from_user_id=? OR to_user_id=?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, meal, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row and row[0] is not None else None


def ensure_1to1_group_today(user_a: int, user_b: int, *, meal: str = "lunch", kind: str | None = None):
    """Ensure a lunch_groups record exists for a matched 1:1 (per meal).

    Host is deterministic (min user_id) to avoid duplicates.
    seats_left=0 by default.
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    kind = _norm_kind(kind)
    host_uid = int(min(user_a, user_b))
    other_uid = int(max(user_a, user_b))

    ua = get_user_by_id(int(user_a))
    ub = get_user_by_id(int(user_b))
    if not ua or not ub:
        return

    a_name = ua[1]
    b_name = ub[1]

    # create/update group
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            INSERT OR IGNORE INTO lunch_groups(date, meal, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name, kind)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (today, meal, host_uid, f"{a_name}, {b_name}", f"{host_uid},{other_uid}", 0, "", "", kind),
        )
        # ensure both members
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_uid, host_uid),
        )
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, meal, host_user_id, user_id) VALUES (?,?,?,?)",
            (today, meal, host_uid, other_uid),
        )
        conn.commit()
    finally:
        conn.close()

    # keep legacy fields aligned
    try:
        _rebuild_group_legacy_fields(host_uid, today, meal=meal)
    except Exception:
        pass


def get_latest_accepted_1to1_detail_today(user_id: int, *, meal: str = "lunch"):
    """Return (req_id, other_user_id, other_name, timestamp) for latest accepted 1:1 request."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id,
               CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END AS other_id,
               u.username,
               r.timestamp
        FROM requests r
        JOIN users u ON u.user_id = (CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END)
        WHERE r.date=? AND r.meal=? AND r.status='accepted' AND r.group_host_user_id IS NULL
          AND (r.from_user_id=? OR r.to_user_id=?)
        ORDER BY r.timestamp DESC
        LIMIT 1
        """,
        (user_id, user_id, today, meal, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def cancel_booking_for_user(user_id: int, *, meal: str = "lunch") -> tuple[bool, str | None]:
    """Cancel a booked meal (per meal)."""
    today = kst_today_iso()
    meal = _norm_meal(meal)

    groups = get_groups_for_user_on_date(user_id, today, meal=meal)
    if groups:
        _gid, _date, host_uid, _host_name, _member_names, _seats_left, _menu, _payer_name, _g_kind = groups[0]
        members = list_group_members(host_uid, today, meal=meal)
        member_ids = [uid for uid, _n, _en in members]

        # If I'm the host and I cancel, dissolve the whole group (even if >2)
        if int(host_uid) == int(user_id):
            related_ids_list = sorted(list(set(member_ids)))
            cancel_accepted_for_users(related_ids_list, meal=meal)
            for uid in related_ids_list:
                clear_status_today(int(uid), meal=meal)

            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM group_chat WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_uid))
            c.execute("DELETE FROM group_members WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_uid))
            c.execute("DELETE FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_uid))
            conn.commit()
            conn.close()
            return True, None

        if len(member_ids) <= 2:
            # cancel entire booking
            related_ids = set(member_ids)

            # safety: if members table is incomplete, also include latest accepted 1:1 partner
            d = get_latest_accepted_1to1_detail_today(user_id, meal=meal)
            if d:
                _req_id, other_id, _other_name, _ts = d
                related_ids.add(int(other_id))
                related_ids.add(int(user_id))

            related_ids_list = sorted(list(related_ids))
            cancel_accepted_for_users(related_ids_list, meal=meal)
            for uid in related_ids_list:
                clear_status_today(uid, meal=meal)

            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM group_members WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_uid))
            c.execute("DELETE FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=?", (today, meal, host_uid))
            conn.commit()
            conn.close()
            return True, None

        # group > 2: remove only this user
        ok, err = remove_member_from_group(host_uid, user_id, today, meal=meal)
        if not ok:
            return False, err

        cancel_accepted_for_users([user_id], meal=meal)
        clear_status_today(user_id, meal=meal)
        return True, None

    # No group: handle 1:1 accepted request
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, from_user_id, to_user_id
        FROM requests
        WHERE date=? AND meal=? AND status='accepted' AND group_host_user_id IS NULL
          AND (from_user_id=? OR to_user_id=?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, meal, user_id, user_id),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        # fallback: just clear me
        clear_status_today(user_id, meal=meal)
        return True, None

    req_id, from_uid, to_uid = row
    other = to_uid if from_uid == user_id else from_uid

    c.execute("UPDATE requests SET status='cancelled' WHERE id=?", (req_id,))
    conn.commit()
    conn.close()

    clear_status_today(user_id, meal=meal)
    clear_status_today(other, meal=meal)
    cancel_pending_requests_for_user(user_id, meal=meal)
    cancel_pending_requests_for_user(other, meal=meal)
    return True, None


def clear_group_chat(host_user_id: int, date_str: str, *, meal: str = "lunch"):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM group_chat WHERE date=? AND meal=? AND host_user_id=?", (date_str, meal, host_user_id))
    conn.commit()
    conn.close()


def _ensure_group_chat_meal_column(conn):
    """Runtime guard: older DBs may not have group_chat.meal."""
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(group_chat)")
        cols = {r[1] for r in c.fetchall()}
        if "meal" not in cols:
            c.execute("ALTER TABLE group_chat ADD COLUMN meal TEXT")
            # backfill
            c.execute("UPDATE group_chat SET meal='lunch' WHERE meal IS NULL OR meal='' ")
            try:
                c.execute(
                    "CREATE INDEX IF NOT EXISTS idx_group_chat_day_host ON group_chat(date, meal, host_user_id, timestamp)"
                )
            except Exception:
                pass
            conn.commit()
    except Exception:
        pass


def list_group_chat(host_user_id: int, date_str: str, *, meal: str = "lunch", limit: int = 200):
    meal = _norm_meal(meal)
    conn = get_connection()
    try:
        _ensure_group_chat_meal_column(conn)
        c = conn.cursor()
        c.execute(
            """
            SELECT user_id, username, message, timestamp
            FROM group_chat
            WHERE date=? AND meal=? AND host_user_id=?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (date_str, meal, host_user_id, int(limit)),
        )
        rows = c.fetchall()
        return rows
    except sqlite3.OperationalError as e:
        # fallback for legacy schema
        if "meal" in str(e).lower():
            c = conn.cursor()
            c.execute(
                """
                SELECT user_id, username, message, timestamp
                FROM group_chat
                WHERE date=? AND host_user_id=?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (date_str, host_user_id, int(limit)),
            )
            return c.fetchall()
        raise
    finally:
        conn.close()


def add_group_chat(host_user_id: int, user_id: int, username: str, message: str, date_str: str, *, meal: str = "lunch") -> tuple[bool, str | None]:
    meal = _norm_meal(meal)
    message = (message or "").strip()
    if not message:
        return False, "메시지를 입력해주세요."

    if not is_member_of_group(host_user_id, user_id, date_str, meal=meal):
        return False, "그룹 멤버만 채팅을 사용할 수 있어요."

    conn = get_connection()
    try:
        _ensure_group_chat_meal_column(conn)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO group_chat(date, meal, host_user_id, user_id, username, message, timestamp) VALUES (?,?,?,?,?,?,?)",
                (date_str, meal, host_user_id, user_id, username, message, kst_now_str()),
            )
        except sqlite3.OperationalError as e:
            # legacy fallback
            if "meal" in str(e).lower():
                c.execute(
                    "INSERT INTO group_chat(date, host_user_id, user_id, username, message, timestamp) VALUES (?,?,?,?,?,?)",
                    (date_str, host_user_id, user_id, username, message, kst_now_str()),
                )
            else:
                raise
        conn.commit()
        return True, None
    finally:
        conn.close()


def is_meal_expired(meal: str) -> bool:
    """Return True if current KST time is past the meal threshold.
    Lunch: 13:00 (1 PM), Dinner: 20:00 (8 PM)
    
    NOTE: Temporarily disabled for testing.
    """
    return False


def delegate_host(date_str: str, meal: str, old_host_id: int, new_host_id: int) -> tuple[bool, str | None]:
    """Transfer hosting responsibilities to another member.

    Notes:
    - Disallow if new_host already has a hosting group for same date+meal (unique constraint).
    """
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    try:
        # conflict check
        c.execute(
            "SELECT 1 FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=? LIMIT 1",
            (date_str, meal, int(new_host_id)),
        )
        if c.fetchone():
            return False, "선택한 사람은 이미 같은 시간대에 호스트로 등록되어 있어요. 다른 사람을 선택해줘."

        # Update lunch_groups host
        c.execute(
            "UPDATE lunch_groups SET host_user_id=? WHERE date=? AND meal=? AND host_user_id=?",
            (int(new_host_id), date_str, meal, int(old_host_id)),
        )
        if c.rowcount == 0:
            return False, "그룹을 찾을 수 없습니다."

        # Update group_members
        c.execute(
            "UPDATE group_members SET host_user_id=? WHERE date=? AND meal=? AND host_user_id=?",
            (int(new_host_id), date_str, meal, int(old_host_id)),
        )

        # Update group_chat
        try:
            c.execute(
                "UPDATE group_chat SET host_user_id=? WHERE date=? AND meal=? AND host_user_id=?",
                (int(new_host_id), date_str, meal, int(old_host_id)),
            )
        except Exception:
            pass

        # Update requests group_host_user_id
        c.execute(
            "UPDATE requests SET group_host_user_id=? WHERE date=? AND meal=? AND group_host_user_id=?",
            (int(new_host_id), date_str, meal, int(old_host_id)),
        )

        conn.commit()
    except Exception as e:
        conn.close()
        return False, str(e)

    # keep legacy display fields aligned (best-effort)
    try:
        _rebuild_group_legacy_fields(int(new_host_id), date_str, meal=meal)
    except Exception:
        pass

    conn.close()
    return True, None


def list_my_group_dates(user_id: int, *, meal: str = "lunch", limit: int = 30):
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT DISTINCT gm.date
        FROM group_members gm
        WHERE gm.user_id=? AND gm.meal=?
        ORDER BY gm.date DESC
        LIMIT ?
        """,
        (user_id, meal, limit),
    )
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def create_auth_session(user_id: int) -> str:
    token = secrets.token_hex(24)
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token


def get_user_by_session_token(token: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT u.user_id, u.username, u.telegram_chat_id, u.team, u.mbti, u.age, u.years, u.employee_id
        FROM auth_sessions s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.token=?
        """,
        (token,),
    )
    row = c.fetchone()
    conn.close()
    return row


def delete_auth_session(token: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()

def _has_host_group_today(user_id: int, *, meal: str = "lunch") -> bool:
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM lunch_groups WHERE date=? AND meal=? AND host_user_id=? LIMIT 1",
        (today, meal, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def get_all_statuses(*, meal: str = "lunch", viewer_friends_ids: list[int] | None = None):
    """Return all users + computed-safe status for today (per meal).
    If viewer_friends_ids is provided (private mode), filter the user list.
    """
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()

    query = """
        SELECT u.user_id, u.username, COALESCE(ds.status, 'Not Set') as status, u.telegram_chat_id, ds.kind
        FROM users u
        LEFT JOIN daily_status ds ON u.user_id = ds.user_id AND ds.date = ? AND ds.meal = ?
        WHERE 1=1
    """
    params = [today, meal]

    if viewer_friends_ids is not None:
        if not viewer_friends_ids:
            conn.close()
            return []
        placeholders = ",".join(["?"] * len(viewer_friends_ids))
        query += f" AND u.user_id IN ({placeholders})"
        params.extend(viewer_friends_ids)

    c.execute(query, params)
    results = c.fetchall()
    conn.close()

    fixed = []
    for user_id, username, status, chat_id, kind in results:
        if status == "Booked" and not has_accepted_today(int(user_id), meal=meal):
            status = "Not Set"
        if status == "Hosting" and not _has_host_group_today(int(user_id), meal=meal):
            status = "Not Set"
        fixed.append((user_id, username, status, chat_id, kind))
    return fixed


def search_users(query: str, exclude_id: int):
    conn = get_connection()
    c = conn.cursor()
    q = f"%{query}%"
    c.execute(
        "SELECT user_id, username, english_name, team FROM users WHERE (username LIKE ? OR english_name LIKE ? OR team LIKE ?) AND user_id != ? LIMIT 20",
        (q, q, q, exclude_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def _norm_meal(meal: str | None) -> str:
    m = (meal or "lunch").strip().lower()
    # Support private modes
    valid = ("lunch", "dinner", "lunch_p", "dinner_p")
    return m if m in valid else ("dinner" if "dinner" in m else "lunch")


def _norm_kind(kind: str | None) -> str | None:
    k = (kind or "").strip().lower()
    if not k:
        return None
    if k in ("meal", "rice", "밥"):
        return "meal"
    if k in ("drink", "술", "alcohol"):
        return "drink"
    return k


def get_status_row_today(user_id: int, *, meal: str = "lunch") -> tuple[str, str | None]:
    """Return (status, kind) for today+meal."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COALESCE(status,'Not Set'), kind FROM daily_status WHERE date=? AND meal=? AND user_id=?",
        (today, meal, user_id),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return "Not Set", None
    return row[0], row[1]


def get_status_today(user_id: int, *, meal: str = "lunch") -> str:
    return get_status_row_today(user_id, meal=meal)[0]

def create_request(
    from_user_id,
    to_user_id,
    group_host_user_id: int | None = None,
    *,
    meal: str = "lunch",
    kind: str | None = None,
):
    """Create an invite request for today (per meal).

    kind: (dinner only) 'meal' | 'drink'

    Returns: (request_id, error_message)
    """
    meal = _norm_meal(meal)
    kind = _norm_kind(kind)

    # time-out guard
    if is_meal_expired(meal):
        label = "점심" if meal == "lunch" else "저녁"
        return None, f"{label} 타임아웃(마감) 이후에는 새 초대를 보낼 수 없어요."

    # one-meal rule
    # If I'm inviting someone into my own hosting group (group_host_user_id == from_user_id),
    # allow even if I'm already Booked/Planning.
    if get_status_today(from_user_id, meal=meal) in ("Booked", "Planning"):
        if not (group_host_user_id and int(group_host_user_id) == int(from_user_id)):
            return None, "이미 점심약속이 있는것 같아요!"

    # Allow inviting a Booked user in two cases:
    # - join request to that booked host's group (group_host_user_id == to_user_id)
    # - host inviting someone into their own group while booked (group_host_user_id == from_user_id)
    if get_status_today(to_user_id, meal=meal) == "Booked":
        ok = False
        if group_host_user_id and int(group_host_user_id) == int(to_user_id):
            ok = True
        if group_host_user_id and int(group_host_user_id) == int(from_user_id):
            ok = True
        if not ok:
            return None, "이미 점심약속이 있는것 같아요!"

    today = kst_today_iso()
    conn = get_connection()
    c = conn.cursor()
    try:
        # Double-check latest status right before insert (reduce race issues)
        if get_status_today(from_user_id, meal=meal) in ("Booked",):
            return None, "이미 약속이 있는것 같아요!"
        if get_status_today(to_user_id, meal=meal) in ("Booked",):
            # allow only join-to-group exceptions (same logic as above)
            ok = False
            if group_host_user_id and int(group_host_user_id) == int(to_user_id):
                ok = True
            if group_host_user_id and int(group_host_user_id) == int(from_user_id):
                ok = True
            if not ok:
                return None, "이미 약속이 있는것 같아요!"

        # If there is already a pending invite from->to today, don't spam.
        c.execute(
            """
            SELECT 1
            FROM requests
            WHERE date=? AND meal=? AND from_user_id=? AND to_user_id=? AND status='pending'
            LIMIT 1
            """,
            (today, meal, from_user_id, to_user_id),
        )
        if c.fetchone():
            return None, "이미 대기중인 요청이 있어요."

        c.execute(
            "INSERT INTO requests (from_user_id, to_user_id, group_host_user_id, date, meal, status, kind) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (from_user_id, to_user_id, group_host_user_id, today, meal, kind),
        )
        conn.commit()
        req_id = c.lastrowid
    finally:
        conn.close()

    # Pending request behavior:
    # - Sender becomes Planning (prevent spamming/duplicate actions)
    # - Receiver stays as-is (so they remain Free/Not Set until they accept)
    set_planning(from_user_id, meal=meal)
    return req_id, None


def update_request_status(request_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()


def cancel_pending_requests_for_user(user_id: int, *, meal: str = "lunch"):
    """Cancel pending invites involving the user today (per meal)."""
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE requests
        SET status='cancelled'
        WHERE date=? AND meal=?
          AND status='pending'
          AND (from_user_id=? OR to_user_id=?)
          AND COALESCE(group_host_user_id, -1) != ?
        """,
        (today, meal, user_id, user_id, user_id),
    )
    conn.commit()
    conn.close()


def has_pending_outgoing_today(user_id: int, *, meal: str = "lunch") -> bool:
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM requests WHERE date=? AND meal=? AND from_user_id=? AND status='pending' LIMIT 1",
        (today, meal, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def cancel_request(request_id):
    update_request_status(request_id, "cancelled")


def get_pending_request_between(from_user_id, to_user_id, *, meal: str = "lunch"):
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, status
        FROM requests
        WHERE date=? AND meal=? AND from_user_id=? AND to_user_id=?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, meal, from_user_id, to_user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def list_incoming_requests(user_id, *, meal: str = "lunch"):
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id, r.from_user_id, u.username, r.status, r.timestamp, r.group_host_user_id, r.kind
        FROM requests r
        JOIN users u ON u.user_id = r.from_user_id
        WHERE r.date=? AND r.meal=? AND r.to_user_id=?
        ORDER BY r.timestamp DESC
        """,
        (today, meal, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def list_outgoing_requests(user_id, *, meal: str = "lunch"):
    today = kst_today_iso()
    meal = _norm_meal(meal)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id, r.to_user_id, u.username, r.status, r.timestamp, r.group_host_user_id, r.kind
        FROM requests r
        JOIN users u ON u.user_id = r.to_user_id
        WHERE r.date=? AND r.meal=? AND r.from_user_id=?
        ORDER BY r.timestamp DESC
        """,
        (today, meal, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows

# --- Friend Management Logic ---

def send_friend_request(from_uid: int, to_uid: int) -> tuple[bool, str | None]:
    if from_uid == to_uid:
        return False, "나 자신에게는 신청할 수 없어요."
    conn = get_connection()
    c = conn.cursor()
    try:
        # Check existing (either direction)
        c.execute(
            "SELECT status FROM friends WHERE (requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)",
            (from_uid, to_uid, to_uid, from_uid),
        )
        row = c.fetchone()
        if row:
            return False, f"이미 신청 중이거나 친구 상태입니다. (상태: {row[0]})"

        c.execute(
            "INSERT INTO friends (requester_id, target_id, status) VALUES (?, ?, 'pending')",
            (from_uid, to_uid),
        )
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def accept_friend_request(target_uid: int, requester_uid: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE friends SET status='accepted' WHERE requester_id=? AND target_id=? AND status='pending'",
        (requester_uid, target_uid),
    )
    ok = c.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def remove_friend(uid1: int, uid2: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM friends WHERE (requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)",
        (uid1, uid2, uid2, uid1),
    )
    conn.commit()
    conn.close()


def list_friends(user_id: int) -> list[int]:
    """Return list of user_ids who are 'accepted' friends."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            SELECT requester_id FROM friends WHERE target_id=? AND status='accepted'
            UNION
            SELECT target_id FROM friends WHERE requester_id=? AND status='accepted'
            """,
            (user_id, user_id),
        )
        ids = [r[0] for r in c.fetchall()]
        return ids
    except Exception:
        return []
    finally:
        conn.close()


def list_pending_requests(user_id: int) -> list[dict]:
    """Requests sent TO me that I haven't accepted yet."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            """
            SELECT f.requester_id, u.username, u.english_name, u.team
            FROM friends f
            JOIN users u ON f.requester_id = u.user_id
            WHERE f.target_id=? AND f.status='pending'
            """,
            (user_id,),
        )
        rows = c.fetchall()
        return [{"user_id": r[0], "username": r[1], "english_name": r[2], "team": r[3]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
