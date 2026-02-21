import streamlit as st
import datetime
import db
import bot
# Optional deps: keep the app running even if Streamlit Cloud install hiccups.
try:
    from streamlit_cookies_manager import EncryptedCookieManager
except Exception:
    EncryptedCookieManager = None

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    def streamlit_js_eval(*args, **kwargs):
        return None


class _NoopCookies(dict):
    def ready(self):
        return True

    def save(self):
        return None


def get_cookie_manager():
    if EncryptedCookieManager is None:
        return _NoopCookies()

    password = None
    try:
        password = st.secrets.get("COOKIE_PASSWORD")
    except Exception:
        password = None

    if not password:
        password = "lunch-buddy-dev-cookie-password"

    cookies = EncryptedCookieManager(prefix="lunch_buddy_", password=password)
    if not cookies.ready():
        st.stop()
    return cookies

# Initialize DB on first run
db.init_db()

# Cookies (persist login)
cookies = get_cookie_manager()

# Auto-login from cookie/localStorage if session_state empty
if "user" not in st.session_state:
    # 1) Try cookie session token
    token = cookies.get("session_token")
    if token:
        row = db.get_user_by_session_token(token)
        if row:
            user_id, username, telegram_chat_id, team, mbti, age, years, emp_id = row
            st.session_state["user"] = {
                "user_id": user_id,
                "username": username,
                "employee_id": emp_id,
                "team": team,
                "mbti": mbti,
                "age": age,
                "years": years,
                "telegram_chat_id": telegram_chat_id,
            }

    # 2) Try cookie employee_id
    if "user" not in st.session_state:
        emp = cookies.get("employee_id")
        if emp:
            u = db.get_user_by_employee_id(str(emp).strip().lower())
            if u:
                user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, *_ = u
                st.session_state["user"] = {
                    "user_id": user_id,
                    "username": username,
                    "employee_id": emp_id,
                    "team": team,
                    "mbti": mbti,
                    "age": age,
                    "years": years,
                    "telegram_chat_id": telegram_chat_id,
                }

    # 3) Safari-friendly fallback: localStorage
    if "user" not in st.session_state:
        emp_ls = streamlit_js_eval(
            js_expressions="localStorage.getItem('lunch_buddy_employee_id')",
            key="ls_get_emp",
        )
        if emp_ls:
            u = db.get_user_by_employee_id(str(emp_ls).strip().lower())
            if u:
                user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, *_ = u
                st.session_state["user"] = {
                    "user_id": user_id,
                    "username": username,
                    "employee_id": emp_id,
                    "team": team,
                    "mbti": mbti,
                    "age": age,
                    "years": years,
                    "telegram_chat_id": telegram_chat_id,
                }

st.set_page_config(page_title="Lunch Buddy 🍱", layout="wide")

