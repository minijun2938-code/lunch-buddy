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
