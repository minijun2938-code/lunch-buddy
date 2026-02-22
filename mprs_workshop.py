import streamlit as st
import mprs_db as db
import os
import pandas as pd

# Page Config
st.set_page_config(page_title="SK Enmove MPRS Synergy Sync 2026", layout="wide", page_icon="🤝")

# Initialize DB
db.init_db()

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
TAGS = ["커뮤니케이션", "요구사항", "리소스", "권한", "프로세스", "툴/인프라", "데이터", "의사결정"]

# Sidebar
with st.sidebar:
    st.image("https://www.skenmove.com/assets/images/common/logo.png", width=150)
    st.title("🤝 MPRS Workshop")
    st.info("SK엔무브 2026 협업 고도화를 위한 아이콘들의 목소리")
    st.caption("팁: 조별 대표 1명이 입력해도 됩니다. 의견 등록 시 From/To를 직접 선택하세요.")
    st.divider()

    st.write(f"보드 투표: {len(st.session_state['voted_items'])} (카드당 1표)")

    admin_code = st.text_input("Admin Code", type="password")
    if admin_code == "0905":
        st.markdown("### 🎛️ 관리자 컨트롤")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🛠️ 아이디어 캔버스 오픈"):
                db.set_state("canvas_open", "1")
                st.success("아이디어 캔버스 탭이 공개되었습니다")
                st.rerun()
        with c2:
            if st.button("🙈 아이디어 캔버스 숨김"):
                db.set_state("canvas_open", "0")
                st.success("아이디어 캔버스 탭을 숨겼습니다")
                st.rerun()

        if st.button("🚨 모든 데이터 초기화"):
            db.clear_db()
            db.clear_ai_suggestions()
            db.set_state("canvas_open", "0")
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
                ("S", "M", "Synergy", "툴/인프라", "협업 포털(문서/티켓/회의록) 단일화로 커뮤니케이션 비용 절감", "프로젝트 진행 중 자료가 분산될 때", "의사결정 속도 개선, 누락 감소", 3, 2),
            ]
            for dept, target, cat, tag, summary, situation, impact, sev, eff in samples:
                db.add_feedback(dept, target, cat, summary, tag=tag, situation=situation, impact=impact, severity=sev, effort=eff)
            st.success("예시 데이터가 입력되었습니다.")
            st.rerun()

# Main Header
st.title("🚀 SK Enmove: MPRS Synergy Sync 2026")

# Tabs (canvas tab is admin-toggled, shared via DB)
canvas_open = db.get_state("canvas_open", "0") == "1"

tabs = ["🗣️ 의견 남기기", "📉 병목 보드", "🌟 시너지 보드", "🎯 우선순위 매트릭스"]
if canvas_open:
    tabs.append("🛠️ 아이디어 캔버스")

_tab_objs = st.tabs(tabs)
if canvas_open:
    tab_speak, tab_bn, tab_syn, tab_matrix, tab_canvas = _tab_objs
else:
    tab_speak, tab_bn, tab_syn, tab_matrix = _tab_objs
    tab_canvas = None


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
            syn_situation = st.text_area("기대 상황")
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


with tab_matrix:
    st.subheader("Impact vs Effort 분석")
    all_data = db.get_all_feedback()
    if all_data:
        m_df = pd.DataFrame(all_data, columns=["id", "from", "target", "cat", "tag", "content", "sit", "imp", "sev", "eff", "likes", "ts"])
        import plotly.express as px

        fig = px.scatter(
            m_df,
            x="eff",
            y="sev",
            color="cat",
            size=[l + 1 for l in m_df["likes"]],
            hover_name="content",
            text="from",
            range_x=[0, 6],
            range_y=[0, 6],
            color_discrete_map={"Bottleneck": "#ED1C24", "Synergy": "#00A651"},
        )
        # (0,0) 축만 표시
        fig.add_hline(y=0, line_color="#111", line_width=2)
        fig.add_vline(x=0, line_color="#111", line_width=2)

        st.plotly_chart(fig, use_container_width=True)
        st.caption("축은 (0,0) 기준이며 값은 양수 영역(0~6)만 사용합니다.")


# AI 전략 리포트 기능은 현재 숨김 처리 (요청 반영)
if False:
    pass