def main():
    st.title("🍱 Lunch Buddy: 오늘 점심 뭐 먹지?")
    st.markdown("---")

    # --- Auth (Sidebar) ---
    with st.sidebar:
        st.header("🔐 로그인")

        if "user" in st.session_state:
            st.success(f"로그인됨: {st.session_state['user']['username']}")
            if st.button("로그아웃"):
                # clear cookie + db session
                token = cookies.get("session_token")
                if token:
                    db.delete_auth_session(token)
                # localStorage token may exist too
                ls_token = streamlit_js_eval(
                    js_expressions="localStorage.getItem('lunch_buddy_session_token')",
                    key="ls_get_token",
                )
                if ls_token:
                    db.delete_auth_session(str(ls_token))
                cookies["session_token"] = ""
                cookies["employee_id"] = ""
                cookies.save()
                streamlit_js_eval(
                    js_expressions="localStorage.removeItem('lunch_buddy_employee_id'); localStorage.removeItem('lunch_buddy_session_token');",
                    key="ls_clear",
                )
                del st.session_state["user"]
                st.rerun()
        else:
            tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

            with tab_login:
                employee_id = st.text_input("사번 (예: sl55555)", key="login_employee_id")
                pin = st.text_input("비밀번호(PIN, 4자리)", type="password", key="login_pin")

                if st.button("로그인", use_container_width=True):
                    ok, user = db.verify_login(employee_id.strip(), pin.strip())
                    if ok:
                        user_id, username, telegram_chat_id, team, mbti, age, years, emp_id, *_ = user
                        st.session_state["user"] = {
                            "user_id": user_id,
                            "username": username,
                            "employee_id": emp_id,
                            "team": team,
                            "mbti": mbti,
                            "age": age,
                            "years": years,
                            "telegram_chat_id": telegram_chat_id,
                        }
                        token = db.create_auth_session(user_id)
                        cookies["session_token"] = token
                        cookies["employee_id"] = emp_id
                        cookies.save()
                        # Also store in localStorage (Safari-friendly)
                        streamlit_js_eval(
                            js_expressions=f"localStorage.setItem('lunch_buddy_employee_id','{emp_id}'); localStorage.setItem('lunch_buddy_session_token','{token}');",
                            key="ls_set_login",
                        )
                        st.rerun()
                    else:
                        st.error("사번 또는 비밀번호가 올바르지 않습니다.")

            with tab_signup:
                st.caption("비밀번호는 숫자 4자리(PIN)로 설정합니다.")
                su_name = st.text_input("이름", key="su_name")
                su_team = st.text_input("팀명", key="su_team")
                su_mbti = st.text_input("MBTI", key="su_mbti")
                su_age = st.number_input("나이", min_value=0, max_value=120, value=30, step=1, key="su_age")
                su_years = st.number_input("연차", min_value=0, max_value=60, value=1, step=1, key="su_years")
                su_emp = st.text_input("사번 (영문2 + 숫자5, 예: sl55555)", key="su_emp")
                su_pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password", key="su_pin")
                su_pin2 = st.text_input("비밀번호 확인", type="password", key="su_pin2")

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

    # check session
    if "user" not in st.session_state:
        st.warning("👈 왼쪽 사이드바에서 로그인/회원가입을 먼저 해주세요!")
        st.stop()

    current_user = st.session_state["user"]["username"]
    user_id = st.session_state["user"]["user_id"]

    # --- Status Setting ---
    st.subheader(f"👋 {current_user}님의 오늘 상태는?")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🟢 점약 없어요 불러주세요", use_container_width=True):
            db.update_status(user_id, "Free")
            st.toast("상태 변경 완료: 점약 없음 🟢")
            st.rerun()

    with col2:
        if st.button("🧑‍🍳 우리쪽에 합류하실분?", use_container_width=True):
            db.update_status(user_id, "Hosting")
            st.toast("상태 변경 완료: 합류 모집 중 🧑‍🍳")
            st.rerun()

    # If hosting, show extra inputs
    my_status_row = [s for s in db.get_all_statuses() if s[0] == user_id]
    my_status = my_status_row[0][2] if my_status_row else "Not Set"

    if my_status == "Hosting":
        st.markdown("### 🧑‍🍳 합류 모집 정보")
        with st.form("hosting_form"):
            member_names = st.text_input("현재 멤버(이름)", value=current_user)
            seats_left = st.number_input("남은 자리", min_value=0, max_value=20, value=1, step=1)
            menu = st.text_input("메뉴", placeholder="예: 김치찌개 / 샐러드 / 파스타")
            submitted = st.form_submit_button("저장")

        if submitted:
            db.upsert_group(user_id, member_names.strip(), int(seats_left), menu.strip())
            st.success("저장 완료! 이제 다른 사람이 '우리쪽에 합류하실분?'에서 확인할 수 있어요.")

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

                            # If I'm hosting today, accepting means the requester joins my group
                            ok_add, _err_add = db.add_member_to_group(user_id, from_name)
                            if ok_add:
                                st.toast("현재 멤버에 추가했어요! (남은 자리 -1)")

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
            st.info("현재 내 상태: **점약 없어요(불러주세요)** 🟢")
        elif my_status == "Hosting":
            st.info("현재 내 상태: **우리쪽 합류 모집 중** 🧑‍🍳")
        elif my_status == "Planning":
            st.info("현재 내 상태: **점약 잡는 중** 🟠")
        elif my_status == "Not Set":
            st.warning("현재 내 상태: **아직 미설정**")
        else:
            st.info(f"현재 내 상태: **{my_status}**")

    # Section A: Groups to join
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

                # Join request button
                if host_uid != user_id:
                    existing_req = db.get_pending_request_between(user_id, host_uid)
                    disabled = bool(existing_req and existing_req[1] == "pending")

                    if st.button(
                        "🙋 저요!저요!",
                        key=f"join_{gid}",
                        disabled=disabled,
                        use_container_width=True,
                    ):
                        req_id = db.create_request(user_id, host_uid)
                        if not req_id:
                            st.warning("이미 오늘 같은 요청을 보냈어요.")
                        else:
                            # Optional telegram notify host
                            host = db.get_user_by_id(host_uid)
                            host_chat = host[2] if host else None
                            bot.send_telegram_msg(host_chat, f"🙋 [Lunch Buddy] {current_user}님이 '{host_name}' 팀에 합류 요청했어요! (앱에서 확인)")
                            st.success("요청 보냈어요! (수락되면 멤버에 추가돼요)")
                        st.rerun()

                    if disabled:
                        st.caption("이미 요청을 보냈어요(대기중).")
                else:
                    st.caption("(내가 만든 모집글)")

    st.markdown("---")

    # Section B: Free people
    st.markdown("### 🟢 점약 없어요 불러주세요")
    free_people = [o for o in others if o[2] == "Free"]

    if not free_people and not joinable:
        st.write("아직 등록된 다른 동료가 없어요.")
    elif not free_people:
        st.caption("지금 '불러주세요' 상태인 사람이 없어요.")
    else:
        cols = st.columns(4)
        for i, (uid, uname, status, t_chat_id) in enumerate(free_people):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}")
                    st.write("상태: 🟢 점약 없음 (불러주세요)")

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
                                st.info("요청은 저장했고, 양쪽 상태는 '점약 잡는 중'으로 바뀌었어요. (텔레그램은 미연결)")
                            st.rerun()

                    if disabled:
                        st.caption("이미 오늘 초대를 보냈어요(대기중).")

if __name__ == "__main__":
    main()
