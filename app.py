import streamlit as st
import datetime
import db
import bot

# Initialize DB on first run
db.init_db()

st.set_page_config(page_title="Lunch Buddy 🍱", layout="wide")

def main():
    st.title("🍱 Lunch Buddy: 오늘 점심 뭐 먹지?")
    st.markdown("---")

    # --- User Identification (Sidebar) ---
    with st.sidebar:
        st.header("👤 내 정보")
        username = st.text_input("이름 (닉네임)", key="username_input")
        chat_id = st.text_input(
            "텔레그램 Chat ID (선택)",
            help="초기엔 비워도 됩니다. (추후: 봇 /start로 자동 연결 예정)",
        )

        if st.button("등록 / 로그인"):
            if username:
                existing = db.get_user(username)
                if not existing:
                    db.register_user(username, chat_id or None)
                    st.success(f"반가워요, {username}님! 등록되었습니다.")
                else:
                    st.info(f"어서오세요, {username}님!")
                    # Optional: update chat id if user typed it now
                    if chat_id:
                        db.update_user_chat_id(existing[0], chat_id)

                st.session_state["user"] = {"username": username}
                st.rerun()

    # check session
    if "user" not in st.session_state:
        st.warning("👈 왼쪽 사이드바에서 먼저 본인의 이름을 입력해주세요!")
        st.stop()
    
    current_user = st.session_state["user"]["username"]
    user_record = db.get_user(current_user)  # ID fetch needed for DB ops
    if not user_record:
        st.error("사용자 정보를 찾을 수 없습니다. 다시 로그인해주세요.")
        st.stop()
    
    user_id = user_record[0]

    # --- Status Setting ---
    st.subheader(f"👋 {current_user}님의 오늘 상태는?")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🟢 점약 없어요 불러주세요", use_container_width=True):
            db.update_status(user_id, "Free")
            st.toast("상태 변경 완료: 점약 없음 🟢")
            st.rerun()

    with col2:
        if st.button("🟠 점약을 잡는 중이에요", use_container_width=True):
            db.update_status(user_id, "Planning")
            st.toast("상태 변경 완료: 점약 잡는 중 🟠")
            st.rerun()

    st.markdown("---")

    # --- Requests (Inbox/Outbox) ---
    st.subheader("📩 오늘 받은 점심 초대")
    incoming = db.list_incoming_requests(user_id)
    if not incoming:
        st.caption("아직 받은 초대가 없어요.")
    else:
        for req_id, from_uid, from_name, status, ts in incoming:
            with st.container(border=True):
                st.write(f"**{from_name}** → 나")
                st.caption(f"상태: {status} · {ts}")

                if status == "pending":
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ 수락", key=f"acc_{req_id}", use_container_width=True):
                            db.update_request_status(req_id, "accepted")
                            # Optional: notify sender
                            sender = db.get_user_by_id(from_uid)
                            if sender and sender[2]:
                                bot.send_telegram_msg(sender[2], f"✅ [Lunch Buddy] {current_user}님이 점심 초대를 수락했어요.")
                            st.success("수락 완료")
                            st.rerun()
                    with c2:
                        if st.button("❌ 거절", key=f"dec_{req_id}", use_container_width=True):
                            db.update_request_status(req_id, "declined")
                            sender = db.get_user_by_id(from_uid)
                            if sender and sender[2]:
                                bot.send_telegram_msg(sender[2], f"❌ [Lunch Buddy] {current_user}님이 오늘은 어렵다고 했어요.")
                            st.info("거절 처리됨")
                            st.rerun()

    st.subheader("📤 오늘 내가 보낸 초대")
    outgoing = db.list_outgoing_requests(user_id)
    if not outgoing:
        st.caption("아직 보낸 초대가 없어요.")
    else:
        for req_id, to_uid, to_name, status, ts in outgoing:
            with st.container(border=True):
                st.write(f"나 → **{to_name}**")
                st.caption(f"상태: {status} · {ts}")
                if status == "pending":
                    if st.button("취소", key=f"cancel_{req_id}"):
                        db.cancel_request(req_id)
                        st.toast("요청을 취소했어요")
                        st.rerun()

    st.markdown("---")

    # --- Dashboard (Others' Status) ---
    st.subheader("👀 동료들의 점심 현황")

    all_statuses = db.get_all_statuses()

    # Filter out self
    others = [s for s in all_statuses if s[1] != current_user]
    myself = [s for s in all_statuses if s[1] == current_user]

    # Display My Status
    if myself:
        my_status = myself[0][2]
        if my_status == "Free":
            st.info("현재 내 상태: **점약 없음(불러주세요)** 🟢")
        elif my_status == "Planning":
            st.info("현재 내 상태: **점약 잡는 중** 🟠")
        elif my_status == "Not Set":
            st.warning("현재 내 상태: **아직 미설정**")
        else:
            st.info(f"현재 내 상태: **{my_status}**")

    if not others:
        st.write("아직 등록된 다른 동료가 없어요.")
    else:
        # Always show only people who said "call me" (Free)
        others = [o for o in others if o[2] == "Free"]

        cols = st.columns(4)
        for i, (uid, uname, status, t_chat_id) in enumerate(others):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}")

                    status_display = "⚪ 미설정"
                    if status == "Free":
                        status_display = "🟢 점약 없음 (불러주세요)"
                    elif status == "Planning":
                        status_display = "🟠 점약 잡는 중"

                    st.write(f"상태: {status_display}")

                    # Invite action
                    if status == "Free":
                        existing_req = db.get_pending_request_between(user_id, uid)
                        disabled = bool(existing_req and existing_req[1] == "pending")

                        if st.button(
                            "🍚 밥 먹자고 찌르기!",
                            key=f"req_{uid}",
                            disabled=disabled,
                            use_container_width=True,
                        ):
                            req_id = db.create_request(user_id, uid)
                            if not req_id:
                                st.warning("이미 오늘 같은 요청을 보냈어요.")
                            else:
                                msg = (
                                    f"🍚 [Lunch Buddy] **{current_user}**님이 점심 같이 먹자고 요청했어요!\n\n"
                                    "(앱에서 수락/거절할 수 있어요)"
                                )
                                success = bot.send_telegram_msg(t_chat_id, msg)
                                if success:
                                    st.success(f"{uname}님에게 알림을 보냈어요! 📲")
                                else:
                                    st.info("요청은 저장했지만, 텔레그램 알림은 못 보냈어요(상대 Chat ID 미연결).")
                                st.rerun()

                        if disabled:
                            st.caption("이미 오늘 초대를 보냈어요(대기중).")

if __name__ == "__main__":
    main()
