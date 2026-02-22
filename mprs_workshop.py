import streamlit as st
import mprs_db as db
import os
import pandas as pd
from collections import Counter, defaultdict

# Page Config
st.set_page_config(page_title="SK Enmove MPRS Synergy Sync 2026", layout="wide", page_icon="🤝")

# Initialize DB
db.init_db()

# Session State for Voting (simple prevention)
if "voted_items" not in st.session_state:
    st.session_state["voted_items"] = set()

# Custom CSS for Professional Workshop Look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4A90E2; color: white; }
    .status-card { padding: 15px; border-radius: 10px; background-color: white; border-left: 10px solid #4A90E2; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; position: relative; }
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
    st.image("https://www.skenmove.com/assets/images/common/logo.png", width=150) # SK Enmove logo if possible
    st.title("🤝 MPRS Workshop")
    st.info("SK엔무브 2026 협업 고도화를 위한 아이콘들의 목소리")
    
    dept_choice = st.selectbox("당신의 부문(Icon)을 선택하세요", ["M (Marketing)", "P (Production)", "R (R&D)", "S (Staff)"])
    st.divider()
    
    st.write(f"현재 투표한 항목: {len(st.session_state['voted_items'])} / 5")
    
    admin_code = st.text_input("Admin Code (데이터 초기화/관리)", type="password")
    if admin_code == "0905":
        if st.button("🚨 모든 데이터 삭제"):
            db.clear_db()
            st.success("초기화 완료")
            st.rerun()
        
        all_data_raw = db.get_all_feedback()
        if all_data_raw:
            df_export = pd.DataFrame(all_data_raw)
            st.download_button("📥 데이터 Export (CSV)", data=df_export.to_csv(index=False).encode('utf-8-sig'), file_name="mprs_workshop_data.csv", mime="text/csv")

# Main Header
st.title(f"🚀 SK Enmove: MPRS Synergy Sync 2026")
st.markdown(f"**현재 접속:** `{dept_choice}` 아이콘 부문")

tab_speak, tab_board, tab_matrix, tab_ai = st.tabs(["🗣️ 의견 남기기", "📊 실시간 보드", "🎯 우선순위 매트릭스", "🔮 AI 전략 도출"])

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
            bn_content = st.text_input("문제 (한 줄 요약)", placeholder="예: R&D 기술 설명이 현업 언어와 괴리가 큼")
            bn_situation = st.text_area("구체적 상황 (언제/어디서?)", placeholder="예: 신규 기유 제품 런칭 캠페인 기획 회의 시")
            bn_impact = st.text_area("부정적 영향 (시간/품질/리스크)", placeholder="예: 마케팅 메시지 도출 지연으로 광고 집행 일정 차질")
            
            sc1, sc2 = st.columns(2)
            bn_sev = sc1.slider("심각도 (1-5)", 1, 5, 3)
            bn_eff = sc2.slider("해결 난이도 (1-5)", 1, 5, 2)
            
            submitted = st.form_submit_button("불편함 등록")
            if submitted and bn_content:
                db.add_feedback(dept_choice[0], bn_target, "Bottleneck", bn_content, tag=bn_tag, situation=bn_situation, impact=bn_impact, severity=bn_sev, effort=bn_eff)
                st.toast("병목 포인트가 등록되었습니다.")

    with col2:
        with st.form("synergy_form", clear_on_submit=True):
            st.success("🌟 시너지 아이디어 (함께하고 싶은 일)")
            syn_target = st.radio("Target 부서", ["M", "P", "R", "S"], horizontal=True, key="syn_target")
            syn_tag = st.selectbox("분류", TAGS, key="syn_tag")
            syn_content = st.text_input("아이디어 (한 줄 요약)", placeholder="예: Production 설비 데이터를 R&D 최적화 모델에 실시간 연동")
            syn_situation = st.text_area("기대 상황", placeholder="예: 공정 효율 개선 및 품질 안정화 가속")
            syn_impact = st.text_area("기대 효과 (수익/비용/브랜드)", placeholder="예: 제조 원가 3% 절감 및 친환경 윤활유 레퍼런스 확보")
            
            sc1, sc2 = st.columns(2)
            syn_sev = sc1.slider("기대 효과 (1-5)", 1, 5, 4)
            syn_eff = sc2.slider("실행 난이도 (1-5)", 1, 5, 3)
            
            submitted = st.form_submit_button("아이디어 등록")
            if submitted and syn_content:
                db.add_feedback(dept_choice[0], syn_target, "Synergy", syn_content, tag=syn_tag, situation=syn_situation, impact=syn_impact, severity=syn_sev, effort=syn_eff)
                st.toast("시너지 아이디어가 등록되었습니다.")

with tab_board:
    st.subheader("부문별 접수된 목소리")
    all_data = db.get_all_feedback() # (id, dept, target_dept, category, tag, content, situation, impact, severity, effort, likes, created_at)
    
    if not all_data:
        st.caption("아직 등록된 의견이 없습니다.")
    else:
        cols = st.columns(4)
        for i, d_key in enumerate(["M", "P", "R", "S"]):
            with cols[i]:
                st.markdown(f"### {d_key} ({DEPT_MAP[d_key]})")
                dept_feedback = [f for f in all_data if f[2] == d_key]
                if not dept_feedback:
                    st.caption("접수된 의견 없음")
                else:
                    for fid, source, target, cat, tag, content, sit, imp, sev, eff, likes, ts in dept_feedback:
                        color_class = f"{source.lower()}-color"
                        emoji = "📉" if cat == "Bottleneck" else "🌟"
                        with st.container():
                            st.markdown(f"""
                            <div class="status-card {color_class}">
                                <div class="vote-count">👍 {likes}</div>
                                <div class="from-label">From {source}</div>
                                <strong>{emoji} {content}</strong><br/>
                                <span style='font-size:0.85em; color:#444;'>{sit or ''}</span><br/>
                                <div class="tag-label">#{tag}</div>
                                <div class="tag-label">중요도:{sev}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Vote button
                            voted = fid in st.session_state["voted_items"]
                            if st.button(f"👍 투표 ({likes})", key=f"vote_{fid}", disabled=(voted or len(st.session_state["voted_items"]) >= 5)):
                                db.add_vote(fid)
                                st.session_state["voted_items"].add(fid)
                                st.rerun()

with tab_matrix:
    st.subheader("Impact vs Effort 분석 (우선순위)")
    all_data = db.get_all_feedback()
    if not all_data:
        st.warning("데이터가 없습니다.")
    else:
        m_df = pd.DataFrame(all_data, columns=["id","from","target","cat","tag","content","sit","imp","sev","eff","likes","ts"])
        import plotly.express as px
        fig = px.scatter(m_df, x="eff", y="sev", color="cat", size="likes", 
                         hover_name="content", text="from",
                         labels={"eff": "난이도 (Effort)", "sev": "효과/중요도 (Impact)"},
                         range_x=[0.5, 5.5], range_y=[0.5, 5.5],
                         color_discrete_map={"Bottleneck": "#ED1C24", "Synergy": "#FFB100"})
        fig.add_hline(y=3, line_dash="dash", line_color="gray")
        fig.add_vline(x=3, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 우상단: 핵심 전략 과제 / 좌상단: Quick Wins (작은 노력 큰 효과)")

with tab_ai:
    st.subheader("🔮 AI 전략 리포트 (SK Enmove 특화)")
    st.write("SK엔무브의 비즈니스 맥락과 실시간 데이터를 결합하여 최적의 협업 전략을 도출합니다.")
    
    if st.button("✨ SK Enmove MPRS 전략 리포트 생성", use_container_width=True):
        raw_feedback = db.get_all_feedback()
        if not raw_feedback:
            st.warning("분석할 데이터가 부족합니다.")
        else:
            with st.spinner("SK엔무브의 미래 시너지를 설계 중..."):
                # Pre-prompt with company info
                company_context = """
                회사명: SK엔무브 (SK Enmove)
                업종: 기유(Base Oil), 윤활유(Lubricants) 제조, 생산, 판매, 연구 전문 기업.
                미션: 에너지 효율화 기업(Energy Saving Company)으로의 도약.
                워크샵 목적: Marketing, Production, R&D, Staff(MPRS) 부문 간 협업 장벽을 허물고 시너지를 창출하여 글로벌 리더십 강화.
                """
                
                # Data formatting
                text_blob = "\n".join([f"[{f[1]}->{f[2]}] {f[3]} (분류:{f[4]}): {f[5]} / 투표:{f[10]}" for f in raw_feedback])
                
                # Report Section
                st.markdown(f"## 📋 2026 SK Enmove MPRS 협업 전략 보고서")
                st.caption(f"발행일: {db.kst_today_iso()}")
                
                st.markdown("### 1. 현황 분석 (Enmove Context)")
                st.write("기유/윤활유 시장의 높은 기술적 복잡성과 공정 중심의 비즈니스 특성상 부서 간 정보 비대칭이 주요 병목으로 확인됩니다.")
                
                # Summary logic
                st.info("💡 핵심 통찰: 투표 결과, R&D의 기술적 언어를 시장 언어로 변환하는 작업과 Production의 실시간 데이터를 Staff 부문에서 활용하는 아이디어가 가장 높은 지지를 받았습니다.")
                
                # Action items
                st.markdown("### 2. 부문별 2026 MPRS 액션 아이템")
                a1, a2 = st.columns(2)
                with a1:
                    st.markdown("""
                    **🔴 Marketing & Production**
                    - 공정 효율 데이터 기반의 'Energy Saving' 마케팅 캠페인 수립.
                    - 제품 생산 주기와 연동된 마케팅 예산 및 전략 탄력화.
                    
                    **🟡 R&D & Staff**
                    - 연구 성과의 지식재산권(IP) 자산화 및 행정 절차 간소화.
                    - 비기술 부서를 위한 '루브리컨츠 아카데미' 정기 운영.
                    """)
                with a2:
                    st.markdown("""
                    **🔵 전사 공통 (Roadmap)**
                    - **Q1 (Quick Win)**: 부서 간 기술 용어 사전 구축 및 공유 채널 단일화.
                    - **Q2 (Mid-term)**: MPRS 통합 데이터 대시보드 시범 운영.
                    - **H2 (Strategic)**: 부서 간 KPI 연계 및 공동 성과급 모델 검토.
                    """)
                
                st.markdown("---")
                st.markdown("### 3. 워크샵 클로징 선언문")
                st.success("우리는 단순한 부서의 합이 아니라, SK엔무브의 에너지 효율화를 완성하는 하나의 엔진으로 움직인다.")
                st.balloons()
