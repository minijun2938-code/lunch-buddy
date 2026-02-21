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
                  member_user_ids TEXT,
                  seats_left INTEGER,
                  menu TEXT,
                  payer_name TEXT,
                  UNIQUE(date, host_user_id))'''
    )

    # Migration: add member_user_ids / payer_name if missing (legacy)
    c.execute("PRAGMA table_info(lunch_groups)")
    gcols = {row[1] for row in c.fetchall()}
    if "member_user_ids" not in gcols:
        c.execute("ALTER TABLE lunch_groups ADD COLUMN member_user_ids TEXT")
    if "payer_name" not in gcols:
        c.execute("ALTER TABLE lunch_groups ADD COLUMN payer_name TEXT")

    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_groups_day
           ON lunch_groups(date)"""
    )

    # Normalized group members (new)
    c.execute(
        '''CREATE TABLE IF NOT EXISTS group_members
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT,
                  host_user_id INTEGER,
                  user_id INTEGER,
                  UNIQUE(date, host_user_id, user_id))'''
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_group_members_day_host
           ON group_members(date, host_user_id)"""
    )
    c.execute(
        """CREATE INDEX IF NOT EXISTS idx_group_members_day_user
           ON group_members(date, user_id)"""
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

    # Requests table
    # status: pending | accepted | declined | cancelled
    c.execute(
        '''CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user_id INTEGER,
                  to_user_id INTEGER,
                  group_host_user_id INTEGER,
                  date TEXT,
                  status TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)'''
    )

    # Migration: add group_host_user_id if missing
    c.execute("PRAGMA table_info(requests)")
    rcols = {row[1] for row in c.fetchall()}
    if "group_host_user_id" not in rcols:
        c.execute("ALTER TABLE requests ADD COLUMN group_host_user_id INTEGER")

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
            INSERT INTO users (username, team, role, mbti, age, years, employee_id, pin_salt, pin_hash, telegram_chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, team, role, mbti, int(age), int(years), employee_id, salt, pin_hash, chat_id),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 사번(employee_id)입니다."
    finally:
        conn.close()


def verify_login(employee_id: str, pin: str) -> tuple[bool, tuple | None]:
    """PIN-based login (4 digits). Returns (ok, user_row)."""
    employee_id = (employee_id or "").strip().lower()
    user = get_user_by_employee_id(employee_id)
    if not user:
        return False, None

    user_id, username, telegram_chat_id, team, role, mbti, age, years, emp_id, salt, pin_hash = user
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
    # Planning should not override Booked
    update_status(user_id, "Planning")


def has_accepted_today(user_id: int) -> bool:
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT 1
        FROM requests
        WHERE date=? AND status='accepted' AND (from_user_id=? OR to_user_id=?)
        LIMIT 1
        """,
        (today, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def reconcile_user_today(user_id: int):
    """Make Booked highest priority if any accepted invite exists today."""
    if has_accepted_today(user_id):
        update_status(user_id, "Booked")

def get_user_by_employee_id(employee_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT user_id, username, telegram_chat_id, team, role, mbti, age, years, employee_id, pin_salt, pin_hash
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

def clear_status_today(user_id: int, *, clear_hosting: bool = True):
    """Remove today's status row so UI shows 'Not Set'.

    If clear_hosting=True, also remove the user's hosting listing for today.
    """
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM daily_status WHERE date=? AND user_id=?", (today, user_id))
    conn.commit()
    conn.close()

    if clear_hosting:
        try:
            delete_group(user_id)
        except Exception:
            pass


def update_status(user_id, status, *, force: bool = False):
    """Set today's status.

    Rule: Booked is terminal for the day (cannot be downgraded),
    but we still allow creating a hosting group while Booked.

    Use force=True for admin/cleanup flows (e.g., cancellation).
    """
    today = datetime.date.today().isoformat()

    current = get_status_today(user_id)
    if (not force) and current == "Booked" and status not in ("Booked",):
        # Do not downgrade Booked.
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO daily_status (id, date, user_id, status) VALUES ((SELECT id FROM daily_status WHERE date=? AND user_id=?), ?, ?, ?)",
        (today, user_id, today, user_id, status),
    )
    conn.commit()
    conn.close()

    if status == "Booked":
        cancel_pending_requests_for_user(user_id)

    # If user explicitly sets to Free/Planning/Not Set, remove their hosting listing.
    # But do NOT delete hosting just because they became Booked.
    if status in ("Free", "Planning", "Not Set"):
        delete_group(user_id)


def delete_group(host_user_id: int):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lunch_groups WHERE date=? AND host_user_id=?", (today, host_user_id))
    conn.commit()
    conn.close()


def upsert_group(host_user_id: int, member_names: str, seats_left: int, menu: str, payer_name: str | None = None):
    """Upsert today's hosting group.

    Ensures host is registered as a member in group_members.
    """
    today = datetime.date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()

    # Keep legacy CSV fields for display
    member_names = member_names or ""
    member_user_ids = str(host_user_id)

    c.execute(
        """
        INSERT OR REPLACE INTO lunch_groups (id, date, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name)
        VALUES ((SELECT id FROM lunch_groups WHERE date=? AND host_user_id=?), ?, ?, ?, ?, ?, ?, ?)
        """,
        (today, host_user_id, today, host_user_id, member_names, member_user_ids, int(seats_left), menu, payer_name or ""),
    )

    # Ensure host is in normalized members
    try:
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
            (today, host_user_id, host_user_id),
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


def get_groups_today():
    """Return today's hosting groups.

    Hosts may be Booked (e.g., 1:1 already fixed but still recruiting more).
    We treat the existence of a lunch_groups row as 'hosting'.
    """
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name
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


def get_group_by_host_on_date(host_user_id: int, date_str: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.date, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name
        FROM lunch_groups g
        JOIN users u ON u.user_id = g.host_user_id
        WHERE g.date=? AND g.host_user_id=?
        LIMIT 1
        """,
        (date_str, host_user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def get_group_by_host_today(host_user_id: int):
    return get_group_by_host_on_date(host_user_id, datetime.date.today().isoformat())


def ensure_member_in_group(host_user_id: int, user_id: int, date_str: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
        (date_str, host_user_id, user_id),
    )
    conn.commit()
    conn.close()


def add_member_to_group(host_user_id: int, member_user_id: int, member_name: str) -> tuple[bool, str | None]:
    """Append member to today's host group and decrement seats_left (atomic-ish).

    Uses normalized group_members + keeps legacy CSV fields in sync for display.
    """
    today = datetime.date.today().isoformat()
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


def set_booked_for_group(host_user_id: int):
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM group_members WHERE date=? AND host_user_id=?",
        (today, host_user_id),
    )
    ids = [r[0] for r in c.fetchall()]
    conn.close()

    for uid in ids:
        try:
            update_status(int(uid), "Booked")
            cancel_pending_requests_for_user(int(uid))
        except Exception:
            continue


def get_groups_for_user_today(user_id: int):
    """Groups where user_id is a member (normalized group_members)."""
    today = datetime.date.today().isoformat()
    return get_groups_for_user_on_date(user_id, today)


def get_groups_for_user_on_date(user_id: int, date_str: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT g.id, g.date, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name
        FROM group_members gm
        JOIN lunch_groups g ON g.date = gm.date AND g.host_user_id = gm.host_user_id
        JOIN users u ON u.user_id = g.host_user_id
        WHERE gm.date=? AND gm.user_id=?
        ORDER BY g.id DESC
        """,
        (date_str, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def list_group_members(host_user_id: int, date_str: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT u.user_id, u.username
        FROM group_members gm
        JOIN users u ON u.user_id = gm.user_id
        WHERE gm.date=? AND gm.host_user_id=?
        ORDER BY u.username
        """,
        (date_str, host_user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def _rebuild_group_legacy_fields(host_user_id: int, date_str: str):
    """Keep lunch_groups.member_names/member_user_ids in sync from normalized members."""
    members = list_group_members(host_user_id, date_str)
    member_names = ", ".join([name for _uid, name in members])
    member_user_ids = ",".join([str(uid) for uid, _name in members])

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE lunch_groups SET member_names=?, member_user_ids=? WHERE date=? AND host_user_id=?",
        (member_names, member_user_ids, date_str, host_user_id),
    )
    conn.commit()
    conn.close()


def remove_member_from_group(host_user_id: int, user_id: int, date_str: str) -> tuple[bool, str | None]:
    """Remove a member from a host group and increment seats_left."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM group_members WHERE date=? AND host_user_id=? AND user_id=?",
        (date_str, host_user_id, user_id),
    )
    removed = c.rowcount > 0
    if not removed:
        conn.close()
        return False, "멤버가 그룹에 없어요."

    c.execute(
        "UPDATE lunch_groups SET seats_left = seats_left + 1 WHERE date=? AND host_user_id=?",
        (date_str, host_user_id),
    )
    conn.commit()
    conn.close()

    _rebuild_group_legacy_fields(host_user_id, date_str)
    return True, None


def cancel_accepted_for_users(user_ids: list[int]):
    """Cancel today's accepted requests for the given users."""
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    for uid in user_ids:
        c.execute(
            """
            UPDATE requests
            SET status='cancelled'
            WHERE date=? AND status='accepted' AND (from_user_id=? OR to_user_id=?)
            """,
            (today, uid, uid),
        )
    conn.commit()
    conn.close()


def get_accepted_partners_today(user_id: int):
    """For 1:1 accepted lunches (no group), return the other user(s)."""
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END AS other_id,
               u.username
        FROM requests r
        JOIN users u ON u.user_id = (CASE WHEN r.from_user_id=? THEN r.to_user_id ELSE r.from_user_id END)
        WHERE r.date=? AND r.status='accepted' AND r.group_host_user_id IS NULL
          AND (r.from_user_id=? OR r.to_user_id=?)
        """,
        (user_id, user_id, today, user_id, user_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_latest_accepted_group_host_today(user_id: int) -> int | None:
    """If user accepted/joined a group today, return group_host_user_id."""
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT group_host_user_id
        FROM requests
        WHERE date=? AND status='accepted' AND group_host_user_id IS NOT NULL
          AND (from_user_id=? OR to_user_id=?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row and row[0] is not None else None


def ensure_1to1_group_today(user_a: int, user_b: int):
    """Ensure a lunch_groups record exists for a matched 1:1 so we can store/show menu/payer.

    Host is deterministic (min user_id) to avoid duplicates.
    seats_left=0 by default.
    """
    today = datetime.date.today().isoformat()
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
            INSERT OR IGNORE INTO lunch_groups(date, host_user_id, member_names, member_user_ids, seats_left, menu, payer_name)
            VALUES (?,?,?,?,?,?,?)
            """,
            (today, host_uid, f"{a_name}, {b_name}", f"{host_uid},{other_uid}", 0, "", ""),
        )
        # ensure both members
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
            (today, host_uid, host_uid),
        )
        c.execute(
            "INSERT OR IGNORE INTO group_members(date, host_user_id, user_id) VALUES (?,?,?)",
            (today, host_uid, other_uid),
        )
        conn.commit()
    finally:
        conn.close()

    # keep legacy fields aligned
    try:
        _rebuild_group_legacy_fields(host_uid, today)
    except Exception:
        pass


def get_latest_accepted_1to1_detail_today(user_id: int):
    """Return (req_id, other_user_id, other_name, timestamp) for latest accepted 1:1 request."""
    today = datetime.date.today().isoformat()
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
        WHERE r.date=? AND r.status='accepted' AND r.group_host_user_id IS NULL
          AND (r.from_user_id=? OR r.to_user_id=?)
        ORDER BY r.timestamp DESC
        LIMIT 1
        """,
        (user_id, user_id, today, user_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def cancel_booking_for_user(user_id: int) -> tuple[bool, str | None]:
    """Cancel a booked lunch.

    - If 1:1 booking: cancel both sides (set statuses Free).
    - If group booking (>2): remove only this user from the group (set status Free).
    """
    today = datetime.date.today().isoformat()

    # If user is in a group, use that as source of truth.
    groups = get_groups_for_user_on_date(user_id, today)
    if groups:
        _gid, _date, host_uid, _host_name, _member_names, _seats_left, _menu = groups[0]
        members = list_group_members(host_uid, today)
        member_ids = [uid for uid, _n in members]

        if len(member_ids) <= 2:
            # cancel entire booking
            related_ids = set(member_ids)

            # safety: if members table is incomplete, also include latest accepted 1:1 partner
            d = get_latest_accepted_1to1_detail_today(user_id)
            if d:
                _req_id, other_id, _other_name, _ts = d
                related_ids.add(int(other_id))
                related_ids.add(int(user_id))

            related_ids_list = sorted(list(related_ids))
            cancel_accepted_for_users(related_ids_list)
            for uid in related_ids_list:
                clear_status_today(uid)

            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM group_members WHERE date=? AND host_user_id=?", (today, host_uid))
            c.execute("DELETE FROM lunch_groups WHERE date=? AND host_user_id=?", (today, host_uid))
            conn.commit()
            conn.close()
            return True, None

        # group > 2: remove only this user
        ok, err = remove_member_from_group(host_uid, user_id, today)
        if not ok:
            return False, err

        cancel_accepted_for_users([user_id])
        clear_status_today(user_id)
        return True, None

    # No group: handle 1:1 accepted request
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, from_user_id, to_user_id
        FROM requests
        WHERE date=? AND status='accepted' AND group_host_user_id IS NULL
          AND (from_user_id=? OR to_user_id=?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (today, user_id, user_id),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        # fallback: just clear me
        clear_status_today(user_id)
        return True, None

    req_id, from_uid, to_uid = row
    other = to_uid if from_uid == user_id else from_uid

    c.execute("UPDATE requests SET status='cancelled' WHERE id=?", (req_id,))
    conn.commit()
    conn.close()

    clear_status_today(user_id)
    clear_status_today(other)
    cancel_pending_requests_for_user(user_id)
    cancel_pending_requests_for_user(other)
    return True, None


def list_my_group_dates(user_id: int, limit: int = 30):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT DISTINCT gm.date
        FROM group_members gm
        WHERE gm.user_id=?
        ORDER BY gm.date DESC
        LIMIT ?
        """,
        (user_id, limit),
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

def _has_host_group_today(user_id: int) -> bool:
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM lunch_groups WHERE date=? AND host_user_id=? LIMIT 1",
        (today, user_id),
    )
    row = c.fetchone()
    conn.close()
    return bool(row)


def get_all_statuses():
    """Return all users + computed-safe status for today.

    Defensive logic to avoid stale UI:
    - If stored status is Booked but there is no accepted request today → treat as Not Set.
    - If stored status is Hosting but there is no lunch_groups row today → treat as Not Set.
    """
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

    fixed = []
    for user_id, username, status, chat_id in results:
        if status == "Booked" and not has_accepted_today(int(user_id)):
            status = "Not Set"
        if status == "Hosting" and not _has_host_group_today(int(user_id)):
            status = "Not Set"
        fixed.append((user_id, username, status, chat_id))
    return fixed


def get_status_today(user_id: int) -> str:
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COALESCE(status,'Not Set') FROM daily_status WHERE date=? AND user_id=?",
        (today, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else "Not Set"

def create_request(from_user_id, to_user_id, group_host_user_id: int | None = None):
    """Create a lunch invite request for today.

    Rules:
    - If either side is already Booked today, block.
    - Side effect: both requester and receiver become "Planning".

    Returns: (request_id, error_message)
    """
    # one-lunch rule
    if get_status_today(from_user_id) == "Booked":
        return None, "이미 점심약속이 있는것 같아요!"

    # Allow inviting a Booked host ONLY when it's a join request to that host's group.
    if get_status_today(to_user_id) == "Booked" and not (group_host_user_id and int(group_host_user_id) == int(to_user_id)):
        return None, "이미 점심약속이 있는것 같아요!"

    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO requests (from_user_id, to_user_id, group_host_user_id, date, status) VALUES (?, ?, ?, ?, 'pending')",
            (from_user_id, to_user_id, group_host_user_id, today),
        )
        conn.commit()
        req_id = c.lastrowid
    except sqlite3.IntegrityError:
        # A request between the same pair already exists today (unique index).
        # If the previous one was cancelled/declined, allow re-request by reviving it.
        c.execute(
            """
            SELECT id, status
            FROM requests
            WHERE date=? AND from_user_id=? AND to_user_id=?
            LIMIT 1
            """,
            (today, from_user_id, to_user_id),
        )
        row = c.fetchone()
        if not row:
            return None, "이미 오늘 같은 요청을 보냈어요."

        existing_id, existing_status = row
        if existing_status in ("cancelled", "declined"):
            c.execute(
                """
                UPDATE requests
                SET status='pending', group_host_user_id=?, timestamp=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (group_host_user_id, existing_id),
            )
            conn.commit()
            req_id = existing_id
        else:
            return None, "이미 오늘 같은 요청을 보냈어요."
    finally:
        conn.close()

    set_planning(from_user_id)
    set_planning(to_user_id)
    return req_id, None


def update_request_status(request_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()


def cancel_pending_requests_for_user(user_id: int):
    """When user is Booked, cancel all other pending invites involving them today."""
    today = datetime.date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE requests
        SET status='cancelled'
        WHERE date=? AND status='pending' AND (from_user_id=? OR to_user_id=?)
        """,
        (today, user_id, user_id),
    )
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
        SELECT r.id, r.from_user_id, u.username, r.status, r.timestamp, r.group_host_user_id
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
        SELECT r.id, r.to_user_id, u.username, r.status, r.timestamp, r.group_host_user_id
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
