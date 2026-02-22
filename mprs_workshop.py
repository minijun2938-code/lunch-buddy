import streamlit as st
import mprs_db as db
import os
import pandas as pd
from collections import Counter, defaultdict

# Page Config
st.set_page_config(page_title="SK Enmove MPRS Synergy Sync 2026", layout="wide", page_icon="🤝")

# Initialize DB
db.init_db()

# Session State for Voting (1인 1표 반영)
if "voted_items" not in st.session_state:
    st.session_state["voted_items"] = set()
if "voted_ai" not in st.session_state:
    st.session_state["voted_ai"] = set()

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4A90E2; color: white; }
    .status-card { padding: 15px; border-radius: 10px; background-color: white; border-left: 10px solid #4A90E2; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; position: relative; }
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
    """, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://www.skenmove.com/assets/images/common/logo.png", width=150)
    st.title("🤝 MPRS Workshop")
    st.info("SK엔무브 2026 협업 고도화를 위한 아이콘들의 목소리")
    
    dept_choice = st.selectbox("당신의 부문(Icon)을 선택하세요", ["M (Marketing)", "P (Production)", "R (R&D)", "S (Staff)"])
    st.divider()
    
    st.write(f"보드 투표: {len(st.session_state['voted_items'])} (카드당 1표)")
    st.write(f"AI 제안 투표: {len(st.session_state['voted_ai'])} / 1")
    
    admin_code = st.text_input("Admin Code", type="password")
    if admin_code == "0905":
        if st.button("🚨 모든 데이터 초기화"):
            db.clear_db()
            db.clear_ai_suggestions()
            st.success("초기화 완료")
            st.rerun()
        
        if st.button("🪄 AI 제안 수동 생성 (테스트용)"):
            db.add_ai_suggestion("R&D 기술 언어 현지화", "Marketing과 R&D가 협업하여 복잡한 기유 기술 용어를 영업용 언어로 번역한 'Enmove 브로슈어'를 공동 제작합니다.")
            st.rerun()

# Main Header
st.title(f"🚀 SK Enmove: MPRS Synergy Sync 2026")

tab_speak, tab_board, tab_matrix, tab_ai = st.tabs(["🗣️ 의견 남기기", "📊 실시간 보드", "🎯 우선순위 매트릭스", "🔮 AI 전략 리포트"])

DEPT_MAP = {"M": "Marketing", "P": "Production", "R": "R&D", "S": "Staff"}
TAGS = ["커뮤니케이션", "요구사항", "리소스", "권한", "프로세스", "툴/인프라", "데이터", "의사결정"]

with tab_speak:
    st.subheader("타 부서와 협업하며 느꼈던 솔직한 의견을 적어주세요.")
    col1, col2 = st.columns(2)
    with col1:
        with st.form("bottleneck_form", clear_on_submit=True):
            st.error("📉 병목 포인트 (불편했던 점)")
            bn_target = st.radio("Target 부서", ["M", "P", "R", "S"], horizontal=True, key="bn_target")
            bn_tag = st.selectbox("분류", TAGS, key="bn_tag")
            bn_content = st.text_input("문제 (한 줄 요약)")
            bn_situation = st.text_area("구체적 상황 (언제/어디서?)")
            bn_impact = st.text_area("부정적 영향 (시간/품질/리스크)")
            sc1, sc2 = st.columns(2)
            bn_sev = sc1.slider("심각도 (1-5)", 1, 5, 3)
            bn_eff = sc2.slider("해결 난이도 (1-5)", 1, 5, 2)
            if st.form_submit_button("불편함 등록") and bn_content:
                db.add_feedback(dept_choice[0], bn_target, "Bottleneck", bn_content, tag=bn_tag, situation=bn_situation, impact=bn_impact, severity=bn_sev, effort=bn_eff)
                st.toast("등록되었습니다.")

    with col2:
        with st.form("synergy_form", clear_on_submit=True):
            st.success("🌟 시너지 아이디어 (함께하고 싶은 일)")
            syn_target = st.radio("Target 부서", ["M", "P", "R", "S"], horizontal=True, key="syn_target")
            syn_tag = st.selectbox("분류", TAGS, key="syn_tag")
            syn_content = st.text_input("아이디어 (한 줄 요약)")
            syn_situation = st.text_area("기대 상황")
            syn_impact = st.text_area("기대 효과")
            sc1, sc2 = st.columns(2)
            syn_sev = sc1.slider("기대 효과 (1-5)", 1, 5, 4)
            syn_eff = sc2.slider("실행 난이도 (1-5)", 1, 5, 3)
            if st.form_submit_button("아이디어 등록") and syn_content:
                db.add_feedback(dept_choice[0], syn_target, "Synergy", syn_content, tag=syn_tag, situation=syn_situation, impact=syn_impact, severity=syn_sev, effort=syn_eff)
                st.toast("등록되었습니다.")

with tab_board:
    all_data = db.get_all_feedback()
    if not all_data: st.caption("의견이 없습니다.")
    else:
        cols = st.columns(4)
        for i, d_key in enumerate(["M", "P", "R", "S"]):
            with cols[i]:
                st.markdown(f"### {d_key} ({DEPT_MAP[d_key]})")
                dept_feedback = [f for f in all_data if f[2] == d_key]
                for fid, source, target, cat, tag, content, sit, imp, sev, eff, likes, ts in dept_feedback:
                    color_class = f"{source.lower()}-color"

                    # 카드 요약(한눈에) - 카테고리(병목/시너지) 배경색으로 즉시 구분
                    cat_class = "bottleneck-card" if cat == "Bottleneck" else "synergy-card"
                    st.markdown(
                        f"""<div class="status-card {color_class} {cat_class}">
                        <div class="vote-count">👍 {likes}</div>
                        <div class="from-label">From {source}  →  To {target} · {cat}</div>
                        <strong>{'📉' if cat=='Bottleneck' else '🌟'} {content}</strong><br/>
                        <div class="tag-label">#{tag}</div>
                        <div class="tag-label">Impact:{sev}</div>
                        <div class="tag-label">Effort:{eff}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                    # 상세(전부 보이게)
                    with st.expander("상세 보기"):
                        if sit:
                            st.markdown(f"**상황**: {sit}")
                        if imp:
                            st.markdown(f"**영향/효과**: {imp}")
                        st.caption(f"작성: {ts}")

                    # 카드당 1표(= 같은 카드에는 1번만 투표 가능)
                    if st.button(
                        "👍 이 카드에 투표",
                        key=f"v_{fid}",
                        disabled=(fid in st.session_state["voted_items"]),
                    ):
                        db.add_vote(fid)
                        st.session_state["voted_items"].add(fid)
                        st.rerun()

with tab_matrix:
    st.subheader("Impact vs Effort 분석")
    all_data = db.get_all_feedback()
    if all_data:
        m_df = pd.DataFrame(all_data, columns=["id","from","target","cat","tag","content","sit","imp","sev","eff","likes","ts"])
        import plotly.express as px
        # 축을 (0,0) 기준으로 두고 양수영역만 사용
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
            color_discrete_map={"Bottleneck": "#ED1C24", "Synergy": "#FFB100"},
        )
        # 점선 가이드는 제거하고, (0,0) 축만 표시
        fig.add_hline(y=0, line_color="#111", line_width=2)
        fig.add_vline(x=0, line_color="#111", line_width=2)

        st.plotly_chart(fig, use_container_width=True)
        st.caption("축은 (0,0) 기준이며 값은 양수 영역(0~6)만 사용합니다.")

