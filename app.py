import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import bot
import db

# --- Init ---
db.init_db()

today = datetime.date.today()
today_str = today.isoformat()
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

    st.title(f"Enmover Lunch Buddy 오늘 점심 드실분? ({today_kor})")
    st.caption(f"오늘 날짜: {today_str}")
    st.markdown("---")

    # --- Auth (sidebar) ---
    with st.sidebar:
        st.caption(f"ver {APP_VERSION}")
        st.header("🔐 회원가입 / 로그인")

        if "user" in st.session_state:
            u = st.session_state["user"]
            st.success(f"로그인됨: {u['username']} ({u['employee_id']})")

            st.markdown("---")
            st.subheader("📚 점심 기록")
            sidebar_user_id = u["user_id"]
            dates = db.list_my_group_dates(sidebar_user_id)
            if dates:
                sel = st.selectbox("날짜 선택", dates, index=0)
                groups = db.get_groups_for_user_on_date(sidebar_user_id, sel)
                if groups:
                    gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name = groups[0]
                    members = db.list_group_members(host_uid, sel)
                    st.write(f"**{sel} 점심 기록**")
                    st.write(f"멤버: {', '.join([n for _uid, n in members]) if members else (member_names or '-')}")
                    st.write(f"메뉴: {menu or '-'}")
                    if payer_name:
                        st.write(f"내가쏜다: {payer_name} 💳")
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
                employee_id = st.text_input("사번 (예: sl55555)", key="login_emp")
                pin = st.text_input("비밀번호(PIN, 숫자 4자리)", type="password", key="login_pin")

                if st.button("로그인", use_container_width=True):
                    ok, user = db.verify_login(employee_id, pin)
                    if not ok:
                        st.error("사번 또는 비밀번호가 올바르지 않습니다.")
                    else:
                        user_id, username, telegram_chat_id, team, role, mbti, age, years, emp_id, *_ = user
                        st.session_state["user"] = {
                            "user_id": user_id,
                            "username": username,
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

    user_id = st.session_state["user"]["user_id"]
    current_user = st.session_state["user"]["username"]

    # Priority: accepted -> Booked
    db.reconcile_user_today(user_id)

    # Defensive cleanup: if status says Hosting but group row is missing, show (미정)
    if db.get_status_today(user_id) == "Hosting" and not db.get_group_by_host_today(user_id):
        db.clear_status_today(user_id)

    # --- My status ---
    st.subheader("🙋 내 현황")
    my_status = db.get_status_today(user_id)

    if my_status == "Booked":
        st.markdown("## 점약 있어요 🎉")

        # Always show detail + chat (no toggle)
        if st.button("🚫 점약 취소하기", type="primary"):
            ok, err = db.cancel_booking_for_user(user_id)
            if ok:
                st.success("취소 완료")
                st.session_state.pop("hosting_open", None)
                st.rerun()
            else:
                st.error(err or "취소 실패")
    else:
        status_text = {
            "Free": "점약 없어요(불러주세요) 🟢",
            "Hosting": "오늘 점심 같이 드실분? 모집중 🧑‍🍳",
            "Planning": "점약 잡는 중 🟠",
            "Skip": "오늘은 넘어갈게요 (미참여) 🙅",
            "Not Set": "(미정)",
        }.get(my_status, my_status)
        st.info(f"현재 내 상태: **{status_text}**")

    # Show who/what (always when Booked)
    show_detail = True

    if show_detail:
        my_groups_today = db.get_groups_for_user_today(user_id)

        # If status is Booked but membership rows are missing (legacy), recover from accepted group request
        if (not my_groups_today) and my_status == "Booked":
            host_id = db.get_latest_accepted_group_host_today(user_id)
            if host_id:
                try:
                    db.ensure_member_in_group(int(host_id), int(user_id), today_str)
                except Exception:
                    pass
                my_groups_today = db.get_groups_for_user_today(user_id)

        if my_groups_today:
            gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name = my_groups_today[0]
            st.markdown("**오늘 점약 상세**" if my_status == "Booked" else "**오늘 같이 먹는 멤버**")
            members = db.list_group_members(host_uid, today_str)
            st.write(", ".join([name for _uid, name in members]) if members else (member_names or "-"))
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
            st.caption(f"호스트: {host_name}")

            # --- Members-only chat ---
            with st.expander("💬 멤버 채팅 (메뉴/시간 정하기)", expanded=True):
                realtime = st.toggle("실시간 업데이트(3초)", value=True, key=f"rt_{host_uid}")
                if realtime:
                    # rerun without full page refresh; keeps widget/session state
                    st_autorefresh(interval=3000, key=f"chat_refresh_{host_uid}")

                chat_rows = db.list_group_chat(host_uid, today_str, limit=200)
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
<div id='lb-chat-box' style='height:280px; overflow-y:auto; border:1px solid rgba(49,51,63,0.18); border-radius:8px;'>
  {''.join(items)}
</div>
<style>
.lb-chat-item{{padding:6px 8px;border-bottom:1px solid rgba(49,51,63,0.12);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;}}
.lb-chat-meta{{font-size:12px;opacity:0.75;line-height:1.15;margin-bottom:2px;}}
.lb-chat-msg{{font-size:14px;line-height:1.25;margin:0;}}
</style>
<script>
  const el = document.getElementById('lb-chat-box');
  if (el) {{ el.scrollTop = el.scrollHeight; }}
</script>
"""
                    st.components.v1.html(chat_html, height=300)

                text = st.chat_input("메시지 입력…")
                if text:
                    ok, err = db.add_group_chat(host_uid, user_id, db.get_display_name(user_id), text, today_str)
                    if not ok:
                        st.error(err or "전송 실패")
                    st.rerun()
        else:
            # 1:1 booked detail (no group) → auto-create a 1:1 group so details can be stored/shown
            if my_status == "Booked":
                d = db.get_latest_accepted_1to1_detail_today(user_id)
                if d:
                    _req_id, other_id, other_name, ts = d
                    db.ensure_1to1_group_today(user_id, int(other_id))

                    # re-fetch as group
                    my_groups_today = db.get_groups_for_user_today(user_id)
                    if my_groups_today:
                        gid, gdate, host_uid, host_name, member_names, seats_left, menu, payer_name = my_groups_today[0]
                        st.markdown("**오늘 점약 상세**")
                        members = db.list_group_members(host_uid, today_str)
                        st.write("함께: " + (", ".join([name for _uid, name in members]) if members else (member_names or "-")))
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
        st.caption("⚠️ 이미 점심약속이 있는것 같아요! (오늘은 변경/요청이 제한돼요)")

    with c1:
        role = st.session_state["user"].get("role")
        free_disabled = (db.get_status_today(user_id) == "Booked") or (role in ("팀장", "임원"))
        if st.button(
            "🟢 점약 없어요 불러주세요",
            use_container_width=True,
            disabled=free_disabled,
        ):
            db.update_status(user_id, "Free")
            st.rerun()
        if role in ("팀장", "임원"):
            st.caption("(팀장/임원은 '불러주세요'를 사용할 수 없어요)")

    with c2:
        if st.button(
            "🙅 오늘은 넘어갈게요 (미참여)",
            use_container_width=True,
            disabled=(db.get_status_today(user_id) == "Booked"),
        ):
            db.update_status(user_id, "Skip")
            st.rerun()

    with c3:
        if st.button(
            "🧑‍🍳 오늘 점심 같이 드실분?",
            use_container_width=True,
            disabled=False,
        ):
            # Allow hosting anytime (even if already matched/Booked). This is for extra recruiting.
            # If already hosting, just open the form.
            if my_status != "Booked":
                db.update_status(user_id, "Hosting")
            st.session_state["hosting_open"] = True
            st.rerun()

    # Hosting inputs
    hosting_open = st.session_state.get("hosting_open") or (db.get_status_today(user_id) == "Hosting")
    if hosting_open:
        st.markdown("### 🧑‍🍳 합류 모집 정보")

        # Autofill current members: me + (if 1:1 booked) partner(s)
        partners = db.get_accepted_partners_today(user_id)
        default_members = ", ".join([current_user] + [name for _uid, name in partners])

        with st.form("hosting_form"):
            member_names = st.text_input("현재 멤버(이름)", value=default_members)
            seats_left = st.number_input("남은 자리", min_value=0, max_value=20, value=1, step=1)
            menu = st.text_input("메뉴")

            st.caption("(선택) 내가쏜다!")
            payer_name = st.text_input("누가 쏘나요? (이름 입력)", value="")
            payer_name = (payer_name or "").strip()
            if not payer_name:
                payer_name = None

            submitted = st.form_submit_button("저장")

        if submitted:
            db.upsert_group(user_id, member_names.strip(), int(seats_left), menu.strip(), payer_name=payer_name)
            # Ensure partner user_ids are in normalized group_members without consuming seats
            for pid, _pname in partners:
                db.ensure_member_in_group(user_id, int(pid), today_str)
            # Rebuild display fields
            try:
                db._rebuild_group_legacy_fields(user_id, today_str)
            except Exception:
                pass
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
                if group_host_user_id:
                    g = db.get_group_by_host_today(int(group_host_user_id))
                    st.write(f"**{from_name}** → 나 (그룹 합류 초대)")
                    if g:
                        _gid, _d, _host_uid, host_name, member_names, seats_left, menu, payer_name = g
                        extra = f" | 내가쏜다: {payer_name} 💳" if payer_name else ""
                        st.caption(f"초대 팀: {host_name} | 멤버: {member_names or '-'} | 남은 자리: {seats_left} | 메뉴: {menu or '-'}{extra}")
                else:
                    st.write(f"**{from_name}** → 나")

                st.caption(f"상태: {pretty_status(status)} · {ts}")

                if status == "pending":
                    # If I'm already planning (I sent/received another request), block accepting others
                    accept_disabled = (db.get_status_today(user_id) == "Planning")
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

                                ok_add, err_add = db.accept_group_join(host_id, target_uid, target_name)
                                if ok_add:
                                    db.set_booked_for_group(host_id)
                                else:
                                    st.warning(err_add or "그룹 합류 처리 실패")
                            else:
                                # 1:1 accept.
                                # Keep both as Booked, and allow multiple accepts to form a natural group.
                                db.update_status(user_id, "Booked")
                                db.update_status(from_uid, "Booked")

                                # If I already have a group today, add the other into that group.
                                my_groups = db.get_groups_for_user_today(user_id)
                                if my_groups:
                                    _gid, _d, my_host_uid, _hn, _mn, _sl, _m, _p = my_groups[0]
                                    db.add_member_fixed_group(int(my_host_uid), int(from_uid), from_name)
                                else:
                                    # create a fixed group for me and add the partner
                                    db.ensure_fixed_group_today(int(user_id))
                                    db.add_member_fixed_group(int(user_id), int(from_uid), from_name)

                                # (optional) also ensure legacy 1:1 group exists for detail compatibility
                                db.ensure_1to1_group_today(user_id, from_uid)

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
        for gid, host_uid, host_name, member_names, seats_left, menu, payer_name in joinable:
            with st.container(border=True):
                st.write(f"**호스트:** {host_name}")
                st.write(f"**현재 멤버:** {member_names or '-'}")
                st.write(f"**남은 자리:** {seats_left}")
                st.write(f"**메뉴:** {menu or '-'}")
                if payer_name:
                    st.write(f"**내가쏜다:** {payer_name} 💳")

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

    host_group = db.get_group_by_host_today(user_id)

    # include me too, so I can confirm my status is visible
    free_people = [s for s in all_statuses if s[2] == "Free"]
    if not free_people:
        st.caption("지금 '불러주세요' 상태인 사람이 없어요.")
    else:
        cols = st.columns(4)
        for i, (uid, uname, _status, _chat) in enumerate(free_people):
            is_me = (uid == user_id)
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}" + (" (나)" if is_me else ""))

                    if is_me:
                        st.caption("✅ 내가 '불러주세요'로 잘 표시되는지 확인용")

                    # 1) If I'm hosting an existing group, invite them to my group
                    if host_group and not is_me:
                        _gid, _d, _host_uid, _host_name, member_names, seats_left, menu, payer_name = host_group
                        invite_label = "🍽️ 우리랑 같이 먹을래요?"
                        invite_disabled = (db.get_status_today(uid) == "Booked") or (int(seats_left or 0) <= 0)
                        if st.button(invite_label, key=f"invite_group_{uid}", use_container_width=True, disabled=invite_disabled):
                            req_id, err = db.create_request(user_id, uid, group_host_user_id=user_id)
                            if not req_id:
                                st.warning(err or "요청 실패")
                            else:
                                st.success("그룹 초대 보냈어요!")
                        extra = f" | 내가쏜다: {payer_name} 💳" if payer_name else ""
                        st.caption(f"(내 모임) 멤버: {member_names or '-'} | 남은 자리: {seats_left} | 메뉴: {menu or '-'}{extra}")

                    # 2) Regular 1:1 invite
                    if not is_me:
                        if st.button("🍚 밥 먹자고 찌르기!", key=f"req_{uid}", use_container_width=True, disabled=(db.get_status_today(user_id) == "Booked")):
                            req_id, err = db.create_request(user_id, uid)
                            if not req_id:
                                st.warning(err or "요청 실패")
                            else:
                                st.success("요청 보냈어요!")
                            st.rerun()

    st.markdown("---")
    st.markdown("### 🙅 미참여")
    skip_people = [o for o in others if o[2] == "Skip"]
    if not skip_people:
        st.caption("오늘 미참여로 설정한 사람이 없어요.")
    else:
        cols = st.columns(4)
        for i, (uid, uname, _status, _chat) in enumerate(skip_people):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"### {uname}")
                    st.write("상태: 오늘은 넘어갈게요 (미참여)")


if __name__ == "__main__":
    main()
