import datetime
import streamlit as st

import bot
import db

# --- Init ---
db.init_db()

today = datetime.date.today()
today_str = today.isoformat()
today_kor = f"{today.month}월 {today.day}일"

st.set_page_config(page_title=f"Lunch Buddy 🍱 ({today_str})", layout="wide")


def _auto_login_from_query():
    """MVP convenience: if ?emp=sl12345 exists and user exists, auto-enter.

    NOTE: This bypasses PIN on refresh. OK for MVP/internal use.
    """
    if "user" in st.session_state:
        return

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
        "team": team,
        "mbti": mbti,
        "age": age,
        "years": years,
    }


_auto_login_from_query()


def main():
    st.title(f"Enmover Lunch Buddy 오늘 점심 드실분? ({today_kor})")
    st.caption(f"오늘 날짜: {today_str}")
    st.markdown("---")

    # --- Auth (sidebar) ---
    with st.sidebar:
        st.header("🔐 회원가입 / 로그인")

        if "user" in st.session_state:
            u = st.session_state["user"]
            st.success(f"로그인됨: {u['username']} ({u['employee_id']})")

            st.markdown("---")
            st.subheader("📚 점심 기록")
            dates = db.list_my_group_dates(user_id)
            if dates:
                sel = st.selectbox("날짜 선택", dates, index=0)
                groups = db.get_groups_for_user_on_date(user_id, sel)
                if groups:
                    gid, gdate, host_uid, host_name, member_names, seats_left, menu = groups[0]
                    members = db.list_group_members(host_uid, sel)
                    st.write(f"**{sel} 점심 기록**")
                    st.write(f"멤버: {', '.join([n for _uid, n in members]) if members else (member_names or '-')}")
                    if menu:
                        st.write(f"메뉴: {menu}")
                    st.caption(f"호스트: {host_name}")
                else:
                    st.caption("해당 날짜 기록이 없어요.")
            else:
                st.caption("아직 기록이 없어요.")

            if st.button("로그아웃"):
                st.query_params.clear()
                del st.session_state["user"]
                st.rerun()
        else:
            tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

            with tab_login:
                employee_id = st.text_input("사번 (예: sl55555)")
                pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password")

                if st.button("로그인", use_container_width=True):
                    ok, user = db.verify_login(employee_id, pin)
                    if not ok:
                        st.error("사번 또는 비밀번호가 올바르지 않습니다.")
                    else:
                        user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, *_ = user
                        st.session_state["user"] = {
                            "user_id": user_id,
                            "username": username,
                            "employee_id": emp_id,
                            "telegram_chat_id": telegram_chat_id,
                            "team": team,
                            "mbti": mbti,
                            "age": age,
                            "years": years,
                        }
                        # Safari-safe persistence via URL
                        st.query_params["emp"] = emp_id
                        st.rerun()

            with tab_signup:
                st.caption("사번은 영문 2개 + 숫자 5개 (예: sl55555), 비밀번호는 숫자 4자리")
                su_name = st.text_input("이름")
                su_team = st.text_input("팀명")
                su_mbti = st.text_input("MBTI")
                su_age = st.number_input("나이", min_value=0, max_value=120, value=30, step=1)
                su_years = st.number_input("연차", min_value=0, max_value=60, value=1, step=1)
                su_emp = st.text_input("사번 (예: sl55555)")
                su_pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password")
                su_pin2 = st.text_input("비밀번호 확인", type="password")

                if st.button("회원가입", use_container_width=True):
                    if su_pin != su_pin2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        ok, err = db.register_user(
                            username=su_name.strip(),
                            team=su_team.strip(),
                            mbti=su_mbti.strip().upper(),
                            age=int(su_age),
                            years=int(su_years),
                            employee_id=su_emp.strip().lower(),
                            pin=su_pin.strip(),
                        )
                        if ok:
                            st.success("회원가입 완료! 이제 로그인 해주세요.")
                        else:
                            st.error(err or "회원가입 실패")

    if "user" not in st.session_state:
        st.info("왼쪽에서 로그인해줘.")
        st.stop()

    user_id = st.session_state["user"]["user_id"]
    current_user = st.session_state["user"]["username"]

    # Priority: accepted -> Booked
    db.reconcile_user_today(user_id)

    # --- My status ---
    st.subheader("🙋 내 현황")
    my_status = db.get_status_today(user_id)

    if my_status == "Booked":
        st.markdown("## 점약 있어요 🎉")
        if st.button("🚫 점약 취소하기", type="primary"):
            ok, err = db.cancel_booking_for_user(user_id)
            if ok:
                st.success("취소 완료")
                st.rerun()
            else:
                st.error(err or "취소 실패")
    else:
        status_text = {
            "Free": "점약 없어요(불러주세요) 🟢",
            "Hosting": "오늘 점심 같이 드실분? 모집중 🧑‍🍳",
            "Planning": "점약 잡는 중 🟠",
            "Not Set": "아직 미설정",
        }.get(my_status, my_status)
        st.info(f"현재 내 상태: **{status_text}**")

    # Show who/what if I'm in a group today (even if not Booked yet)
    my_groups_today = db.get_groups_for_user_today(user_id)
    if my_groups_today:
        gid, gdate, host_uid, host_name, member_names, seats_left, menu = my_groups_today[0]
        st.markdown("**오늘 같이 먹는 멤버**")
        members = db.list_group_members(host_uid, today_str)
        st.write(", ".join([name for _uid, name in members]) if members else (member_names or "-"))
        if menu:
            st.markdown(f"**메뉴:** {menu}")
        st.caption(f"호스트: {host_name}")

    # --- Status buttons ---
    st.subheader("👋 오늘 상태는?")
    c1, c2 = st.columns(2)

    if my_status == "Booked":
        st.caption("⚠️ 이미 점심약속이 있는것 같아요! (오늘은 변경/요청이 제한돼요)")

    with c1:
        if st.button(
            "🟢 점약 없어요 불러주세요",
            use_container_width=True,
            disabled=(db.get_status_today(user_id) == "Booked"),
        ):
            db.update_status(user_id, "Free")
            st.rerun()

    with c2:
        if st.button(
            "🧑‍🍳 오늘 점심 같이 드실분?",
            use_container_width=True,
            disabled=(db.get_status_today(user_id) == "Booked"),
        ):
            if db.get_groups_for_user_today(user_id):
                st.warning("이미 점심약속이 있는것 같아요!")
            else:
                db.update_status(user_id, "Hosting")
                st.rerun()

    # Hosting inputs
    if db.get_status_today(user_id) == "Hosting":
        st.markdown("### 🧑‍🍳 합류 모집 정보")
        with st.form("hosting_form"):
            member_names = st.text_input("현재 멤버(이름)", value=current_user)
            seats_left = st.number_input("남은 자리", min_value=0, max_value=20, value=1, step=1)
            menu = st.text_input("메뉴")
            submitted = st.form_submit_button("저장")

        if submitted:
            db.upsert_group(user_id, member_names.strip(), int(seats_left), menu.strip())
            st.success("저장 완료!")

    st.markdown("---")

    # --- Requests ---
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

    confirmed = [r for r in incoming if r[3] == "accepted"] + [r for r in outgoing if r[3] == "accepted"]
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

                            if group_host_user_id:
                                ok_add, err_add = db.add_member_to_group(int(group_host_user_id), from_uid, from_name)
                                if ok_add:
                                    db.set_booked_for_group(int(group_host_user_id))
                                else:
                                    st.warning(err_add or "그룹 합류 처리 실패")
                            else:
                                db.update_status(user_id, "Booked")
                                db.update_status(from_uid, "Booked")

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
        for req_id, to_uid, to_name, status, ts, _group_host_user_id in outgoing:
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

    st.markdown("### 🧑‍🍳 오늘 점심 같이 드실분?")
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
