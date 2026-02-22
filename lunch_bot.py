import os
import requests


def _get_bot_token() -> str | None:
    # Prefer Streamlit secrets, then environment variable.
    try:
        import streamlit as st  # optional

        token = st.secrets.get("TELEGRAM_BOT_TOKEN")
        if token:
            return str(token)
    except Exception:
        pass

    return os.environ.get("TELEGRAM_BOT_TOKEN")


def send_telegram_msg(chat_id: str | None, text: str) -> bool:
    token = _get_bot_token()
    if not token or not chat_id:
        print("Telegram bot not configured or chat_id missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending telegram: {e}")
        return False


def get_bot_username() -> str | None:
    """Read bot username from Streamlit secrets/env.

    Needed for deep link: https://t.me/<username>?start=<payload>
    """
    try:
        import streamlit as st
        u = st.secrets.get("TELEGRAM_BOT_USERNAME")
        if u:
            return str(u).lstrip("@").strip()
    except Exception:
        pass

    u = os.environ.get("TELEGRAM_BOT_USERNAME")
    return (u or "").lstrip("@").strip() or None


def get_updates(offset: int | None = None, timeout: int = 0):
    token = _get_bot_token()
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": int(timeout)}
    if offset is not None:
        params["offset"] = int(offset)
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _extract_start_payload(text: str) -> str | None:
    text = (text or "").strip()
    if not text.startswith("/start"):
        return None
    # Telegram deep link comes as: "/start <payload>"
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


def try_register_chat_id_for_employee(employee_id: str, *, max_scan: int = 200) -> tuple[bool, str | None, str | None]:
    """Scan recent getUpdates and find /start <employee_id>.

    Returns: (ok, err, chat_id)
    """
    employee_id = (employee_id or "").strip().lower()
    if not employee_id:
        return False, "사번이 비어있습니다.", None

    data = get_updates()
    if not data or not data.get("ok"):
        return False, "봇 업데이트를 불러오지 못했어요(토큰/권한 확인 필요).", None

    updates = data.get("result") or []
    updates = updates[-max_scan:]

    # Search from newest
    for u in reversed(updates):
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            continue
        text = msg.get("text") or ""
        payload = _extract_start_payload(text)
        if not payload:
            continue
        if payload.strip().lower() != employee_id:
            continue
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        return True, None, str(chat_id)

    return False, "텔레그램에서 봇을 열고 '시작(Start)'을 눌러주세요. (연동 확인이 아직 안 됐어요)", None
