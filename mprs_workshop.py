import streamlit as st
import mprs_db as db
import os
import pandas as pd
import uuid
from streamlit_cookies_manager import EncryptedCookieManager

# Page Config
st.set_page_config(page_title="SK Enmove MPRS Synergy Sync 2026", layout="wide", page_icon="🤝")

# Initialize DB
db.init_db()

# Identify current user (cookie-based) so canvas entries are private per writer
cookies = EncryptedCookieManager(prefix="mprs_", password=os.environ.get("COOKIE_PASSWORD", "mprs-workshop"))
if not cookies.ready():
    st.stop()

author_id = cookies.get("uid")
if not author_id:
    author_id = str(uuid.uuid4())
    cookies["uid"] = author_id
    cookies.save()

# Session State for Voting
if "voted_items" not in st.session_state:
    st.session_state["voted_items"] = set()
if "voted_ai" not in st.session_state:
    st.session_state["voted_ai"] = set()

# Custom CSS
st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4A90E2; color: white; }
    .status-card { padding: 15px; border-radius: 10px; background-color: white; border-left: 10px solid #4A90E2; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); margin-bottom: 14px; position: relative; }
    /* Category tint: Bottleneck vs Synergy */
    .bottleneck-card { background-color: #fff1f1; } /* light red tint */
    .synergy-card { background-color: #ecfff2; }    /* light green tint */

    .ai-card { padding: 20px; border-radius: 10px; background-color: #f0f7ff; border: 1px solid #cce3ff; margin-bottom: 15px; position: relative; }
    .m-color { border-left-color: #ED1C24; } /* SK Red */
    .p-color { border-left-color: #FFB100; } /* SK Orange */
    .r-color { border-left-color: #4ECDC4; }
    .s-color { border-left-color: #1A535C; }
    .from-label { font-size: 0.8em; color: #666; font-weight: bold; margin-bottom: 2px; }
    .vote-count { position: absolute; top: 10px; right: 10px; background: #f0f2f6; padding: 2px 8px; border-radius: 15px; font-weight: bold; font-size: 0.9em; }
    .tag-label { display: inline-block; background: #e1e4e8; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; margin-right: 5px; margin-top: 5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

DEPT_MAP = {"M": "Marketing", "P": "Production", "R": "R&D", "S": "Staff"}
TAGS = ["커뮤니케이션", "요구사항", "리소스", "권한", "프로세스", "툴/인프라", "데이터", "의사결정", "기타"]

# Sidebar
with st.sidebar:
    # (logo hidden)
    st.title("🤝 MPRS Workshop")
    st.info("SK엔무브 2026 협업 고도화를 위한 아이콘들의 목소리")
    st.caption("팁: 조별 대표 1명이 입력해도 됩니다. 의견 등록 시 From/To를 직접 선택하세요.")
    st.divider()

    st.write(f"보드 투표: {len(st.session_state['voted_items'])} (카드당 1표)")

    admin_code = st.text_input("Admin Code", type="password")
    if admin_code == "0905":
        st.markdown("### 🎛️ 관리자 컨트롤")
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            if st.button("🛠️ 아이디어 캔버스 오픈"):
                db.set_state("canvas_open", "1")
                st.success("아이디어 캔버스 탭이 공개되었습니다")
                st.rerun()
        with r1c2:
            if st.button("🙈 아이디어 캔버스 숨김"):
                db.set_state("canvas_open", "0")
                st.success("아이디어 캔버스 탭을 숨겼습니다")
                st.rerun()

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            if st.button("✅ 협업방안 생성 탭 오픈"):
                db.set_state("todo_open", "1")
                st.success("협업방안 생성 탭이 공개되었습니다")
                st.rerun()
        with r2c2:
            if st.button("🙈 협업방안 생성 탭 숨김"):
                db.set_state("todo_open", "0")
                st.success("협업방안 생성 탭을 숨겼습니다")
                st.rerun()

        if st.button("🚨 모든 데이터 초기화"):
            db.clear_db()
            db.clear_action_items()
            db.clear_ai_suggestions()
            db.set_state("canvas_open", "0")
            db.set_state("todo_open", "0")
            st.success("초기화 완료")
            st.rerun()

        if st.button("🧪 성능테스트용 예시 데이터 넣기"):
            samples = [
                # Bottlenecks
                ("M", "R", "Bottleneck", "커뮤니케이션", "기술 용어가 너무 어려워서 메시지로 못 바꾸겠음", "신규 윤활유 제품 캠페인 초안 작성 단계", "광고/영업 자료 제작 지연, 고객 커뮤니케이션 품질 저하", 4, 2),
                ("P", "M", "Bottleneck", "요구사항", "시장/고객 요구 변경이 현장에 너무 늦게 공유됨", "긴급 발주/스펙 변경 발생 시", "생산 스케줄 재조정 비용 증가, 납기 리스크", 5, 3),
                ("R", "P", "Bottleneck", "프로세스", "시험 배합을 현장 검증까지 넘기는 절차가 너무 길다", "실험 배합 검증 후 파일럿 생산 전환 시", "상용화 리드타임 증가, 경쟁력 약화", 4, 4),
                ("S", "P", "Bottleneck", "리소스", "설비/구매 관련 협업 요청이 건별로 흩어져 누락됨", "정기보수/부품 교체 요청이 몰릴 때", "다운타임 증가, 비용 예측 어려움", 3, 3),
                # Synergies
                ("M", "P", "Synergy", "데이터", "공정 데이터 기반 ‘Energy Saving’ 고객 제안서 패키지", "주요 고객사 기술 미팅 준비", "고객 신뢰 상승, 차별화된 기술영업 강화", 5, 3),
                ("P", "R", "Synergy", "데이터", "품질 이상 징후 조기탐지(공정+랩 데이터) 룰셋 공동 구축", "품질 이슈 발생 전 사전 감지", "불량/클레임 감소, 안정 생산", 4, 4),
                ("R", "M", "Synergy", "커뮤니케이션", "연구소-마케팅 ‘월 1회 기술 브리핑’으로 스토리라인 합의", "분기별 제품/기술 로드맵 공유", "브랜드 메시지 일관성 확보", 4, 2),
                ("S", "M", "Synergy", "툴/인프라", "협업 포털(문서/티켓/회의록) 단일화로 커뮤니케이션 비용 절감", "프로젝트 진행 중 자료가 분산될 때}", "의사결정 속도 개선, 누락 감소", 3, 2),
            ]
            for dept, target, cat, tag, summary, situation, impact, sev, eff in samples:
                db.add_feedback(dept, target, cat, summary, tag=tag, situation=situation, impact=impact, severity=sev, effort=eff)
            st.success("예시 보드 데이터가 입력되었습니다.")
            st.rerun()

        if st.button("🧪 캔버스 예시 데이터 넣기"):
            # Ensure some feedback exists to attach to
            all_fb = db.get_all_feedback()
            if not all_fb:
                st.warning("먼저 '성능테스트용 예시 데이터 넣기'를 눌러 보드 데이터를 만든 후 실행해 주세요.")
            else:
                # attach to top 2 bottlenecks + top 2 synergies
                bn = [f for f in all_fb if f[3] == "Bottleneck"]
                syn = [f for f in all_fb if f[3] == "Synergy"]
                picks = (sorted(bn, key=lambda x: x[10], reverse=True)[:2] + sorted(syn, key=lambda x: x[10], reverse=True)[:2])
                for row in picks:
                    fid, from_dept, to_dept, cat, tag, summary, situation, impact, sev, eff, likes, ts = row
                    proposal = "\n".join([
                        "- 협업 툴(Teams/Slack)에 ‘실시간 데이터 공유 보드’를 만들고 핵심 링크/지표를 고정",
                        f"- {from_dept}-{to_dept} 정기 싱크(월 1회)로 용어/결정사항을 합의하고 회의록을 한 곳에 누적",
                        "- 요청/응답은 티켓(접수→진행→완료)으로 상태를 공유해 누락을 줄이기",
                    ])
                    db.upsert_action_item(
                        feedback_id=fid,
                        author_id=author_id,
                        category=cat,
                        from_dept=from_dept,
                        to_dept=to_dept,
                        summary=summary,
                        votes=likes,
                        proposal=proposal,
                    )
                st.success("내 캔버스에 예시 데이터가 입력되었습니다.")
                st.rerun()

# Main Header
st.title("🚀 SK Enmove: MPRS Synergy Sync 2026")

# Tabs (admin-toggled, shared via DB)
canvas_open = db.get_state("canvas_open", "0") == "1"
todo_open = db.get_state("todo_open", "0") == "1"

tabs = ["🗣️ 의견 남기기", "📉 병목 보드", "🌟 시너지 보드"]
if canvas_open:
    tabs.append("🛠️ 아이디어 캔버스")
if todo_open:
    tabs.append("✅ 협업방안 생성")

_tab_objs = st.tabs(tabs)
if canvas_open and todo_open:
    tab_speak, tab_bn, tab_syn, tab_canvas, tab_todo = _tab_objs
elif canvas_open and not todo_open:
    tab_speak, tab_bn, tab_syn, tab_canvas = _tab_objs
    tab_todo = None
elif (not canvas_open) and todo_open:
    tab_speak, tab_bn, tab_syn, tab_todo = _tab_objs
    tab_canvas = None
else:
    tab_speak, tab_bn, tab_syn = _tab_objs
    tab_canvas = None
    tab_todo = None


def render_board(category: str):
    """category: 'Bottleneck' or 'Synergy'"""
    all_data = db.get_all_feedback()
    if not all_data:
        st.caption("의견이 없습니다.")
        return

    cols = st.columns(4)
    for i, d_key in enumerate(["M", "P", "R", "S"]):
        with cols[i]:
            st.markdown(f"### {d_key} ({DEPT_MAP[d_key]})")
            dept_feedback = [f for f in all_data if f[2] == d_key and f[3] == category]

            if not dept_feedback:
                st.caption("접수된 의견 없음")
                continue

            for fid, source, target, cat, tag, content, sit, imp, sev, eff, likes, ts in dept_feedback:
                color_class = f"{source.lower()}-color"
                cat_class = "bottleneck-card" if category == "Bottleneck" else "synergy-card"
                icon = "📉" if category == "Bottleneck" else "🌟"

                st.markdown(
                    f"""<div class="status-card {color_class} {cat_class}">
                    <div class="vote-count">👍 {likes}</div>
                    <div class="from-label">From {source}  →  To {target} · {cat}</div>
                    <strong>{icon} {content}</strong><br/>
                    <div class="tag-label">#{tag}</div>
                    <div class="tag-label">Impact:{sev}</div>
                    <div class="tag-label">Effort:{eff}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                with st.expander("상세 보기", expanded=False):
                    if sit:
                        st.markdown(f"**상황**: {sit}")
                    if imp:
                        st.markdown(f"**영향/효과**: {imp}")
                    st.caption(f"작성: {ts}")

                if st.button(
                    "👍 이 카드에 투표",
                    key=f"v_{fid}",
                    disabled=(fid in st.session_state["voted_items"]),
                ):
                    db.add_vote(fid)
                    st.session_state["voted_items"].add(fid)
                    st.rerun()


with tab_speak:
    st.subheader("의견 남기기")
    st.caption("‘내 부문 선택’ 없이, 의견 등록 시 From/To를 직접 선택합니다. (조별 대표 입력 가능)")

    col1, col2 = st.columns(2)

    with col1:
        with st.form("bottleneck_form", clear_on_submit=True):
            st.error("📉 병목 포인트")
            ft1, ft2 = st.columns(2)
            bn_from = ft1.selectbox("From", ["M", "P", "R", "S"], key="bn_from")
            bn_target = ft2.selectbox("To", ["M", "P", "R", "S"], key="bn_to")
            bn_tag = st.selectbox("분류", TAGS, key="bn_tag")
            bn_content = st.text_input("문제 (한 줄 요약)")
            bn_situation = st.text_area("구체적 상황 (언제/어디서?)")
            bn_impact = st.text_area("부정적 영향 (시간/품질/리스크)")
            sc1, sc2 = st.columns(2)
            bn_sev = sc1.slider("심각도 (1-5)", 1, 5, 3)
            bn_eff = sc2.slider("해결 난이도 (1-5)", 1, 5, 2)
            if st.form_submit_button("등록") and bn_content:
                db.add_feedback(
                    bn_from,
                    bn_target,
                    "Bottleneck",
                    bn_content,
                    tag=bn_tag,
                    situation=bn_situation,
                    impact=bn_impact,
                    severity=bn_sev,
                    effort=bn_eff,
                )
                st.toast("등록되었습니다.")

    with col2:
        with st.form("synergy_form", clear_on_submit=True):
            st.success("🌟 시너지 아이디어")
            ft1, ft2 = st.columns(2)
            syn_from = ft1.selectbox("From", ["M", "P", "R", "S"], key="syn_from")
            syn_target = ft2.selectbox("To", ["M", "P", "R", "S"], key="syn_to")
            syn_tag = st.selectbox("분류", TAGS, key="syn_tag")
            syn_content = st.text_input("아이디어 (한 줄 요약)")
            syn_situation = st.text_area("구체적 상황 (언제/어디서?)")
            syn_impact = st.text_area("기대 효과")
            sc1, sc2 = st.columns(2)
            syn_sev = sc1.slider("기대 효과 (1-5)", 1, 5, 4)
            syn_eff = sc2.slider("실행 난이도 (1-5)", 1, 5, 3)
            if st.form_submit_button("등록") and syn_content:
                db.add_feedback(
                    syn_from,
                    syn_target,
                    "Synergy",
                    syn_content,
                    tag=syn_tag,
                    situation=syn_situation,
                    impact=syn_impact,
                    severity=syn_sev,
                    effort=syn_eff,
                )
                st.toast("등록되었습니다.")


with tab_bn:
    st.subheader("📉 병목 보드")
    render_board("Bottleneck")


with tab_syn:
    st.subheader("🌟 시너지 보드")
    render_board("Synergy")


# AI 전략 리포트 기능은 현재 숨김 처리 (요청 반영)
if False:
    pass


if tab_canvas is not None:
    with tab_canvas:
        st.subheader("🛠️ 아이디어 캔버스 (투표 이후)")
        st.caption("실시간 투표 결과를 보고, 선택된 카드에 대한 ‘해결 아이디어/구체적 방안’을 정리하는 공간입니다.")

        all_data = db.get_all_feedback()
        if not all_data:
            st.info("먼저 보드에 의견을 등록해 주세요.")
        else:
            bn = [f for f in all_data if f[3] == "Bottleneck"]
            syn = [f for f in all_data if f[3] == "Synergy"]
            bn_top = sorted(bn, key=lambda x: x[10], reverse=True)[:8]
            syn_top = sorted(syn, key=lambda x: x[10], reverse=True)[:8]

            pick_kind = st.radio("카테고리 선택", ["📉 병목", "🌟 시너지"], horizontal=True)

            if pick_kind.startswith("📉"):
                st.markdown("### 📉 병목 Top (득표순)")
                pick_id = st.selectbox(
                    "병목 카드 선택",
                    options=[f[0] for f in bn_top],
                    format_func=lambda fid: next((f"[{x[10]}표] {x[1]}→{x[2]} / {x[5]}" for x in bn_top if x[0] == fid), ""),
                ) if bn_top else None
            else:
                st.markdown("### 🌟 시너지 Top (득표순)")
                pick_id = st.selectbox(
                    "시너지 카드 선택",
                    options=[f[0] for f in syn_top],
                    format_func=lambda fid: next((f"[{x[10]}표] {x[1]}→{x[2]} / {x[5]}" for x in syn_top if x[0] == fid), ""),
                ) if syn_top else None

            if pick_id is None:
                st.info("득표된 카드가 아직 없으면, 먼저 보드에서 투표를 진행해 주세요.")
            else:
                row = next((x for x in all_data if x[0] == pick_id), None)
                if not row:
                    st.warning("선택한 카드를 찾지 못했습니다.")
                else:
                    fid, from_dept, to_dept, cat, tag, summary, situation, impact, sev, eff, likes, ts = row
                    st.markdown(f"#### 선택 카드: [{likes}표] {from_dept} → {to_dept} / {cat}")
                    st.write(f"**요약:** {summary}")
                    if situation:
                        st.write(f"**상황:** {situation}")
                    if impact:
                        st.write(f"**영향/효과:** {impact}")

                    with st.form("canvas_form", clear_on_submit=True):
                        st.markdown("### 어떻게 하면 좋을까요?")
                        proposal = st.text_area(
                            "아이디어와 구체적 해결 방안을 제안해주세요.",
                            placeholder="예: 협업 툴(Teams/Slack)에 ‘실시간 데이터 공유 보드’를 만들고, 공정/품질/시장반응 링크를 고정한다.\n예: 마케팅-연구소 월 1회 기술 브리핑으로 용어/스토리라인을 합의한다.",
                            height=160,
                            key="cv_proposal",
                        )
                        saved = st.form_submit_button("💾 캔버스 저장")
                        if saved:
                            db.upsert_action_item(
                                feedback_id=fid,
                                author_id=author_id,
                                category=cat,
                                from_dept=from_dept,
                                to_dept=to_dept,
                                summary=summary,
                                votes=likes,
                                proposal=proposal,
                            )
                            st.session_state["cv_proposal"] = ""
                            st.success("저장 완료")
                            st.rerun()

            st.markdown("---")
            st.markdown("### 📌 저장된 캔버스 목록 (내가 작성한 것만)")
            items = db.get_action_items(author_id=author_id)
            if not items:
                st.caption("아직 저장된 캔버스가 없습니다.")
            else:
                md_lines = ["# MPRS Workshop Action Canvas", ""]
                for (fid, _author, cat, f, t, summary, votes, proposal, created_at) in items:
                    st.markdown(f"**[{votes}표] {f}→{t} / {cat}**  ")
                    st.write(f"- {summary}")
                    if proposal:
                        st.write(proposal)

                    md_lines += [
                        f"## [{votes}표] {f}→{t} / {cat}",
                        f"- 요약: {summary}",
                        f"- 제안: {proposal}",
                        "",
                    ]

                st.download_button(
                    "📥 캔버스 결과 다운로드 (Markdown)",
                    data="\n".join(md_lines).encode("utf-8"),
                    file_name="mprs_action_canvas.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            # 협업방안/To-do 생성은 별도 탭에서 진행 (관리자 오픈)


if tab_todo is not None:
    with tab_todo:
        st.subheader("✅ 협업방안 생성 (To-do)")
        st.caption("캔버스에 저장된 모든 논의 내용을 ‘실행 To-do’ 체크리스트로 변환합니다.")

        # 이 탭은 관리자 오픈용이므로 전체 캔버스를 기준으로 생성
        items = db.get_action_items()
        if not items:
            st.info("캔버스에 저장된 항목이 없어서 To-do를 만들 수 없습니다.")
        else:
            # items: (feedback_id, author_id, category, from_dept, to_dept, summary, votes, proposal, created_at)
            def _todo_md(items_rows):
                bn = [r for r in items_rows if r[2] == "Bottleneck"]
                syn = [r for r in items_rows if r[2] == "Synergy"]

                def todos_for(r):
                    fid, _author, cat, f, t, summary, votes, proposal, created_at = r
                    header = f"### [{votes}표] {f}→{t} / {('병목' if cat=='Bottleneck' else '시너지')}"
                    lines = [header, f"- 원문(요약): {summary}"]
                    lines.append("- To-do:")

                    # proposal 문장을 줄 단위로 To-do화
                    if proposal and proposal.strip():
                        for ln in [x.strip(" -\t") for x in proposal.splitlines() if x.strip()]:
                            lines.append(f"  - [ ] {ln}")
                    else:
                        lines.append("  - [ ] (캔버스 제안이 비어있음) 해결 방안을 캔버스에 작성")

                    return "\n".join(lines)

                md = []
                md.append("# SK Enmove MPRS Workshop - To-do List (Canvas 기반)")
                md.append("")
                md.append(f"- 캔버스 항목: {len(items_rows)}개 (병목 {len(bn)} / 시너지 {len(syn)})")
                md.append("")

                md.append("## 병목 To-do (득표순)")
                if not bn:
                    md.append("- (병목 항목 없음)")
                else:
                    for r in bn:
                        md.append(todos_for(r))
                        md.append("")

                md.append("## 시너지 To-do (득표순)")
                if not syn:
                    md.append("- (시너지 항목 없음)")
                else:
                    for r in syn:
                        md.append(todos_for(r))
                        md.append("")

                return "\n".join(md)

            if st.button("✨ To-do 생성", use_container_width=True):
                todo = _todo_md(items)
                st.session_state["canvas_todo"] = todo

            todo = st.session_state.get("canvas_todo")
            if todo:
                st.markdown(todo)
                st.download_button(
                    "📥 To-do 다운로드 (Markdown)",
                    data=todo.encode("utf-8"),
                    file_name="mprs_todo.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
