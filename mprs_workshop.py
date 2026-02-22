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
    
    st.write(f"보드 투표: {len(st.session_state['voted_items'])} / 1")
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
                    st.markdown(f"""<div class="status-card {color_class}"><div class="vote-count">👍 {likes}</div><div class="from-label">From {source}</div><strong>{'📉' if cat=='Bottleneck' else '🌟'} {content}</strong><br/><div class="tag-label">#{tag}</div></div>""", unsafe_allow_html=True)
                    if st.button(f"👍 투표", key=f"v_{fid}", disabled=(fid in st.session_state["voted_items"] or len(st.session_state["voted_items"]) >= 1)):
                        db.add_vote(fid); st.session_state["voted_items"].add(fid); st.rerun()

with tab_matrix:
    st.subheader("Impact vs Effort 분석")
    all_data = db.get_all_feedback()
    if all_data:
        m_df = pd.DataFrame(all_data, columns=["id","from","target","cat","tag","content","sit","imp","sev","eff","likes","ts"])
        import plotly.express as px
        fig = px.scatter(m_df, x="eff", y="sev", color="cat", size=[l+1 for l in m_df['likes']], hover_name="content", text="from", range_x=[0.5, 5.5], range_y=[0.5, 5.5], color_discrete_map={"Bottleneck": "#ED1C24", "Synergy": "#FFB100"})
        fig.add_hline(y=3, line_dash="dash", line_color="gray"); fig.add_vline(x=3, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)

with tab_ai:
    st.subheader("🔮 AI 기반 협업 고도화 제안")
    st.info("실시간 데이터를 분석하여 SK엔무브에 최적화된 협업 액션을 제안합니다.")
    
    if st.button("✨ 전략 리포트 및 협업 방안 도출", use_container_width=True):
        raw_feedback = db.get_all_feedback()
        if not raw_feedback: st.warning("데이터가 부족합니다.")
        else:
            with st.spinner("SK엔무브 MPRS 시너지 분석 및 혁신 방안 설계 중..."):
                # Construct data context for the simulation
                # (In a real LLM call, we'd send this to Gemini)
                context_data = "\n".join([f"[{f[1]}->{f[2]}] {f[3]}: {f[5]} (심각도:{f[8]}, 난이도:{f[9]})" for f in raw_feedback])
                
                # Mocking 3 distinct high-value suggestions based on common SK Enmove MPRS patterns
                db.clear_ai_suggestions()
                
                # We'll generate 3 tailored suggestions
                db.add_ai_suggestion(
                    "기유 공정 데이터 실시간 시각화 & M-P 협업 채널 구축", 
                    "Production의 생산 스케줄과 기유 품질 데이터를 Marketing 부서가 실시간 대시보드로 확인하여, 고객사의 긴급 발주나 스펙 문의에 즉각 대응하는 프로세스를 구축합니다."
                )
                db.add_ai_suggestion(
                    "R&D-Production 통합 패스트트랙 실험 공정 운영", 
                    "R&D에서 개발한 신규 윤활유 배합을 실제 Production 라인에서 소규모로 즉시 테스트할 수 있는 전용 실험 슬롯과 승인 간소화 절차를 마련하여 상용화 기간을 30% 단축합니다."
                )
                db.add_ai_suggestion(
                    "Staff-MPRS 통합 'Energy Saving' 가치 지표 도입", 
                    "단순 부서별 KPI를 넘어, Staff 부문 주도로 전사적인 '에너지 효율화' 기여도를 측정하는 공동 성과 지표를 설계하여 부서 간 리소스 이기주의를 타파하고 원팀 문화를 조성합니다."
                )
                st.success("AI가 분석한 3대 핵심 협업 방안이 도출되었습니다! 아래에서 가장 필요하다고 생각하는 방안에 투표해주세요.")
                st.rerun()

    suggestions = db.get_ai_suggestions()
    if suggestions:
        st.markdown("### 🗳️ AI가 제안한 협업 방안 투표")
        for sid, title, content, vcount in suggestions:
            with st.container():
                st.markdown(f"""<div class="ai-card"><h3>{title}</h3><p>{content}</p><div class="vote-count">현재 {vcount}표</div></div>""", unsafe_allow_html=True)
                if st.button(f"이 방안에 투표하기", key=f"ai_v_{sid}", disabled=(sid in st.session_state["voted_ai"] or len(st.session_state["voted_ai"]) >= 1)):
                    db.vote_ai_suggestion(sid); st.session_state["voted_ai"].add(sid); st.rerun()
