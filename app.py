import streamlit as st
import datetime
import db
import bot

# Initialize DB on first run
# (Streamlit Cloud may reset local filesystem; treat this as MVP)
db.init_db()

# Daily reset is already implicit because all reads/writes are scoped by `date=today`.
# We keep DB history, but every new day starts clean in the UI.

today_str = datetime.date.today().isoformat()

st.set_page_config(page_title=f"Lunch Buddy 🍱 ({today_str})", layout="wide")


def _load_user_from_query():
    emp = st.query_params.get("emp")
    if not emp:
        return
    u = db.get_user_by_employee_id(str(emp).strip().lower())
    if not u:
        return
    user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, *_ = u
    st.session_state["user"] = {
        "user_id": user_id,
        "username": username,
        "employee_id": emp_id,
        "telegram_chat_id": telegram_chat_id,
    }


if "user" not in st.session_state:
    _load_user_from_query()


def main():
    st.title(f"🍱 {today_str} 오늘 점심 같이 드실분?")
    st.markdown("---")

    # --- MVP Entrance (Sidebar) ---
    with st.sidebar:
        st.header("👤 입장")

        if "user" in st.session_state:
            st.success(f"입장됨: {st.session_state['user']['username']} ({st.session_state['user']['employee_id']})")
            if st.button("나가기"):
                st.query_params.clear()
                del st.session_state["user"]
                st.rerun()
        else:
            emp = st.text_input("사번 (예: sl55555)")
            name = st.text_input("이름")
            if st.button("입장하기", use_container_width=True):
                ok, user, err = db.get_or_create_user_simple(employee_id=emp, username=name)
                if not ok:
                    st.error(err or "입장 실패")
                else:
                    user_id, username, telegram_chat_id, *_rest = user
                    st.session_state["user"] = {
                        "user_id": user_id,
                        "username": username,
                        "employee_id": emp.strip().lower(),
                        "telegram_chat_id": telegram_chat_id,
                    }
                    # Persist across refresh via URL param (Safari-safe)
                    st.query_params["emp"] = emp.strip().lower()
                    st.rerun()

    if "user" not in st.session_state:
        st.info("왼쪽에서 사번+이름 입력하고 입장해줘.")
        st.stop()

    user_id = st.session_state["user"]["user_id"]
    current_user = st.session_state["user"]["username"]

    # --- Status Setting (one lunch per day rule) ---
    st.subheader(f"👋 {current_user}님의 오늘 상태")

    my_status = db.get_status_today(user_id)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🟢 점약 없어요 불러주세요", use_container_width=True, disabled=(my_status == "Booked")):
            db.update_status(user_id, "Free")
            st.rerun()

    with c2:
        if st.button("🧑‍🍳 우리쪽에 합류하실분?", use_container_width=True, disabled=(my_status == "Booked")):
            # Block if already member of any group today
            if db.get_groups_for_user_today(user_id):
                st.warning("이미 점심약속이 있는것 같아요!")
            else:
                db.update_status(user_id, "Hosting")
                st.rerun()

    # status line under buttons
    status_text = {
        "Booked": "점약 있어요 🎉",
        "Free": "점약 없어요(불러주세요) 🟢",
        "Hosting": "오늘 점심 같이 드실분? 모집중 🧑‍🍳",
        "Planning": "점약 잡는 중 🟠",
        "Not Set": "아직 미설정",
    }.get(my_status, my_status)
    st.caption(f"오늘 상태: {status_text}")
    if my_status == "Booked":
        st.caption("⚠️ 이미 점심약속이 있는것 같아요! (오늘은 변경/요청이 제한돼요)")

    # Hosting extra inputs
    if db.get_status_today(user_id) == "Hosting":
        st.markdown("### 🧑‍🍳 합류 모집 정보")
        with st.form("hosting_form"):
            member_names = st.text_input("현재 멤버(이름)", value=current_user)
            seats_left = st.number_input("남은 자리", min_value=0, max_value=20, value=1, step=1)
            menu = st.text_input("메뉴", placeholder="예: 김치찌개 / 샐러드 / 파스타")
            submitted = st.form_submit_button("저장")

        if submitted:
            db.upsert_group(user_id, member_names.strip(), int(seats_left), menu.strip())
            st.success("저장 완료!")

    st.markdown("---")

    # --- Requests (Inbox/Outbox/Stats) ---
    def pretty_status(status: str) -> str:
        if status == "pending":
            return "대기중…"
        if status == "accepted":
            return "🍚👏 우리 같이 먹어요"
        if status == "declined":
            return "오늘은 다음에 🙏"
        if status == "cancelled":
            return "취소됨"
        return status

    incoming = db.list_incoming_requests(user_id)
    outgoing = db.list_outgoing_requests(user_id)

    confirmed = [row for row in incoming if row[3] == "accepted"] + [row for row in outgoing if row[3] == "accepted"]
    st.subheader("📊 오늘 점심 성사")
    st.metric("성사 건수", len(confirmed))

    st.subheader("📩 오늘 받은 점심 초대")
    if not incoming:
        st.caption("아직 받은 초대가 없어요.")
    else:
        for req_id, from_uid, from_name, status, ts, group_host_user_id in incoming:
            with st.container(border=True):
                st.write(f"**{from_name}** → 나")
                st.caption(f"상태: {pretty_status(status)} · {ts}")

                if status == "pending":
                    a, b = st.columns(2)
                    with a:
                        if st.button("✅ 수락", key=f"acc_{req_id}", use_container_width=True):
                            db.update_request_status(req_id, "accepted")

                            # If this request targets a group host, add member there.
                            if group_host_user_id:
                                ok_add, err_add = db.add_member_to_group(int(group_host_user_id), from_uid, from_name)
                                if ok_add:
                                    db.set_booked_for_group(int(group_host_user_id))
                                else:
                                    st.warning(err_add or "그룹 합류 처리 실패")
                            else:
                                # 1:1
                                db.update_status(user_id, "Booked")
                                db.update_status(from_uid, "Booked")
                                db.cancel_pending_requests_for_user(user_id)
                                db.cancel_pending_requests_for_user(from_uid)

                            sender = db.get_user_by_id(from_uid)
                            if sender and sender[2]:
                                bot.send_telegram_msg(sender[2], f"✅ [Lunch Buddy] {current_user}님이 점심 초대를 수락했어요.")

                            st.success("🍚👏 우리 같이 먹어요")
                            st.rerun()
                    with b:
                        if st.button("❌ 거절", key=f"dec_{req_id}", use_container_width=True):
                            db.update_request_status(req_id, "declined")
                            st.rerun()

    st.subheader("📤 오늘 내가 보낸 초대")
    if not outgoing:
        st.caption("아직 보낸 초대가 없어요.")
    else:
        for req_id, to_uid, to_name, status, ts, group_host_user_id in outgoing:
            with st.container(border=True):
                st.write(f"나 → **{to_name}**")
                st.caption(f"상태: {pretty_status(status)} · {ts}")
                if status == "pending":
                    if st.button("취소", key=f"cancel_{req_id}"):
                        db.cancel_request(req_id)
                        st.rerun()

    st.markdown("---")

    # --- Dashboard ---
    st.subheader("👀 동료들의 점심 현황")

    all_statuses = db.get_all_statuses()
    others = [s for s in all_statuses if s[0] != user_id]

    # Groups to join
    st.markdown("### 🧑‍🍳 우리쪽에 합류하실분?")
    groups = db.get_groups_today()
    joinable = [g for g in groups if g[4] is None or int(g[4]) > 0]
    if not joinable:
        st.caption("아직 모집 중인 팀이 없어요.")
    else:
        for gid, host_uid, host_name, member_names, seats_left, menu in joinable:
            with st.container(border=True):
                st.write(f"**호스트:** {host_name}")
                st.write(f"**현재 멤버:** {member_names or '-'}")
                st.write(f"**남은 자리:** {seats_left}")
                st.write(f"**메뉴:** {menu or '-'}")

                if host_uid != user_id:
                    if st.button("🙋 저요!저요!", key=f"join_{gid}", use_container_width=True, disabled=(db.get_status_today(user_id) == "Booked")):
                        req_id, err = db.create_request(user_id, host_uid, group_host_user_id=host_uid)
                        if not req_id:
                            st.warning(err or "요청 실패")
                        else:
                            st.success("요청 보냈어요! (수락되면 멤버에 추가돼요)")
                        st.rerun()

    st.markdown("---")

    # Free list
    st.markdown("### 🟢 점약 없어요 불러주세요")
    free_people = [o for o in others if o[2] == "Free"]
    if not free_people:
        st.caption("지금 '불러주세요' 상태인 사람이 없어요.")
    else:
        cols = st.columns(4)
        for i, (uid, uname, _status, _chat) in enumerate(free_people):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}")
                    if st.button("🍚 밥 먹자고 찌르기!", key=f"req_{uid}", use_container_width=True, disabled=(db.get_status_today(user_id) == "Booked")):
                        req_id, err = db.create_request(user_id, uid)
                        if not req_id:
                            st.warning(err or "요청 실패")
                        else:
                            st.success("요청 보냈어요!")
                        st.rerun()

    st.markdown("---")

    st.markdown("### ✅ 성사완료")
    booked_people = [o for o in others if o[2] == "Booked"]
    if not booked_people:
        st.caption("아직 성사완료된 사람이 없어요.")
    else:
        cols = st.columns(4)
        for i, (uid, uname, _status, _chat) in enumerate(booked_people):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}")
                    st.write("상태: 점약 있어요 🎉")


if __name__ == "__main__":
    main()
