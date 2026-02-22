import datetime
import streamlit as st

# Optional dependency
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    def st_autorefresh(*args, **kwargs):
        return None

import lunch_bot as bot
import db

# --- Init ---
db.init_db()

# Use KST date to avoid UTC drift on Streamlit Cloud
today_str = db.kst_today_iso()
today = datetime.date.fromisoformat(today_str)
today_kor = f"{today.month}월 {today.day}일"

APP_VERSION = "2026-02-21.13"

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
    # hidden reset switch for testing
    reset_v = st.query_params.get("reset")
    if isinstance(reset_v, list):
        reset_v = reset_v[0] if reset_v else None
    if reset_v == "today":
        db.reset_today_data()
        st.query_params.clear()
        st.success("오늘 점약 데이터 초기화 완료")
        st.stop()

    if reset_v == "all":
        db.reset_all_data()
        st.query_params.clear()
        st.success("전체 DB 초기화 완료 (가입/히스토리 모두 삭제)")
        st.stop()

    # --- Meal state initialization ---
    # Base meal (lunch/dinner) decided by time or toggle
    if "meal" not in st.session_state:
        # Default to dinner after 2 PM (14:00) KST
        now_kst = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
        if now_kst.hour >= 14:
            st.session_state["meal"] = "dinner"
        else:
            st.session_state["meal"] = "lunch"

    # We use the toggle values directly if they exist in session_state to avoid lag.
    base_meal = "dinner" if st.session_state.get("meal_toggle") else "lunch"
    is_private = st.session_state.get("privacy_toggle", False)
    
    final_meal = f"{base_meal}_p" if is_private else base_meal
    st.session_state["meal"] = final_meal

    meal = st.session_state["meal"]
    is_p_mode = meal.endswith("_p")
    base_label = "점심" if "lunch" in meal else "저녁"
    meal_label = f"{base_label}({'🔒' if is_p_mode else '🔓'})"

    st.title("[Enmover Meal Finder, EMF]")
    st.markdown(f"### 오늘 {meal_label} 드실분 ? ({today_kor})")
    st.caption(f"오늘 날짜: {today_str}")

    # Dinner mode: force dark-ish UI via CSS (Streamlit theme can't be switched per-run)
    if st.session_state["meal"] == "dinner":
        st.markdown(
            """
            <style>
            /* ---- Dinner Dark Mode (CSS override) ---- */
            :root{color-scheme:dark;}

            /* app + sidebar backgrounds */
            [data-testid="stAppViewContainer"]{background:#0e1117 !important;}
            [data-testid="stSidebar"]{background:#0b1220 !important;}

            /* global text */
            html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
            [data-testid="stMarkdownContainer"], [data-testid="stText"],
            p, li, span, label, small, div{
              color:#e5e7eb !important;
            }

            /* headings */
            h1,h2,h3,h4,h5,h6{color:#f9fafb !important;}

            /* captions/help */
            [data-testid="stCaptionContainer"], .stCaption{color:rgba(229,231,235,0.75) !important;}

            /* links */
            a{color:#93c5fd !important;}

            /* containers/borders */
            div[data-testid="stVerticalBlockBorderWrapper"]{border-color:rgba(255,255,255,0.14) !important;}

            /* inputs */
            input, textarea{color:#e5e7eb !important; caret-color:#e5e7eb !important;}
            [data-baseweb="input"] input{background:rgba(255,255,255,0.06) !important;}
            [data-baseweb="textarea"] textarea{background:rgba(255,255,255,0.06) !important;}
            [data-baseweb="select"] div{background:rgba(255,255,255,0.06) !important;}

            /* buttons */
            button[kind="primary"], button[kind="secondary"], .stButton button{
              color:#000000 !important; /* requested: black text */
              background:#e5e7eb !important;
              border-color:rgba(255,255,255,0.25) !important;
            }
            /* Streamlit buttons often contain nested spans that were being forced to white by global rules */
            button[kind="primary"] *, button[kind="secondary"] *, .stButton button *{
              color:#000000 !important;
              fill:#000000 !important;
            }
            .stButton button:hover{filter:brightness(0.92);}

            /* alerts (st.info/st.success/st.warning/st.error)
               일부 테마에서 alert 내부 텍스트가 어둡게 고정되는 케이스가 있어 selector를 강하게 잡음 */
            [data-testid="stAlert"], .stAlert, div[role="alert"]{
              background:#111827 !important; /* slate-900 */
              border:1px solid rgba(255,255,255,0.16) !important;
            }
            [data-testid="stAlert"] [data-testid="stMarkdownContainer"] *,
            [data-testid="stAlert"] p, [data-testid="stAlert"] span, [data-testid="stAlert"] div,
            .stAlert [data-testid="stMarkdownContainer"] *{
              color:#f9fafb !important;
            }
            /* info box icon */
            [data-testid="stAlert"] svg{color:#93c5fd !important; fill:#93c5fd !important;}

            /* expander/header blocks sometimes use light bg */
            [data-testid="stExpander"] details{background:rgba(255,255,255,0.04) !important;}

            /* metric widget text */
            [data-testid="stMetricValue"], [data-testid="stMetricDelta"]{color:#f9fafb !important;}
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Lunch mode: force Light UI (even if OS is in dark mode)
        st.markdown(
            """
            <style>
            /* ---- Lunch Light Mode (CSS override) ---- */
            :root{color-scheme:light;}
            html, body{background:#ffffff !important;}

            /* Backgrounds */
            [data-testid="stAppViewContainer"]{background:#ffffff !important;}
            [data-testid="stSidebar"]{background:#f0f2f6 !important;}

            /* Global text */
            [data-testid="stAppViewContainer"] *, [data-testid="stSidebar"] *{
                color:#111827 !important; /* slate-900 */
            }
            h1,h2,h3,h4,h5,h6{color:#0f172a !important;}

            /* Inputs */
            [data-baseweb="input"] input,
            [data-baseweb="textarea"] textarea,
            [data-baseweb="select"] div{
                background:#ffffff !important;
                color:#111827 !important;
                border-color:rgba(17,24,39,0.18) !important;
            }

            /* Header/top bar */
            [data-testid="stHeader"], [data-testid="stToolbar"], header{
                background:#ffffff !important;
                color:#111827 !important;
            }
            [data-testid="stHeader"] *, [data-testid="stToolbar"] *{color:#111827 !important;}

            /* Tabs */
            [data-testid="stTabs"] button, [data-testid="stTabs"] *{color:#111827 !important;}

            /* Buttons: keep clear contrast */
            .stButton button, button[kind="primary"], button[kind="secondary"]{
                background:#ffffff !important;
                color:#111827 !important;
                border:1px solid rgba(17,24,39,0.25) !important;
            }
            .stButton button *{color:#111827 !important; fill:#111827 !important;}

            /* Alerts */
            [data-testid="stAlert"]{
              background:#f0f2f6 !important;
              border:1px solid rgba(17,24,39,0.12) !important;
            }
            [data-testid="stAlert"] *{color:#111827 !important;}

            /* Containers/borders */
            div[data-testid="stVerticalBlockBorderWrapper"]{border-color:rgba(17,24,39,0.12) !important;}

            /* Toggle: Streamlit toggles can be hard to see in forced light mode */
            [data-testid="stWidgetLabel"] p { color: #111827 !important; font-weight: 500 !important; }
            
            /* The track (background) of the toggle */
            div[data-testid="stCheckbox"] div[role="switch"] {
                background-color: #1e293b !important; /* VERY dark slate-800 for contrast */
                border: 2px solid #0f172a !important;
            }
            /* The handle (circle) of the toggle when OFF */
            div[data-testid="stCheckbox"] div[role="switch"] > div {
                background-color: #ffffff !important; /* White handle so it pops against dark track */
            }
            /* When checked (ON) */
            div[data-testid="stCheckbox"] div[role="switch"][aria-checked="true"] {
                background-color: #2563eb !important; /* blue track */
            }
            div[data-testid="stCheckbox"] div[role="switch"][aria-checked="true"] > div {
                background-color: #ffffff !important; /* white handle when on */
            }

            /* Metric text */
            [data-testid="stMetricValue"], [data-testid="stMetricDelta"]{color:#111827 !important;}

            /* Expander */
            [data-testid="stExpander"] details{background:#ffffff !important;}
            </style>
            """,
            unsafe_allow_html=True,
        )

    # tighter separator (default --- is too tall)
    st.markdown("<hr style='margin:0.35rem 0 0.6rem 0; border:0; border-top:1px solid rgba(128,128,128,0.35);'>", unsafe_allow_html=True)

    meal = st.session_state["meal"]

    # --- Auth (sidebar) ---
    with st.sidebar:
        st.caption(f"ver {APP_VERSION}")
        st.header("🔐 회원가입 / 로그인")

        # Meal toggle: label reflects current mode
        toggle_label = "🌙 저녁 모드" if st.session_state.get("meal_toggle") else "☀️ 점심 모드"
        st.toggle(toggle_label, value=("dinner" in st.session_state["meal"]), key="meal_toggle")

        # --- Privacy mode toggle ---
        st.toggle("🔒 프라이빗 모드", value=st.session_state["meal"].endswith("_p"), key="privacy_toggle")
        st.caption("(프라이빗: 밥친구에게만 내 상태 공개/친구 상태 확인)")

        # --- Hosting cancel confirmation dialog ---
        @st.dialog("모집 취소 확인")
        def confirm_hosting_cancel(target_status, target_kind=None):
            st.write(f"현재 모집 중인 {('점심' if meal=='lunch' else '저녁')} 그룹이 있습니다.")
            st.write("새로운 상태로 변경하면 현재 모집글이 삭제됩니다. 정말 취소하시겠습니까?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("예, 취소합니다", use_container_width=True):
                    db.clear_status_today(user_id, meal=meal) # deletes group
                    if target_status == "Free":
                        db.update_status(user_id, "Free", meal=meal, kind=target_kind)
                    elif target_status == "Skip":
                        db.update_status(user_id, "Skip", meal=meal)
                    st.rerun()
            with c2:
                if st.button("아니오", use_container_width=True):
                    st.rerun()

        if "user" in st.session_state:
            u = st.session_state["user"]
            name = db.format_name(u.get('username',''), u.get('english_name',''))
            st.success(f"로그인됨: {name} ({u['employee_id']})")

            st.markdown("---")

            # --- Telegram notification onboarding (TEMPORARILY HIDDEN) ---
            if False: # Hidden per user request
                st.subheader("🔔 텔레그램 알림")
                urow = db.get_user_by_id(int(u["user_id"]))
                _tg_chat_id = None
                if urow:
                    _tg_chat_id = urow[3]

                if _tg_chat_id:
                    st.success("✅ 알림 연동됨")
                else:
                    st.warning("❌ 알림 미연동 (초대를 놓칠 수 있어요)")
                    
                    bot_username = bot.get_bot_username()
                    emp_id = u.get("employee_id")
                    
                    if bot_username and emp_id:
                        st.link_button(
                            "텔레그램 연동하기(봇 열기)",
                            f"https://t.me/{bot_username}?start={emp_id}",
                            use_container_width=True,
                        )
                        st.caption("버튼 클릭 → 텔레그램에서 '시작(Start)'만 누르면 됩니다")

                        if st.button("연동 확인", use_container_width=True):
                            ok2, err2, chat_id = bot.try_register_chat_id_for_employee(emp_id)
                            if not ok2:
                                st.error(err2 or "연동 확인 실패")
                            else:
                                ok3, err3 = db.update_user_chat_id_by_employee_id(emp_id, chat_id)
                                if ok3:
                                    st.success("연동 완료! 이제 초대/수락 알림이 텔레그램으로 와요.")
                                    st.rerun()
                                else:
                                    st.error(err3 or "DB 저장 실패")
                    else:
                        if not bot_username:
                            st.error("⚠️ 텔레그램 봇 아이디(USERNAME)가 설정되지 않았습니다. (Streamlit Secrets 확인 필요)")
                        if not emp_id:
                            st.error("⚠️ 사용자 사번 정보가 없습니다.")

                st.markdown("---")
            st.subheader("👤 내 프로필")
            with st.expander("프로필 수정 (사번 제외)", expanded=False):
                urow = db.get_user_by_id(int(u["user_id"]))
                if urow:
                    _uid, uname, ename, _chat, team, role, _mbti, _age, years, emp, _salt, _ph = urow
                    with st.form("profile_edit_form"):
                        new_team = st.text_input("팀명", value=team or "", key="pf_team")
                        new_years = st.number_input("연차", min_value=0, max_value=60, value=int(years or 0), step=1, key="pf_years")
                        new_name = st.text_input("한글이름", value=uname or "", key="pf_name")
                        new_en = st.text_input("영어이름", value=ename or "", key="pf_en")
                        st.caption(f"사번(변경불가): {emp}")
                        st.caption(f"직급: {role}")
                        submitted_pf = st.form_submit_button("저장")

                    if submitted_pf:
                        ok, err = db.update_user_profile(
                            user_id=int(u["user_id"]),
                            username=new_name,
                            english_name=new_en,
                            team=new_team,
                            years=int(new_years),
                        )
                        if ok:
                            # refresh session cache
                            st.session_state["user"]["username"] = new_name
                            st.session_state["user"]["english_name"] = new_en
                            st.session_state["user"]["team"] = new_team
                            st.session_state["user"]["years"] = int(new_years)
                            st.success("프로필 저장 완료")
                            st.rerun()
                        else:
                            st.error(err or "저장 실패")
                else:
                    st.error("프로필 정보를 불러오지 못했어요.")

            st.markdown("---")
            st.subheader(f"📚 {('점심' if meal=='lunch' else '저녁')} 기록")
            sidebar_user_id = u["user_id"]
            dates = db.list_my_group_dates(sidebar_user_id, meal=meal)
            if dates:
                sel = st.selectbox("날짜 선택", dates, index=0)
                groups = db.get_groups_for_user_on_date(sidebar_user_id, sel, meal=meal)
                if groups:
                    gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name, _g_kind = groups[0]
                    members = db.list_group_members(host_uid, sel, meal=meal)
                    st.write(f"**{sel} {('점심' if meal=='lunch' else '저녁')} 기록**")
                    st.write(f"멤버: {', '.join([db.format_name(n, en) for _uid, n, en in members]) if members else (member_names or '-')}")
                    st.write(f"메뉴: {menu or '-'}")
                    if payer_name:
                        st.write(f"내가쏜다: {payer_name} 💳")
                    st.caption(f"호스트: {db.get_display_name(host_uid)}")
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
                employee_id = st.text_input("사번 (예: sl55555)", key="login_emp")
                pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password", key="login_pin")

                if st.button("로그인", use_container_width=True):
                    ok, user = db.verify_login(employee_id, pin)
                    if not ok:
                        st.error("사번 또는 비밀번호가 올바르지 않습니다.")
                    else:
                        user_id, username, english_name, telegram_chat_id, team, role, mbti, age, years, emp_id, *_ = user
                        st.session_state["user"] = {
                            "user_id": user_id,
                            "username": username,
                            "english_name": english_name,
                            "employee_id": emp_id,
                            "telegram_chat_id": telegram_chat_id,
                            "team": team,
                            "role": role,
                            "mbti": mbti,
                            "age": age,
                            "years": years,
                        }
                        # Safari-safe persistence via URL
                        st.query_params["emp"] = emp_id
                        st.rerun()

            with tab_signup:
                st.caption("사번은 영문 2개 + 숫자 5개 (예: sl55555), 비밀번호는 숫자 4자리")
                su_name = st.text_input("이름", key="su_name")
                su_english = st.text_input("영어이름", key="su_english")
                su_team = st.text_input("팀명", key="su_team")
                su_role = st.selectbox("직급", ["팀원", "팀장", "임원"], index=0, key="su_role")
                # MBTI/나이는 입력받지 않음 (단순화)
                su_years = st.number_input("연차", min_value=0, max_value=60, value=1, step=1, key="su_years")
                su_emp = st.text_input("사번 (예: sl55555)", key="su_emp")
                su_pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password", key="su_pin")
                su_pin2 = st.text_input("비밀번호 확인", type="password", key="su_pin2")

                if st.button("회원가입", use_container_width=True):
                    if su_pin != su_pin2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        ok, err = db.register_user(
                            username=su_name.strip(),
                            english_name=su_english.strip(),
                            team=su_team.strip(),
                            role=su_role,
                            mbti="",
                            age=0,
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

    # global auto refresh (invites + colleagues)
    # Pause refresh while a confirmation dialog is open (otherwise it disappears)
    if not st.session_state.get("pause_refresh", False):
        st_autorefresh(interval=3000, key="global_refresh")

    user_id = st.session_state["user"]["user_id"]
    current_user = st.session_state["user"]["username"]

    # Priority: accepted -> Booked
    db.reconcile_user_today(user_id, meal=meal)

    # Time-out logic: if meal is expired, Free/Hosting statuses are hidden from board.
    expired = db.is_meal_expired(meal)

    # Defensive cleanup: if status says Hosting but group row is missing, show (미정)
    if db.get_status_today(user_id, meal=meal) == "Hosting" and not db.get_group_by_host_today(user_id, meal=meal):
        db.clear_status_today(user_id, meal=meal)

    # Prepare friend list for private filtering
    my_friends_ids = None
    if is_p_mode:
        my_friends_ids = db.list_friends(user_id)
        # Always include myself in the filter so I can see my own status/group
        my_friends_ids.append(user_id)

    tab_my, tab_board = st.tabs([
        f"🍱 오늘 나의 {base_label} 현황",
        f"📌 {base_label}찾기 게시판",
    ])
    
    if is_p_mode:
        with st.sidebar:
            st.markdown("---")
            st.subheader("👫 밥친구 관리")
            
            f_tab1, f_tab2 = st.tabs(["내 친구", "요청"])
            with f_tab1:
                fids = db.list_friends(user_id)
                if not fids:
                    st.caption("아직 밥친구가 없어요.")
                else:
                    for fid in fids:
                        f_row = db.get_user_by_id(fid)
                        if f_row:
                            col_a, col_b = st.columns([3, 1])
                            col_a.write(db.get_display_name(fid))
                            if col_b.button("삭제", key=f"del_f_{fid}"):
                                db.remove_friend(user_id, fid)
                                st.rerun()

                st.markdown("**🔍 친구 찾기**")
                f_query = st.text_input("이름/팀명 검색", key="f_search_input")
                if f_query:
                    results = db.search_users(f_query, user_id)
                    for rid, rname, reng, rteam in results:
                        col_a, col_b = st.columns([3, 1])
                        col_a.write(f"{rname} ({rteam})")
                        if col_b.button("신청", key=f"req_f_{rid}"):
                            ok, err = db.send_friend_request(user_id, rid)
                            if ok: st.success("요청 보냄")
                            else: st.error(err)

            with f_tab2:
                pending = db.list_pending_requests(user_id)
                if not pending:
                    st.caption("받은 요청이 없어요.")
                else:
                    for p in pending:
                        st.write(f"**{p['username']}** ({p['team']})")
                        ca, cb = st.columns(2)
                        if ca.button("수락", key=f"acc_f_{p['user_id']}", use_container_width=True):
                            db.accept_friend_request(user_id, p['user_id'])
                            st.rerun()
                        if cb.button("거절", key=f"rej_f_{p['user_id']}", use_container_width=True):
                            db.remove_friend(user_id, p['user_id'])
                            st.rerun()

    with tab_my:
            # --- My status ---
            st.subheader("🙋 내 현황")
            my_status, my_kind = db.get_status_row_today(user_id, meal=meal)

            if my_status == "Booked":
                st.markdown("## 점약 있어요 🎉")

                # Confirm dialog (prevents accidental cancel)
                if st.button("🚫 점약 취소하기", type="primary"):
                    st.session_state["confirm_cancel_open"] = True
                    st.session_state["confirm_cancel_shown_once"] = False
                    st.session_state["pause_refresh"] = True

                # NOTE: st.dialog has an (X) close button; Streamlit doesn't give us an onClose.
                # Workaround: if the dialog was already shown once and we rerun again without a choice,
                # treat it as closed.
                if st.session_state.get("confirm_cancel_open", False):
                    if st.session_state.get("confirm_cancel_shown_once", False):
                        st.session_state["confirm_cancel_open"] = False
                        st.session_state["pause_refresh"] = False
                    else:
                        @st.dialog("정말 취소하시겠어요? (눈물)")
                        def _confirm_cancel_dialog():
                            # Determine if I'm the host of a multi-person group
                            groups_now = db.get_groups_for_user_today(user_id, meal=meal)
                            host_uid = None
                            member_candidates = []
                            if groups_now:
                                _gid, _d, host_uid, _hn, _mn, _sl, _m, _p, _k = groups_now[0]
                                members = db.list_group_members(int(host_uid), today_str, meal=meal)
                                # candidates exclude me
                                member_candidates = [(uid, db.format_name(n, en)) for uid, n, en in members if int(uid) != int(user_id)]

                            is_host_multi = bool(host_uid) and (int(host_uid) == int(user_id)) and (len(member_candidates) >= 2)

                            if is_host_multi:
                                st.write("호스트라서, 취소 방식 선택이 필요해요.")
                                mode = st.radio(
                                    "선택",
                                    ["전체 취소(모임 해산)", "방장 위임 후 나는 빠지기"],
                                    index=0,
                                    key="cancel_mode_radio",
                                )
                                new_host_id = None
                                if mode == "방장 위임 후 나는 빠지기":
                                    new_host_id = st.selectbox(
                                        "새 방장 선택",
                                        options=member_candidates,
                                        format_func=lambda x: x[1],
                                        key="new_host_select",
                                    )
                            else:
                                st.write("지금 잡힌 약속/그룹이 취소돼요. 괜찮아요?")
                                mode = "전체 취소(모임 해산)"
                                new_host_id = None

                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("예", type="primary", use_container_width=True, key="do_cancel_btn"):
                                    ok = True
                                    err = None

                                    if is_host_multi and mode == "방장 위임 후 나는 빠지기":
                                        try:
                                            # delegate host
                                            chosen_uid = int(new_host_id[0]) if new_host_id else None
                                            if not chosen_uid:
                                                ok, err = False, "새 방장을 선택해줘."
                                            else:
                                                ok, err = db.delegate_host(today_str, meal, int(user_id), int(chosen_uid))
                                                if ok:
                                                    # remove myself from the delegated group
                                                    db.remove_member_from_group(int(chosen_uid), int(user_id), today_str, meal=meal)
                                                    db.cancel_accepted_for_users([int(user_id)], meal=meal)
                                                    db.clear_status_today(int(user_id), meal=meal)
                                        except Exception as e:
                                            ok, err = False, str(e)
                                    else:
                                        ok, err = db.cancel_booking_for_user(user_id, meal=meal)

                                    st.session_state["confirm_cancel_open"] = False
                                    st.session_state["pause_refresh"] = False

                                    if ok:
                                        st.success("취소 완료")
                                        st.session_state.pop("hosting_open", None)
                                        st.rerun()
                                    else:
                                        st.error(err or "취소 실패")

                            with c2:
                                if st.button("아니오", use_container_width=True, key="cancel_dialog_no_btn"):
                                    st.session_state["confirm_cancel_open"] = False
                                    st.session_state["pause_refresh"] = False
                                    st.rerun()

                        _confirm_cancel_dialog()
                        st.session_state["confirm_cancel_shown_once"] = True
            else:
                status_text = {
                    "Free": (f"{('점심' if meal=='lunch' else '저녁')} 약속 없어요(불러주세요) 🙇‍♂️" if meal=="lunch" else f"저녁 {('술' if my_kind=='drink' else '밥')} 가능해요!"),
                    "Hosting": f"오늘 {('점심' if meal=='lunch' else '저녁')} 같이 하실분? 모집중 🧑‍🍳",
                    "Planning": f"{('점심' if meal=='lunch' else '저녁')} 약속 잡는 중 🟠",
                    "Skip": "오늘은 넘어갈게요 (미참여) 🙅",
                    "Not Set": "(미정)",
                }.get(my_status, my_status)
                st.info(f"현재 내 상태: **{status_text}**")

            # Show who/what (always when Booked)
            show_detail = True

            if show_detail:
                my_groups_today = db.get_groups_for_user_today(user_id, meal=meal)

                # If status is Booked but membership rows are missing (legacy), recover from accepted group request
                if (not my_groups_today) and my_status == "Booked":
                    host_id = db.get_latest_accepted_group_host_today(user_id, meal=meal)
                    if host_id:
                        try:
                            db.ensure_member_in_group(int(host_id), int(user_id), today_str, meal=meal)
                        except Exception:
                            pass
                        my_groups_today = db.get_groups_for_user_today(user_id, meal=meal)

                if my_groups_today:
                    gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name, g_kind = my_groups_today[0]
                    st.markdown("**오늘 점약 상세**" if my_status == "Booked" else "**오늘 같이 먹는 멤버**")
                    if (meal == "dinner") and g_kind:
                        st.caption("타입: " + ("🍻 술" if g_kind == "drink" else "🍚 밥"))
                    members = db.list_group_members(host_uid, today_str, meal=meal)
                    st.write(", ".join([db.format_name(name, en) for _uid, name, en in members]) if members else (member_names or "-"))
                    # Menu editable box
                    with st.expander("🍽️ 메뉴/쏘는사람 수정", expanded=False):
                        new_menu = st.text_input("메뉴", value=(menu or ""), key=f"menu_edit_{host_uid}")
                        new_payer = st.text_input("(선택) 내가쏜다!", value=(payer_name or ""), key=f"payer_edit_{host_uid}")
                        new_payer = (new_payer or "").strip()
                        if st.button("저장", key=f"save_menu_{host_uid}"):
                            db.update_group_menu_payer(host_uid, today_str, new_menu.strip(), new_payer or None)
                            st.success("저장 완료")
                            st.rerun()

                    st.markdown(f"**메뉴:** {menu or '-'}")
                    if payer_name:
                        st.markdown(f"**내가쏜다:** {payer_name} 💳")
                    st.caption(f"호스트: {db.get_display_name(host_uid)}")

                    # --- Members-only chat ---
                    with st.expander("💬 멤버 채팅 (메뉴/시간 정하기)", expanded=True):
                        realtime = st.toggle("실시간 업데이트(3초)", value=True, key=f"rt_{host_uid}")
                        # If user is typing, don't autorefresh (it disrupts input)
                        typing_key = f"chat_msg_{host_uid}_{meal}"
                        is_typing = bool(st.session_state.get(typing_key, ""))
                        if realtime and (not is_typing):
                            st_autorefresh(interval=3000, key=f"chat_refresh_{host_uid}_{meal}")

                        # Defensive: ensure I'm registered as a member of this group (fixes "그룹 멤버만" send failures)
                        try:
                            db.ensure_member_in_group(int(host_uid), int(user_id), today_str, meal=meal)
                        except Exception:
                            pass

                        chat_rows = db.list_group_chat(host_uid, today_str, meal=meal, limit=200)
                        if not chat_rows:
                            st.caption("아직 대화가 없어요.")
                        else:
                            # Scroll to bottom on each rerun (JS inside iframe)
                            import html as _html
                            items = []
                            for _uid, uname, msg, ts in chat_rows[-80:]:
                                items.append(
                                    f"<div class='lb-chat-item'>"
                                    f"<div class='lb-chat-meta'><b>{_html.escape(str(uname))}</b> · {_html.escape(str(ts))}</div>"
                                    f"<div class='lb-chat-msg'>{_html.escape(str(msg))}</div>"
                                    f"</div>"
                                )

                            chat_html = f"""
        <div id='lb-chat-box' style='height:280px; overflow-y:auto; border:1px solid rgba(128,128,128,0.25); border-radius:8px;'>
          {''.join(items)}
        </div>
        <style>
        .lb-chat-item{{
            padding:6px 8px;
            border-bottom:1px solid rgba(128,128,128,0.15);
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;
            color: {('#e5e7eb' if meal=='dinner' else '#111827')} !important;
        }}
        .lb-chat-meta{{
            font-size:12px;
            opacity:0.65;
            line-height:1.15;
            margin-bottom:2px;
            color: {('#e5e7eb' if meal=='dinner' else '#111827')} !important;
        }}
        .lb-chat-msg{{
            font-size:14px;
            line-height:1.25;
            margin:0;
            color: {('#f9fafb' if meal=='dinner' else '#111827')} !important;
        }}
        </style>
        <script>
          const el = document.getElementById('lb-chat-box');
          if (el) {{ el.scrollTop = el.scrollHeight; }}
        </script>
        """
                            st.components.v1.html(chat_html, height=300)

                        # Layout chat input and send button in one row
                        msg_key = f"chat_msg_{host_uid}_{meal}"

                        def on_chat_submit():
                            val = st.session_state.get(msg_key, "").strip()
                            if val:
                                ok, err = db.add_group_chat(host_uid, user_id, db.get_display_name(user_id), val, today_str, meal=meal)
                                if ok:
                                    st.session_state[msg_key] = ""
                                else:
                                    st.error(err or "전송 실패")

                        chat_col1, chat_col2 = st.columns([5, 1])
                        with chat_col1:
                            st.text_input("메시지", key=msg_key, placeholder="메시지 입력…", on_change=on_chat_submit, label_visibility="collapsed")
                        with chat_col2:
                            st.button("전송", key=f"send_{host_uid}_{meal}", on_click=on_chat_submit, use_container_width=True)
                else:
                    # 1:1 booked detail (no group) → auto-create a 1:1 group so details can be stored/shown
                    if my_status == "Booked":
                        d = db.get_latest_accepted_1to1_detail_today(user_id, meal=meal)
                        if d:
                            _req_id, other_id, other_name, ts = d
                            db.ensure_1to1_group_today(user_id, int(other_id), meal=meal, kind=my_kind)

                            # re-fetch as group
                            my_groups_today = db.get_groups_for_user_today(user_id, meal=meal)
                            if my_groups_today:
                                gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name, g_kind = my_groups_today[0]
                                st.markdown("**오늘 점약 상세**")
                                if (meal == "dinner") and g_kind:
                                    st.caption("타입: " + ("🍻 술" if g_kind == "drink" else "🍚 밥"))
                                members = db.list_group_members(host_uid, today_str, meal=meal)
                                st.write("함께: " + (", ".join([db.format_name(name, en) for _uid, name, en in members]) if members else (member_names or "-")))
                                st.markdown(f"**메뉴:** {menu or '-'}")
                                if payer_name:
                                    st.markdown(f"**내가쏜다:** {payer_name} 💳")
                                st.caption(f"시간: {ts}")
                            else:
                                st.markdown("**오늘 점약(1:1) 상세**")
                                st.write(f"함께: {current_user} + {other_name}")
                                st.write("메뉴: -")
                                st.caption(f"시간: {ts}")
                        else:
                            st.caption("(아직 매칭된 점약 정보를 찾지 못했어요. 새로고침 후 다시 시도해줘)")

            # --- Status buttons ---

            st.subheader("👋 오늘 상태는?")
            c1, c2, c3 = st.columns(3)

            if my_status == "Booked":
                st.caption("⚠️ 이미 약속이 있는 것 같아요! (오늘은 변경/요청이 제한돼요)")

            role = st.session_state["user"].get("role")
            is_lunch = (meal == "lunch")

            # Sender lock: if I have a pending outgoing invite, I shouldn't set myself to Free.
            base_free_disabled = db.get_status_today(user_id, meal=meal) in ("Booked", "Planning")

            with c1:
                if is_lunch:
                    # 점심: 팀장/임원은 비활성화 유지
                    free_disabled = base_free_disabled or (role in ("팀장", "임원")) or expired
                    if st.button("🙇‍♂️ 점약 없어요 불러주세요", use_container_width=True, disabled=free_disabled):
                        if my_status == "Hosting":
                            confirm_hosting_cancel("Free")
                        elif my_status == "Free":
                            db.clear_status_today(user_id, meal=meal)
                            st.rerun()
                        else:
                            db.update_status(user_id, "Free", meal=meal)
                            st.rerun()
                    if role in ("팀장", "임원"):
                        st.caption("(점심은 팀장/임원 '불러주세요' 비활성화)")
                else:
                    # 저녁: 모두 가능 + 밥/술 구분
                    if st.button("🍚 저녁 밥 가능", use_container_width=True, disabled=(base_free_disabled or expired)):
                        if my_status == "Hosting":
                            confirm_hosting_cancel("Free", "meal")
                        elif my_status == "Free" and my_kind == "meal":
                            db.clear_status_today(user_id, meal=meal)
                            st.rerun()
                        else:
                            db.update_status(user_id, "Free", meal=meal, kind="meal")
                            st.rerun()

            with c2:
                if is_lunch:
                    if st.button(
                        "🙅 오늘은 넘어갈게요 (미참여)",
                        use_container_width=True,
                        disabled=(db.get_status_today(user_id, meal=meal) == "Booked"),
                    ):
                        if my_status == "Hosting":
                            confirm_hosting_cancel("Skip")
                        elif my_status == "Skip":
                            db.clear_status_today(user_id, meal=meal)
                            st.rerun()
                        else:
                            db.update_status(user_id, "Skip", meal=meal)
                            st.rerun()
                else:
                    if st.button("🍻 저녁 술 가능", use_container_width=True, disabled=(base_free_disabled or expired)):
                        if my_status == "Hosting":
                            confirm_hosting_cancel("Free", "drink")
                        elif my_status == "Free" and my_kind == "drink":
                            db.clear_status_today(user_id, meal=meal)
                            st.rerun()
                        else:
                            db.update_status(user_id, "Free", meal=meal, kind="drink")
                            st.rerun()

            with c3:
                host_label = "🧑‍🍳 오늘 점심 같이 드실분?" if is_lunch else "🌙 오늘 저녁 같이 하실분?"
                if st.button(host_label, use_container_width=True, disabled=expired):
                    currently_open = bool(st.session_state.get("hosting_open", False))
                    st.session_state["hosting_open"] = not currently_open

                    if (not currently_open) and my_status != "Booked":
                        db.update_status(user_id, "Hosting", meal=meal, kind=("meal" if (meal=="dinner") else None))

                    st.rerun()

            if db.get_status_today(user_id, meal=meal) == "Planning":
                st.caption("(초대 보낸 상태라서, 초대 철회 전까지는 '불러주세요'로 바꿀 수 없어요)")

            # Hosting inputs (open only when user toggles it)
            hosting_open = bool(st.session_state.get("hosting_open", False))
            if hosting_open:
                st.markdown("### 🧑‍🍳 합류 모집 정보")

                # Autofill current members: me + (if 1:1 booked) partner(s)
                partners = db.get_accepted_partners_today(user_id, meal=meal)
                default_members = ", ".join([current_user] + [name for _uid, name in partners])
                
                # Load existing group data for editing
                existing_group = db.get_group_by_host_today(user_id, meal=meal)
                default_seats = 1
                default_menu = ""
                default_payer = ""
                default_kind_idx = 0
                
                if existing_group:
                    # g.id, g.date, g.host_user_id, u.username, g.member_names, g.seats_left, g.menu, g.payer_name, g.kind
                    _, _, _, _, g_members, g_seats, g_menu, g_payer, g_kind = existing_group
                    default_members = g_members or default_members
                    default_seats = int(g_seats or 1)
                    default_menu = g_menu or ""
                    default_payer = g_payer or ""
                    if meal == "dinner":
                        default_kind_idx = 1 if g_kind == "drink" else 0

                with st.form("hosting_form"):
                    member_names = st.text_input("현재 멤버(이름)", value=default_members, key=f"host_members_{user_id}")
                    seats_left = st.number_input("남은 자리", min_value=0, max_value=20, value=default_seats, step=1, key=f"host_seats_{user_id}")

                    if meal == "dinner":
                        dinner_kind = st.selectbox("저녁 타입", ["밥만", "술"], index=default_kind_idx, key="dinner_kind_host")
                        st.caption("(저녁은 '밥만' / '술'로 구분됩니다)")

                    menu = st.text_input("메뉴", value=default_menu, key=f"host_menu_{user_id}")

                    st.caption("(선택) 내가쏜다!")
                    payer_name = st.text_input("누가 쏘나요? (이름 입력)", value=default_payer, key=f"host_payer_{user_id}")
                    payer_name = (payer_name or "").strip()
                    if not payer_name:
                        payer_name = None

                    submitted = st.form_submit_button("저장")

                if submitted:
                    # Dinner: allow host to mark kind (밥/술)
                    kind = None
                    if meal == "dinner":
                        v = st.session_state.get("dinner_kind_host", "밥만")
                        kind = "drink" if v == "술" else "meal"
                    db.upsert_group(
                        user_id,
                        member_names.strip(),
                        int(seats_left),
                        menu.strip(),
                        payer_name=payer_name,
                        meal=meal,
                        kind=kind,
                    )
                    # Ensure partner user_ids are in normalized group_members without consuming seats
                    for pid, _pname in partners:
                        db.ensure_member_in_group(user_id, int(pid), today_str, meal=meal)
                    # Rebuild display fields
                    try:
                        db._rebuild_group_legacy_fields(user_id, today_str, meal=meal)
                    except Exception:
                        pass
                    st.session_state["hosting_open"] = False # Close the form
                    st.success("저장 완료!")
                    st.rerun()

            st.markdown("---")


    # --- Requests (moved to My tab) ---
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

            incoming = db.list_incoming_requests(user_id, meal=meal)
            outgoing = db.list_outgoing_requests(user_id, meal=meal)

            confirmed = [r for r in incoming if r[3] == "accepted"] + [r for r in outgoing if r[3] == "accepted"]
            st.subheader(f"📊 오늘 {('점심' if meal=='lunch' else '저녁')} 성사")
            st.metric("성사 건수", len(confirmed))

            st.subheader(f"📩 오늘 받은 {('점심' if meal=='lunch' else '저녁')} 초대")
            if not incoming:
                st.caption("아직 받은 초대가 없어요.")
            else:
                for req_id, from_uid, from_name, status, ts, group_host_user_id, req_kind in incoming:
                    with st.container(border=True):
                        if group_host_user_id:
                            g = db.get_group_by_host_today(int(group_host_user_id), meal=meal)
                            st.write(f"**{from_name}** → 나 (그룹 합류 초대)")
                            if g:
                                _gid, _d, _host_uid, host_name, member_names, seats_left, menu, payer_name, g_kind = g
                                extra = f" | 내가쏜다: {payer_name} 💳" if payer_name else ""
                                host_disp = db.get_display_name(int(group_host_user_id))
                                st.caption(f"초대 팀: {host_disp} | 멤버: {member_names or '-'} | 남은 자리: {seats_left} | 메뉴: {menu or '-'}{extra}")
                        else:
                            st.write(f"**{from_name}** → 나")

                        st.caption(f"상태: {pretty_status(status)} · {ts}")

                        if status == "pending":
                            # Accept should be possible even if I'm Booked when I'm the host receiving join requests
                            is_join_to_my_group = bool(group_host_user_id) and int(group_host_user_id) == int(user_id)
                            accept_disabled = (db.get_status_today(user_id, meal=meal) == "Booked") and (not is_join_to_my_group)
                            a, b = st.columns(2)
                            with a:
                                if st.button("✅ 수락", key=f"acc_{req_id}", use_container_width=True, disabled=accept_disabled):
                                    db.update_request_status(req_id, "accepted")

                                    if group_host_user_id:
                                        host_id = int(group_host_user_id)
                                        # Two cases:
                                        # 1) I'm the host receiving a join request (from_uid wants to join my group)
                                        # 2) I'm receiving a group invite (I want to join host_id's group)
                                        if host_id == int(user_id):
                                            target_uid = int(from_uid)
                                            target_name = from_name
                                        else:
                                            target_uid = int(user_id)
                                            target_name = current_user

                                        ok_add, err_add = db.accept_group_join(host_id, target_uid, target_name, meal=meal)
                                        if ok_add:
                                            db.set_booked_for_group(host_id, meal=meal)
                                        else:
                                            st.warning(err_add or "그룹 합류 처리 실패")
                                    else:
                                        # 1:1 accept.
                                        # Keep both as Booked, and allow multiple accepts to form a natural group.
                                        db.update_status(user_id, "Booked", meal=meal)
                                        db.update_status(from_uid, "Booked", meal=meal)

                                        # If I already have a group today, add the other into that group.
                                        my_groups = db.get_groups_for_user_today(user_id, meal=meal)
                                        if my_groups:
                                            _gid, _d, my_host_uid, _hn, _mn, _sl, _m, _p, _k = my_groups[0]
                                            db.add_member_fixed_group(int(my_host_uid), int(from_uid), from_name, meal=meal)
                                        else:
                                            # create a fixed group for me and add the partner
                                            # New booking → reset chat
                                            db.clear_group_chat(int(user_id), today_str, meal=meal)
                                            db.ensure_fixed_group_today(int(user_id), meal=meal)
                                            db.add_member_fixed_group(int(user_id), int(from_uid), from_name, meal=meal)

                                        # (optional) also ensure legacy 1:1 group exists for detail compatibility
                                        db.ensure_1to1_group_today(user_id, from_uid, meal=meal, kind=my_kind)

                                    sender = db.get_user_by_id(from_uid)
                                    if sender and sender[2]:
                                        bot.send_telegram_msg(sender[2], f"✅ [Lunch Buddy] {current_user}님이 점심 초대를 수락했어요.")

                                    st.success("🍚👏 우리 같이 먹어요")
                                    st.rerun()
                            with b:
                                if st.button("❌ 거절", key=f"dec_{req_id}", use_container_width=True):
                                    db.update_request_status(req_id, "declined")
                                    st.rerun()

            st.subheader(f"📤 오늘 내가 보낸 {('점심' if meal=='lunch' else '저녁')} 초대")
            if not outgoing:
                st.caption("아직 보낸 초대가 없어요.")
            else:
                # show latest per recipient (prevents cancelled history from hiding current pending UX)
                seen = set()
                for req_id, to_uid, to_name, status, ts, _group_host_user_id, req_kind in outgoing:
                    if to_uid in seen:
                        continue
                    seen.add(to_uid)

                    with st.container(border=True):
                        st.write(f"나 → **{to_name}**")
                        st.caption(f"상태: {pretty_status(status)} · {ts}")

                        # 철회 버튼은 'pending'일 때 항상 노출
                        if status == "pending":
                            if st.button("초대 철회", key=f"cancel_{req_id}"):
                                db.cancel_request(req_id)
                                # if no more pending outgoing, unlock status back to (미정)
                                if (db.get_status_today(user_id, meal=meal) == "Planning") and (not db.has_pending_outgoing_today(user_id, meal=meal)):
                                    db.clear_status_today(user_id, meal=meal)
                                st.rerun()

            st.markdown("---")
    with tab_board:
            # --- Dashboard ---
            is_lunch = (meal == "lunch")
            meal_label = "점심" if is_lunch else "저녁"

            if expired:
                st.warning(f"⏰ {meal_label} 타임아웃! (점심 1시 / 저녁 8시 이후에는 새 매칭이 마감돼요)")

            st.subheader(f"👀 동료들의 {meal_label} 현황")

            my_status_board, my_kind_board = db.get_status_row_today(user_id, meal=meal)

            all_statuses = db.get_all_statuses(meal=meal, viewer_friends_ids=my_friends_ids)
            others = [s for s in all_statuses if s[0] != user_id]

            st.markdown(f"### 🧑‍🍳 오늘 {meal_label} 같이 하실분?")
            groups = db.get_groups_today(meal=meal, viewer_friends_ids=my_friends_ids)
            # rows: (gid, host_uid, host_name, member_names, seats_left, menu, payer_name, kind)
            joinable = [] if expired else [g for g in groups if g[4] is None or int(g[4]) > 0]
            if not joinable:
                st.caption("아직 모집 중인 팀이 없어요." if not expired else "타임아웃 이후에는 새 합류/모집이 마감돼요.")
            else:
                for gid, host_uid, host_name, member_names, seats_left, menu, payer_name, g_kind in joinable:
                    with st.container(border=True):
                        st.write(f"**호스트:** {db.get_display_name(host_uid)}")
                        if (meal == "dinner") and g_kind:
                            st.caption("타입: " + ("🍻 술" if g_kind == "drink" else "🍚 밥"))
                        st.write(f"**현재 멤버:** {member_names or '-'}")
                        st.write(f"**남은 자리:** {seats_left}")
                        st.write(f"**메뉴:** {menu or '-'}")
                        if payer_name:
                            st.write(f"**내가쏜다:** {payer_name} 💳")

                        if host_uid != user_id:
                            if st.button(
                                "🙋 저요!저요!",
                                key=f"join_{gid}",
                                use_container_width=True,
                                disabled=(db.get_status_today(user_id, meal=meal) == "Booked"),
                            ):
                                req_id, err = db.create_request(
                                    user_id,
                                    host_uid,
                                    group_host_user_id=host_uid,
                                    meal=meal,
                                    kind=(my_kind_board if meal == "dinner" else None),
                                )
                                if not req_id:
                                    st.warning(err or "요청 실패")
                                else:
                                    st.success("요청 보냈어요! (수락되면 멤버에 추가돼요)")
                                st.rerun()

            st.markdown("---")

            st.markdown("### 🙇‍♂️ 불러주세요")

            host_group = db.get_group_by_host_today(user_id, meal=meal)

            # include me too, so I can confirm my status is visible
            free_people = [] if expired else [s for s in all_statuses if s[2] == "Free"]
            if not free_people:
                st.caption("지금 '불러주세요' 상태인 사람이 없어요." if not expired else "타임아웃 이후에는 '불러주세요'를 표시하지 않아요.")
            else:
                cols = st.columns(4)
                for i, (uid, uname, _status, _chat, u_kind) in enumerate(free_people):
                    is_me = (uid == user_id)
                    with cols[i % 4]:
                        with st.container(border=True):
                            disp = db.get_display_name(uid)
                            st.markdown(f"### {disp}" + (" (나)" if is_me else ""))

                            if (meal == "dinner") and u_kind:
                                st.caption("가능: " + ("🍻 술" if u_kind == "drink" else "🍚 밥"))

                            if is_me:
                                st.caption("✅ 내가 '불러주세요'로 잘 표시되는지 확인용")

                            # 1) If I'm hosting an existing group, invite them to my group
                            if host_group and not is_me:
                                _gid, _d, _host_uid, _host_name, member_names, seats_left, menu, payer_name, g_kind = host_group
                                invite_label = "🍽️ 우리랑 같이 먹을래요?" if meal == "lunch" else "🌙 우리랑 같이 할래요?"
                                invite_disabled = (db.get_status_today(uid, meal=meal) == "Booked") or (int(seats_left or 0) <= 0)
                                if st.button(invite_label, key=f"invite_group_{uid}", use_container_width=True, disabled=invite_disabled):
                                    req_id, err = db.create_request(
                                        user_id,
                                        uid,
                                        group_host_user_id=user_id,
                                        meal=meal,
                                        kind=(my_kind_board if meal == "dinner" else None),
                                    )
                                    if not req_id:
                                        st.warning(err or "요청 실패")
                                    else:
                                        st.success("그룹 초대 보냈어요!")
                                extra = f" | 내가쏜다: {payer_name} 💳" if payer_name else ""
                                st.caption(f"(내 모임) 멤버: {member_names or '-'} | 남은 자리: {seats_left} | 메뉴: {menu or '-'}{extra}")

                            # 2) Regular 1:1 invite
                            if not is_me:
                                invite_1to1 = "🍚 밥 먹자고 찌르기!" if meal == "lunch" else "🌙 같이 하자고 찌르기!"
                                if st.button(invite_1to1, key=f"req_{uid}", use_container_width=True, disabled=(db.get_status_today(user_id, meal=meal) == "Booked")):
                                    req_id, err = db.create_request(
                                        user_id,
                                        uid,
                                        meal=meal,
                                        kind=(my_kind_board if meal == "dinner" else None),
                                    )
                                    if not req_id:
                                        st.warning(err or "요청 실패")
                                    else:
                                        st.success("요청 보냈어요!")
                                    st.rerun()

            st.markdown("---")

            # Skip board only for lunch
            if meal == "lunch":
                st.markdown("### 🙅 미참여")
                skip_people = [o for o in others if o[2] == "Skip"]
                if not skip_people:
                    st.caption("오늘 미참여로 설정한 사람이 없어요.")
                else:
                    cols = st.columns(4)
                    for i, (uid, uname, _status, _chat, _kind) in enumerate(skip_people):
                        with cols[i % 4]:
                            with st.container(border=True):
                                st.markdown(f"### {uname}")
                                st.write("상태: 오늘은 넘어갈게요 (미참여)")


if __name__ == "__main__":
    main()
