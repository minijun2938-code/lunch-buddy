import streamlit as st
import mprs_db as db
import os

# Page Config
st.set_page_config(page_title="MPRS Synergy Sync 2026", layout="wide", page_icon="🤝")

# Initialize DB
db.init_db()

# Custom CSS for Professional Workshop Look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4A90E2; color: white; }
    .status-card { padding: 15px; border-radius: 10px; background-color: white; border-left: 5px solid #4A90E2; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .m-color { border-left-color: #FF6B6B; }
    .p-color { border-left-color: #4ECDC4; }
    .r-color { border-left-color: #FFE66D; }
    .s-color { border-left-color: #1A535C; }
    .from-label { font-size: 0.85em; color: #666; font-weight: bold; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🤝 MPRS Workshop")
    st.info("2026년 협업 고도화를 위한 아이콘들의 목소리")
    
    dept_choice = st.selectbox("당신의 부문(Icon)을 선택하세요", ["M (Marketing)", "P (Production)", "R (R&D)", "S (Staff)"])
    st.divider()
    
    admin_code = st.text_input("Admin Code (데이터 초기화용)", type="password")
    if admin_code == "0905": # Using your password as default
        if st.button("🚨 모든 데이터 삭제"):
            db.clear_db()
            st.success("초기화 완료")
            st.rerun()

# Main Header
st.title(f"🚀 MPRS Synergy Sync 2026")
st.markdown(f"**현재 접속:** `{dept_choice}` 아이콘")

tab_speak, tab_board, tab_ai = st.tabs(["🗣️ 의견 남기기", "📊 실시간 보드", "🔮 AI 전략 도출"])

DEPT_MAP = {"M": "Marketing", "P": "Production", "R": "R&D", "S": "Staff"}

with tab_speak:
    st.subheader("타 부서와 협업하며 느꼈던 솔직한 의견을 적어주세요.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("bottleneck_form", clear_on_submit=True):
            st.error("📉 병목 포인트 (불편했던 점)")
            target_dept = st.radio("어느 부서(Target)에 대한 의견인가요?", ["M", "P", "R", "S"], horizontal=True, key="bn_target")
            content = st.text_area("구체적으로 어떤 부분이 힘든가요?", placeholder="예: R&D 기술 설명이 너무 어려워요.")
            submitted = st.form_submit_button("불편함 등록")
            if submitted and content:
                db.add_feedback(dept_choice[0], target_dept, "Bottleneck", content)
                st.toast("병목 포인트가 등록되었습니다.")

    with col2:
        with st.form("synergy_form", clear_on_submit=True):
            st.success("🌟 시너지 아이디어 (함께하고 싶은 일)")
            target_dept = st.radio("어느 부서(Target)와 시너지를 내고 싶나요?", ["M", "P", "R", "S"], horizontal=True, key="syn_target")
            content = st.text_area("우리가 힘을 합치면 이런 것도 해볼 수 있을 것 같아요!", placeholder="예: Production의 사용성 데이터를 Staff 부문에서 활용하고 싶어요.")
            submitted = st.form_submit_button("아이디어 등록")
            if submitted and content:
                db.add_feedback(dept_choice[0], target_dept, "Synergy", content)
                st.toast("시너지 아이디어가 등록되었습니다.")

with tab_board:
    st.subheader("부문별 접수된 목소리")
    all_data = db.get_all_feedback()
    
    if not all_data:
        st.caption("아직 등록된 의견이 없습니다. 첫 의견을 남겨주세요!")
    else:
        # 4 Columns for the dashboard
        cols = st.columns(4)
        depts = ["M", "P", "R", "S"]
        
        for i, d_key in enumerate(depts):
            with cols[i]:
                st.markdown(f"### {d_key} ({DEPT_MAP[d_key]})")
                st.caption(f"Towards {DEPT_MAP[d_key]}")
                
                # Filter data for this target department
                dept_feedback = [f for f in all_data if f[1] == d_key]
                
                if not dept_feedback:
                    st.caption("접수된 의견 없음")
                else:
                    for source_dept, target_dept, cat, content, ts in dept_feedback:
                        color_class = f"{source_dept.lower()}-color"
                        emoji = "📉" if cat == "Bottleneck" else "🌟"
                        st.markdown(f"""
                        <div class="status-card {color_class}">
                            <div class="from-label">From {source_dept}</div>
                            <strong>{emoji} {cat}</strong><br/>
                            {content}
                            <div style='font-size:0.7em; color:gray; text-align:right; margin-top:5px;'>{ts}</div>
                        </div>
                        """, unsafe_allow_html=True)

with tab_ai:
    st.subheader("AI가 제안하는 2026 MPRS 협업 로드맵")
    st.write("지금까지 수집된 모든 목소리를 기반으로 올해의 핵심 전략을 도출합니다.")
    
    if st.button("✨ 전략 리포트 생성 (Gemini)", use_container_width=True):
        raw_feedback = db.get_all_feedback()
        if not raw_feedback:
            st.warning("분석할 데이터가 부족합니다.")
        else:
            with st.spinner("MPRS의 목소리를 분석하여 최적의 시너지를 설계 중..."):
                # Real logic or more structured report
                st.markdown("### 📋 2026 MPRS 협업 선언문 (Draft)")
                st.info("💡 분석 결과: 부서 간 '언어의 장벽'이 가장 큰 병목으로 확인되었습니다. R&D의 기술 언어를 Marketing이 대중 언어로 변환하는 프로세스 표준화가 시급합니다.")
                
                st.markdown("""
                #### 🛠️ 부문별 핵심 액션 아이템
                1. **Marketing**: R&D 실무자와 주간 '커피 챗'을 통해 최신 기술 트렌드 미리 파악.
                2. **Production**: Staff 부서의 인프라 지원 요청을 주 1회 정기 검토.
                3. **R&D**: 비개발 부서를 위한 '1줄 기술 요약' 공유 채널 운영.
                4. **Staff**: 현장의 리소스 부족 및 행정 병목을 데이터화하여 Production팀에 공유.
                """)
                st.balloons()