with tab_ai:
    st.subheader("🔮 실시간 보드 기반 AI 협업 전략")
    st.info("실시간 보드에 쌓인 부서별 의견과 투표 결과를 분석하여 SK엔무브에 최적화된 협업 방안을 도출합니다.")
    
    if st.button("✨ 실시간 보드 분석 및 전략 도출", use_container_width=True):
        raw_feedback = db.get_all_feedback()
        if not raw_feedback: 
            st.warning("분석할 데이터가 부족합니다. 실시간 보드에 의견을 먼저 등록해 주세요.")
        else:
            with st.spinner("실시간 보드 데이터를 심층 분석 중..."):
                # 1. 실시간 보드 데이터 가공 (AI 프롬프트용)
                # (id, dept, target_dept, category, tag, content, situation, impact, severity, effort, likes, ts)
                board_context = ""
                for f in raw_feedback:
                    board_context += f"- [From {f[1]} -> To {f[2]}] {f[3]}({f[4]}): {f[5]} (투표:{f[10]}, 심각도:{f[8]})\n"

                # 2. AI 제안 생성 (실시간 보드 데이터를 기반으로 3대 과제 도출)
                # 실제 환경에서는 Gemini API 등에 board_context를 전달합니다.
                # 여기서는 보드 데이터의 주요 키워드와 투표수를 고려한 동적 제안 로직을 시뮬레이션합니다.
                
                db.clear_ai_suggestions()
                
                # 보드 데이터에서 투표가 가장 많은 상위 의견 추출
                top_issues = sorted(raw_feedback, key=lambda x: x[10], reverse=True)[:3]
                
                def _idea_pack(from_dept, to_dept, cat, tag, summary, situation, impact):
                    """Return (title, content) ideas strictly grounded on board entry."""
                    base = f"[From {from_dept} → To {to_dept}] {summary}"

                    # common idea bullets
                    ideas = []

                    if cat == "Bottleneck":
                        # templates by tag
                        if tag in ("데이터", "툴/인프라"):
                            ideas += [
                                "협업 툴에 ‘실시간 데이터 공유 보드(단일 화면)’를 만들고, 핵심 지표/문서 링크를 한 곳으로 고정(핀)",
                                "요청/응답을 메신저 DM이 아니라 ‘티켓(요청서) + 상태(접수/진행/완료)’로 관리해 누락을 줄이기",
                            ]
                        if tag in ("커뮤니케이션", "요구사항", "의사결정"):
                            ideas += [
                                f"{from_dept}-{to_dept} 정기 싱크(30분) 운영: 이번 주 이슈 3개만 정해서 합의/정리",
                                "회의 전 ‘1페이지 브리프(목표/제약/결정필요/담당)’ 템플릿으로 의사결정 속도 올리기",
                            ]
                        if tag in ("프로세스", "권한", "리소스"):
                            ideas += [
                                "승인/결재 흐름을 ‘2단계’로 단순화(누가 최종결정인지 명확히)하고, 예외 케이스만 상향",
                                "핵심 병목에 대해 ‘RACI(책임/승인/협의/공유)’ 한 장으로 역할을 고정",
                            ]

                        # fallback
                        if not ideas:
                            ideas += [
                                f"{from_dept}-{to_dept} 간 담당자 1명씩 ‘단일 창구(SPOC)’ 지정해서 핑퐁 최소화",
                                "업무/요청 정의를 예시 포함해서 문서화(‘이 수준이면 완료’ 기준 합의)",
                            ]

                        title = f"다득표 병목 해결 아이디어: {base}"

                    else:  # Synergy
                        if tag in ("데이터", "툴/인프라"):
                            ideas += [
                                "부서 간 공통 대시보드(품질/공정/클레임/시장반응)를 만들고, ‘같은 숫자’를 보게 만들기",
                                "데이터 정의(용어/단위/주기)부터 합의해서 ‘해석 싸움’을 없애기",
                            ]
                        if tag in ("커뮤니케이션", "프로세스"):
                            ideas += [
                                "캠페인/제품/공정 변경 시 ‘런칭 체크리스트’를 공동으로 운영(변경점 공유→리스크 확인→커뮤니케이션)",
                                "주요 프로젝트는 ‘공동 킥오프 + 주간 15분 스탠드업’으로 속도 유지",
                            ]
                        if tag in ("요구사항", "의사결정"):
                            ideas += [
                                "요구사항을 ‘문장’이 아니라 ‘수용기준(acceptance criteria)’로 맞추고 재작업을 줄이기",
                                "결정이 필요한 안건은 ‘옵션 2~3개 + 트레이드오프’ 형태로 올려서 즉시 선택",
                            ]

                        if not ideas:
                            ideas += [
                                "작게 파일럿(2주) → 잘되면 확장하는 방식으로 실행 장벽 낮추기",
                                "성과를 ‘부서별’이 아니라 ‘공동 KPI’로 한 번 묶어서 원팀화",
                            ]

                        title = f"다득표 시너지 확장 아이디어: {base}"

                    # ground with board context
                    context_lines = []
                    if situation:
                        context_lines.append(f"- 보드 상황: {situation}")
                    if impact:
                        context_lines.append(f"- 보드 영향/효과: {impact}")
                    context_lines.append(f"- 보드 투표: {likes}표")

                    content = "\n".join(
                        context_lines
                        + ["", "[해결/확대 아이디어] "]
                        + [f"- {x}" for x in ideas[:4]]
                    )
                    return title, content

                for issue in top_issues:
                    # (id, dept, target_dept, category, tag, content, situation, impact, severity, effort, likes, ts)
                    _, from_dept, to_dept, cat, tag, summary, situation, impact, *_rest = issue
                    likes = issue[10]
                    title, detail = _idea_pack(from_dept, to_dept, cat, tag, summary, situation, impact)
                    db.add_ai_suggestion(title, detail)
                
                # 만약 투표 데이터가 부족할 경우 보충 제안
                if len(top_issues) < 3:
                    db.add_ai_suggestion("MPRS 통합 데이터 거버넌스 수립", "부서별로 파편화된 공정, 연구, 마케팅 데이터를 하나의 SK Enmove 통합 플랫폼으로 연결하여 부서 간 정보 비대칭을 원천 차단합니다.")

                st.success("실시간 보드 상의 핵심 이슈를 반영한 3대 전략 과제가 도출되었습니다! 아래에서 투표를 진행해 주세요.")
                st.rerun()

    suggestions = db.get_ai_suggestions()
    if suggestions:
        st.markdown("### 🗳️ AI가 제안한 협업 방안 투표")
        for sid, title, content, vcount in suggestions:
            with st.container():
                st.markdown(f"""<div class="ai-card"><h3>{title}</h3><p>{content}</p><div class="vote-count">현재 {vcount}표</div></div>""", unsafe_allow_html=True)
                if st.button(f"이 방안에 투표하기", key=f"ai_v_{sid}", disabled=(sid in st.session_state["voted_ai"] or len(st.session_state["voted_ai"]) >= 1)):
                    db.vote_ai_suggestion(sid); st.session_state["voted_ai"].add(sid); st.rerun()