if tab_canvas is not None:
    with tab_canvas:
        st.subheader("🛠️ 아이디어 캔버스 (투표 이후) ")
        st.caption("실시간 투표 결과를 보고, 선택된 카드에 대한 ‘협업 아이디어’를 정리하는 공간입니다. (기한/일정 없음, 아이디어 중심)")

        all_data = db.get_all_feedback()
        if not all_data:
            st.info("먼저 보드에 의견을 등록해 주세요.")
        else:
            # top voted lists
            bn = [f for f in all_data if f[3] == "Bottleneck"]
            syn = [f for f in all_data if f[3] == "Synergy"]
            bn_top = sorted(bn, key=lambda x: x[10], reverse=True)[:8]
            syn_top = sorted(syn, key=lambda x: x[10], reverse=True)[:8]

            left, right = st.columns(2)
            with left:
                st.markdown("### 📉 병목 Top (득표순)")
                bn_pick = st.selectbox(
                    "캔버스에 올릴 병목 카드 선택",
                    options=[f[0] for f in bn_top],
                    format_func=lambda fid: next((f"[{x[10]}표] {x[1]}→{x[2]} / {x[5]}" for x in bn_top if x[0] == fid), str(fid)),
                ) if bn_top else None
            with right:
                st.markdown("### 🌟 시너지 Top (득표순)")
                syn_pick = st.selectbox(
                    "캔버스에 올릴 시너지 카드 선택",
                    options=[f[0] for f in syn_top],
                    format_func=lambda fid: next((f"[{x[10]}표] {x[1]}→{x[2]} / {x[5]}" for x in syn_top if x[0] == fid), str(fid)),
                ) if syn_top else None

            # unify picks
            pick_id = st.radio(
                "작성할 카드 선택",
                options=[x for x in [bn_pick, syn_pick] if x is not None],
                format_func=lambda fid: f"{fid}",
                horizontal=True,
            ) if (bn_pick or syn_pick) else None

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

                    with st.form("canvas_form"):
                        st.markdown("### 협업 아이디어(아이디어만)")
                        idea1 = st.text_input("아이디어 1", placeholder="예: 협업 툴에 실시간 데이터 공유 보드를 만들고 링크/지표를 고정")
                        idea2 = st.text_input("아이디어 2", placeholder="예: 마케팅-연구소 정기 회의(월 1회)로 기술 스토리라인 합의")
                        idea3 = st.text_input("아이디어 3", placeholder="예: 요청/응답을 티켓으로 관리하고 상태를 공유")
                        collab_tool = st.text_input("협업 툴/채널(선택)", placeholder="예: Slack/Teams + Confluence/Notion + Jira/Asana")
                        meeting_cadence = st.text_input("회의/싱크 방식(선택)", placeholder="예: 주 1회 30분 / 월 1회 60분")
                        notes = st.text_area("추가 메모(선택)")
                        saved = st.form_submit_button("💾 캔버스 저장")
                        if saved:
                            db.upsert_action_item(
                                feedback_id=fid,
                                category=cat,
                                from_dept=from_dept,
                                to_dept=to_dept,
                                summary=summary,
                                votes=likes,
                                idea1=idea1,
                                idea2=idea2,
                                idea3=idea3,
                                collab_tool=collab_tool,
                                meeting_cadence=meeting_cadence,
                                notes=notes,
                            )
                            st.success("저장 완료")
                            st.rerun()

            st.markdown("---")
            st.markdown("### 📌 저장된 캔버스 목록")
            items = db.get_action_items()
            if not items:
                st.caption("아직 저장된 캔버스가 없습니다.")
            else:
                md_lines = ["# MPRS Workshop Action Canvas", ""]
                for (fid, cat, f, t, summary, votes, i1, i2, i3, tool, cadence, notes, created_at) in items:
                    st.markdown(f"**[{votes}표] {f}→{t} / {cat}**  ")
                    st.write(f"- {summary}")
                    if i1:
                        st.write(f"  - 아이디어1: {i1}")
                    if i2:
                        st.write(f"  - 아이디어2: {i2}")
                    if i3:
                        st.write(f"  - 아이디어3: {i3}")
                    if tool:
                        st.write(f"  - 협업툴: {tool}")
                    if cadence:
                        st.write(f"  - 회의: {cadence}")
                    if notes:
                        st.write(f"  - 메모: {notes}")

                    md_lines += [
                        f"## [{votes}표] {f}→{t} / {cat}",
                        f"- 요약: {summary}",
                        f"- 아이디어1: {i1}",
                        f"- 아이디어2: {i2}",
                        f"- 아이디어3: {i3}",
                        f"- 협업툴: {tool}",
                        f"- 회의: {cadence}",
                        f"- 메모: {notes}",
                        "",
                    ]

                st.download_button(
                    "📥 캔버스 결과 다운로드 (Markdown)",
                    data="\n".join(md_lines).encode("utf-8"),
                    file_name="mprs_action_canvas.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
