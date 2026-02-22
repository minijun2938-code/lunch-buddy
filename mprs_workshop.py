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
    st.subheader("전략 리포트 (실시간 보드 기반)")
    st.write("실시간 보드에 쌓인 내용을 요약/정리해서 워크샵 장표에 바로 붙일 수 있는 형태로 뽑습니다.")

    if st.button("✨ 전략 리포트 생성", use_container_width=True):
        raw_feedback = db.get_all_feedback()
        if not raw_feedback:
            st.warning("분석할 데이터가 부족합니다. 먼저 의견을 몇 개 등록해 주세요.")
        else:
            with st.spinner("실시간 보드 데이터를 분석 중..."):
                from collections import Counter, defaultdict
                import re

                # raw_feedback rows: (dept, target_dept, category, content, created_at)
                by_target_cat = Counter()
                by_from_to = Counter()
                quotes_by_target_cat = defaultdict(list)

                def _keywords(txt: str):
                    txt = (txt or "")
                    txt = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", txt)
                    tokens = [t.strip() for t in txt.split() if len(t.strip()) >= 2]
                    stop = {"그리고","그래서","하지만","때문","이것","저것","그냥","정말","너무","같아요","합니다","있어요","없어요","가능","불가","부서","업무","요청"}
                    return [t for t in tokens if t not in stop]

                kw_counter = Counter()

                for from_dept, target_dept, cat, content, ts in raw_feedback:
                    by_target_cat[(target_dept, cat)] += 1
                    by_from_to[(from_dept, target_dept, cat)] += 1
                    if len(quotes_by_target_cat[(target_dept, cat)]) < 5:
                        quotes_by_target_cat[(target_dept, cat)].append(content)
                    kw_counter.update(_keywords(content))

                # 1) Overview
                st.markdown("### 1) 한눈에 보는 요약")
                total = len(raw_feedback)
                st.write(f"- 총 의견 수: **{total}건**")

                # 2) Heatmap-like table (From -> To)
                st.markdown("### 2) From → To 흐름 (병목/시너지)")
                matrix_rows = []
                for f in ["M","P","R","S"]:
                    row = {"From": f}
                    for t in ["M","P","R","S"]:
                        row[t] = int(by_from_to[(f,t,"Bottleneck")] + by_from_to[(f,t,"Synergy")])
                    matrix_rows.append(row)
                st.dataframe(matrix_rows, use_container_width=True, hide_index=True)

                # 3) Top bottlenecks per target
                st.markdown("### 3) Target 부서별 병목 TOP")
                for t in ["M","P","R","S"]:
                    cnt = by_target_cat[(t, "Bottleneck")]
                    st.markdown(f"**- {t} (받은 병목): {cnt}건**")
                    qs = quotes_by_target_cat.get((t, "Bottleneck"), [])
                    if not qs:
                        st.caption("(등록된 병목이 없습니다)")
                    else:
                        for q in qs[:3]:
                            st.write(f"• {q}")

                # 4) Top synergy ideas per target
                st.markdown("### 4) Target 부서별 시너지 아이디어 TOP")
                for t in ["M","P","R","S"]:
                    cnt = by_target_cat[(t, "Synergy")]
                    st.markdown(f"**- {t} (받은 시너지): {cnt}건**")
                    qs = quotes_by_target_cat.get((t, "Synergy"), [])
                    if not qs:
                        st.caption("(등록된 시너지가 없습니다)")
                    else:
                        for q in qs[:3]:
                            st.write(f"• {q}")

                # 5) Keyword hints
                st.markdown("### 5) 반복 키워드(힌트)")
                top_kw = kw_counter.most_common(15)
                if top_kw:
                    st.write(", ".join([f"{k}({v})" for k,v in top_kw]))
                else:
                    st.caption("(키워드가 충분하지 않습니다)")

                # 6) Action plan template
                st.markdown("### 6) 워크샵 결과물 템플릿(바로 복사) ")
                st.code(
                    "\n".join([
                        "[2026 MPRS 협업 액션 아이템]",
                        "- TOP 병목 1: (From ? → To ?) / 문제: ______ / Owner: ___ / 기한: ___ / DoD: ___",
                        "- TOP 병목 2: ...",
                        "- TOP 시너지 1: (From ? → To ?) / 아이디어: ______ / Owner: ___ / 기한: ___ / DoD: ___",
                        "- TOP 시너지 2: ...",
                    ]),
                    language="text",
                )

                st.success("실시간 보드 기반 리포트 생성 완료")
