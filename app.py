import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import analyzer as az

# 페이지 설정
st.set_page_config(
    page_title="이동평균선 상향 반전 감시 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS 주입 (프리미엄 다크/블루 테마 및 카드 디자인)
st.markdown("""
<style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stApp {
        background-color: #0f172a;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #38bdf8 !important;
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    .card {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 14px;
        color: #94a3b8;
    }
    .status-triggered {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 12px;
        display: inline-block;
    }
    .status-normal {
        background-color: #334155;
        color: #94a3b8;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        display: inline-block;
    }
    div[data-testid="stMetricValue"] {
        color: #38bdf8 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        color: #94a3b8;
        font-size: 16px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        color: #38bdf8 !important;
        border-bottom-color: #38bdf8 !important;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화 및 설정 로드
if "config" not in st.session_state:
    st.session_state.config = az.load_config()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

config = st.session_state.config

# 사이드바 관리자 로그인 및 잠금 제어
with st.sidebar:
    st.markdown("### 🔒 관리자 권한 설정")
    pw_hash = config.get("admin_settings", {}).get("password_hash", "")
    
    if not pw_hash:
        st.warning("⚠️ 관리자 비밀번호가 설정되지 않았습니다. 누구나 설정을 변경할 수 있습니다.")
        st.session_state.authenticated = True
    else:
        if st.session_state.authenticated:
            st.success("🔓 관리자 권한 잠금 해제됨")
            if st.button("🔒 다시 잠그기", use_container_width=True):
                st.session_state.authenticated = False
                st.rerun()
        else:
            input_pw = st.text_input("관리자 비밀번호 입력", type="password", key="sidebar_pw_input")
            if st.button("🔓 잠금 해제", use_container_width=True):
                if az.hash_password(input_pw) == pw_hash:
                    st.session_state.authenticated = True
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")

# 헤더 영역
st.title("📈 이평선 상향 반전 감시 대시보드")
st.markdown("자산들의 3개 이동평균선(200, 288, 365)이 하락/평평에서 어제 종가 기준 상승세로 돌아섰는지 실시간 분석합니다.")

# 탭 구성
tab_dash, tab_assets, tab_settings = st.tabs(["📊 실시간 대시보드", "📂 자산 관리", "⚙️ 프로그램 설정"])

# ----------------- 탭 1: 실시간 대시보드 -----------------
with tab_dash:
    st.markdown("### 🔍 실시간 시장 스캔 결과")
    
    # 분석 실행 버튼 및 상태 정보
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.info("아래의 '스캔 시작' 버튼을 누르면 yfinance로부터 최신 데이터를 수집하여 분석을 수행합니다. (자산 수에 따라 수십 초 소요될 수 있습니다.)")
    with col_btn:
        run_scan = st.button("🚀 전체 자산 스캔 시작", use_container_width=True)
    
    if run_scan:
        st.session_state.scan_results = []
        st.session_state.triggered_list = []
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        assets = config["assets"]
        total_assets = len(assets)
        
        for idx, asset in enumerate(assets):
            ticker = asset["ticker"]
            name = asset["name"]
            category = asset["category"]
            
            status_text.text(f"분석 중: {name} ({ticker}) [{idx+1}/{total_assets}]...")
            
            res = az.analyze_asset(ticker, config["ma_settings"])
            if res.get("success"):
                res["name"] = name
                res["category"] = category
                st.session_state.scan_results.append(res)
                if res["triggered"]:
                    st.session_state.triggered_list.append(res)
            else:
                st.session_state.scan_results.append({
                    "success": False,
                    "ticker": ticker,
                    "name": name,
                    "category": category,
                    "error": res.get("error", "알 수 없는 오류")
                })
            
            progress_bar.progress((idx + 1) / total_assets)
            
        status_text.text("스캔 완료!")
        progress_bar.empty()
        
        # 메일 자동 발송 체크
        send_on_trig = config.get("email_settings", {}).get("send_on_trigger", True)
        if st.session_state.triggered_list:
            if send_on_trig and config.get("email_settings", {}).get("sender_email"):
                st.toast("🚨 조건 만족 자산 포착! 알림 이메일을 전송합니다...")
                success, msg = az.send_notification_email(config["email_settings"], st.session_state.triggered_list, st.session_state.scan_results)
                if success:
                    st.success(msg)
                else:
                    st.warning(msg)
            else:
                st.info("🚨 조건 만족 자산이 포착되었습니다. (이메일 자동 발송 옵션이 비활성화되어 있거나 SMTP 설정이 누락되었습니다.)")
    
    # 스캔 결과 출력
    if "scan_results" in st.session_state:
        results = st.session_state.scan_results
        
        # 카테고리 필터링
        categories = ["전체"] + list(set([r["category"] for r in results]))
        selected_cat = st.selectbox("📂 카테고리 필터", categories)
        
        filtered_results = [
            r for r in results if selected_cat == "전체" or r["category"] == selected_cat
        ]
        
        # 카드 지표 요약
        col1, col2, col3 = st.columns(3)
        total_cnt = len(filtered_results)
        success_cnt = sum(1 for r in filtered_results if r.get("success"))
        triggered_cnt = sum(1 for r in filtered_results if r.get("success") and r["triggered"])
        
        with col1:
            st.metric("총 스캔 자산", f"{total_cnt} 개")
        with col2:
            st.metric("분석 성공", f"{success_cnt} 개", f"오류 {total_cnt-success_cnt}개", delta_color="inverse")
        with col3:
            st.metric("🚨 상향 반전 포착", f"{triggered_cnt} 개", delta_color="normal")
            
        # 결과 표 데이터 프레임 구축
        table_data = []
        for r in filtered_results:
            if r.get("success"):
                # 각 이평선의 상태 텍스트
                ma_a_status = "▲" if r["ma_a"]["upward"] else "▼"
                ma_b_status = "▲" if r["ma_b"]["upward"] else "▼"
                ma_c_status = "▲" if r["ma_c"]["upward"] else "▼"
                
                # 어제 반전 여부
                ma_a_rev = "★" if r["ma_a"]["reversed"] else ""
                ma_b_rev = "★" if r["ma_b"]["reversed"] else ""
                ma_c_rev = "★" if r["ma_c"]["reversed"] else ""
                
                table_data.append({
                    "종목명": r["name"],
                    "티커": r["ticker"],
                    "카테고리": r["category"],
                    "어제 종가": f"${r['close']:,.2f}",
                    "전일비": f"{r['change_pct']:.2f}%",
                    f"200일선": f"{ma_a_status} {ma_a_rev}",
                    f"288일선": f"{ma_b_status} {ma_b_rev}",
                    f"365일선": f"{ma_c_status} {ma_c_rev}",
                    "상향 반전 포착": "🚨 포착됨" if r["triggered"] else "대기"
                })
            else:
                table_data.append({
                    "종목명": r["name"],
                    "티커": r["ticker"],
                    "카테고리": r["category"],
                    "어제 종가": "N/A",
                    "전일비": "N/A",
                    f"200일선": "오류",
                    f"288일선": "오류",
                    f"365일선": "오류",
                    "상향 반전 포착": f"실패 ({r['error']})"
                })
                
        df_table = pd.DataFrame(table_data)
        
        # 테이블 스타일 및 표시
        st.dataframe(
            df_table,
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("---")
        st.markdown("### 📈 상세 차트 분석")
        
        # 차트를 그릴 종목 선택
        valid_tickers = [r["ticker"] for r in filtered_results if r.get("success")]
        if valid_tickers:
            selected_ticker = st.selectbox("차트를 보실 자산을 선택하세요", valid_tickers)
            
            # 선택된 자산의 결과 추출
            selected_res = next(r for r in filtered_results if r["ticker"] == selected_ticker)
            df_chart = selected_res["df"]
            
            # Plotly 캔들차트 그리기
            fig = go.Figure()
            
            # 봉 차트 추가
            fig.add_trace(go.Candlestick(
                x=df_chart.index,
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name="주가 (Close)"
            ))
            
            # 이평선 A, B, C 선 추가
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart['MA_A'],
                mode='lines', line=dict(width=1.5, color='#fb923c'),
                name=f"MA A ({config['ma_settings']['ma_a']}일)"
            ))
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart['MA_B'],
                mode='lines', line=dict(width=1.5, color='#38bdf8'),
                name=f"MA B ({config['ma_settings']['ma_b']}일)"
            ))
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart['MA_C'],
                mode='lines', line=dict(width=1.5, color='#a855f7'),
                name=f"MA C ({config['ma_settings']['ma_c']}일)"
            ))
            
            # 레이아웃 스타일 설정
            fig.update_layout(
                title=f"{selected_res['name']} ({selected_ticker}) 주가 및 이평선 흐름 (최근 1년)",
                yaxis_title="가격 (USD)",
                xaxis_title="날짜",
                template="plotly_dark",
                height=600,
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=40, b=10),
                legend=dict(
                    orientation="h",
                    y=1.08,
                    x=0.5,
                    xanchor="center"
                )
            )
            
            # 최근 1년(약 252영업일) 데이터만 디스플레이 범위로 설정하여 로딩 시 쾌적하게 보여줌
            latest_idx = df_chart.index[-1]
            one_year_ago_idx = df_chart.index[-min(252, len(df_chart))]
            fig.update_xaxes(range=[one_year_ago_idx, latest_idx])
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 상세 수치 출력 카드
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">이평선 A ({config['ma_settings']['ma_a']}일)</div>
                    <div class="metric-value">${selected_res['ma_a']['val']:,.2f}</div>
                    <div style="font-size:12px; color:{'#34d399' if selected_res['ma_a']['upward'] else '#94a3b8'}">
                        기울기: {'▲ 상승 중' if selected_res['ma_a']['upward'] else '▼ 하락/평평'} 
                        ({selected_res['ma_a']['val'] - selected_res['ma_a']['prev_val']:+.4f})
                    </div>
                    <div style="font-size:12px; color:#fb923c">
                        {'★ 어제 상향 반전 포착!' if selected_res['ma_a']['reversed'] else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">이평선 B ({config['ma_settings']['ma_b']}일)</div>
                    <div class="metric-value">${selected_res['ma_b']['val']:,.2f}</div>
                    <div style="font-size:12px; color:{'#34d399' if selected_res['ma_b']['upward'] else '#94a3b8'}">
                        기울기: {'▲ 상승 중' if selected_res['ma_b']['upward'] else '▼ 하락/평평'}
                        ({selected_res['ma_b']['val'] - selected_res['ma_b']['prev_val']:+.4f})
                    </div>
                    <div style="font-size:12px; color:#38bdf8">
                        {'★ 어제 상향 반전 포착!' if selected_res['ma_b']['reversed'] else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_c:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">이평선 C ({config['ma_settings']['ma_c']}일)</div>
                    <div class="metric-value">${selected_res['ma_c']['val']:,.2f}</div>
                    <div style="font-size:12px; color:{'#34d399' if selected_res['ma_c']['upward'] else '#94a3b8'}">
                        기울기: {'▲ 상승 중' if selected_res['ma_c']['upward'] else '▼ 하락/평평'}
                        ({selected_res['ma_c']['val'] - selected_res['ma_c']['prev_val']:+.4f})
                    </div>
                    <div style="font-size:12px; color:#a855f7">
                        {'★ 어제 상향 반전 포착!' if selected_res['ma_c']['reversed'] else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("차트를 그릴 수 있는 정상 분석 자산이 없습니다.")
    else:
        st.info("데이터를 보려면 위의 '전체 자산 스캔 시작' 버튼을 클릭하세요.")


# ----------------- 탭 2: 자산 관리 -----------------
with tab_assets:
    st.markdown("### 📂 감시 자산 목록 관리")
    st.write("프로그램에서 감시할 ETF 및 크립토 티커 목록을 관리합니다. 대소문자 관계없이 입력 가능합니다.")
    
    # 관리자 잠금 상태 안내
    if not st.session_state.authenticated:
        st.info("🔒 자산 관리(추가/삭제)가 잠겨 있습니다. 설정을 변경하려면 왼쪽 사이드바에서 비밀번호를 입력해 잠금을 해제해 주세요.")
        
    # 새로운 자산 추가 폼
    with st.form("add_asset_form"):
        col_t, col_n, col_c, col_b = st.columns([2, 3, 2, 2])
        with col_t:
            new_ticker = st.text_input("티커 (예: SPY, IBIT)", placeholder="SPY", disabled=not st.session_state.authenticated).strip().upper()
        with col_n:
            new_name = st.text_input("자산 이름 (예: S&P500)", placeholder="S&P500", disabled=not st.session_state.authenticated).strip()
        with col_c:
            new_cat = st.selectbox("카테고리 분류", ["주식", "원자재", "채권", "크립토", "기타"], disabled=not st.session_state.authenticated)
        with col_b:
            st.write("")  # 수직 정렬용 여백
            st.write("")
            add_submitted = st.form_submit_button("➕ 자산 추가", use_container_width=True, disabled=not st.session_state.authenticated)
            
        if add_submitted:
            if not new_ticker or not new_name:
                st.error("티커와 이름을 모두 입력해 주세요.")
            elif any(a["ticker"] == new_ticker for a in config["assets"]):
                st.error("이미 존재하는 티커입니다.")
            else:
                config["assets"].append({
                    "ticker": new_ticker,
                    "name": new_name,
                    "category": new_cat
                })
                if az.save_config(config):
                    st.success(f"{new_name} ({new_ticker}) 자산이 성공적으로 추가되었습니다!")
                    st.session_state.config = config
                    st.rerun()
                else:
                    st.error("설정 파일 저장 실패")
                    
    # 기존 자산 삭제 및 보기 테이블
    st.markdown("### 📋 현재 등록된 자산 목록")
    
    # 테이블 표 형태로 카테고리별 정렬하여 출력
    df_assets = pd.DataFrame(config["assets"])
    if not df_assets.empty:
        df_assets = df_assets.rename(columns={"ticker": "티커", "name": "자산명", "category": "카테고리"})
        st.dataframe(df_assets, use_container_width=True, hide_index=True)
        
        # 삭제 폼
        st.write("---")
        st.markdown("#### 🗑️ 자산 삭제")
        col_del, col_del_btn = st.columns([3, 1])
        with col_del:
            delete_ticker = st.selectbox(
                "삭제할 자산의 티커를 선택하세요", 
                [a["ticker"] for a in config["assets"]],
                format_func=lambda t: f"{t} ({next(a['name'] for a in config['assets'] if a['ticker'] == t)})"
            )
        with col_del_btn:
            st.write("")
            st.write("")
            delete_btn = st.button("🗑️ 선택 자산 삭제", use_container_width=True, type="primary", disabled=not st.session_state.authenticated)
            
        if delete_btn:
            config["assets"] = [a for a in config["assets"] if a["ticker"] != delete_ticker]
            if az.save_config(config):
                st.success(f"선택한 자산({delete_ticker})이 성공적으로 삭제되었습니다.")
                st.session_state.config = config
                st.rerun()
            else:
                st.error("설정 파일 저장 실패")
    else:
        st.info("등록된 자산이 없습니다.")


# ----------------- 탭 3: 프로그램 설정 -----------------
with tab_settings:
    st.markdown("### ⚙️ 프로그램 세부 설정")
    
    # 관리자 잠금 상태 안내
    if not st.session_state.authenticated:
        st.info("🔒 설정 변경이 잠겨 있습니다. 설정을 저장하려면 왼쪽 사이드바에서 비밀번호를 입력해 잠금을 해제해 주세요.")
        
    # 이평선 및 탐색 조건 설정
    st.markdown("#### 1. 이동평균선 및 알고리즘 설정")
    col_ma_a, col_ma_b, col_ma_c = st.columns(3)
    with col_ma_a:
        ma_a_val = st.number_input("이평선 A 기간 (일수)", min_value=5, max_value=500, value=config["ma_settings"].get("ma_a", 200), disabled=not st.session_state.authenticated)
    with col_ma_b:
        ma_b_val = st.number_input("이평선 B 기간 (일수)", min_value=5, max_value=500, value=config["ma_settings"].get("ma_b", 288), disabled=not st.session_state.authenticated)
    with col_ma_c:
        ma_c_val = st.number_input("이평선 C 기간 (일수)", min_value=5, max_value=500, value=config["ma_settings"].get("ma_c", 365), disabled=not st.session_state.authenticated)
        
    col_ma_t, col_cond = st.columns(2)
    with col_ma_t:
        ma_type_val = st.selectbox("이동평균선 계산 방식", ["SMA (단순)", "EMA (지수)"], 
                                   index=0 if config["ma_settings"].get("ma_type", "SMA") == "SMA" else 1, disabled=not st.session_state.authenticated)
    with col_cond:
        cond_map = {"joint_turn": "동시 우상향 상태 진입 (어제 모두 우상향, 그 전날엔 아님)", "individual_turn": "개별 이평선 동시 반전 (3개 모두 어제 정확히 하락->상승 반전)"}
        selected_cond_key = st.selectbox(
            "상향 전환 감지 알고리즘", 
            list(cond_map.keys()),
            format_func=lambda x: cond_map[x],
            index=0 if config["ma_settings"].get("condition_type", "joint_turn") == "joint_turn" else 1, disabled=not st.session_state.authenticated
        )
        
    # SMTP 이메일 설정
    st.markdown("#### 2. 이메일(SMTP) 알림 설정")
    st.info("알림을 받으시려면 SMTP 설정 정보를 입력해야 합니다. Gmail을 사용하는 경우 '구글 앱 비밀번호' 생성이 필요합니다.")
    
    email_settings = config.get("email_settings", {})
    smtp_server_val = st.text_input("SMTP 서버 주소", value=email_settings.get("smtp_server", "smtp.gmail.com"), disabled=not st.session_state.authenticated)
    smtp_port_val = st.number_input("SMTP 포트 번호", min_value=25, max_value=65535, value=email_settings.get("smtp_port", 587), disabled=not st.session_state.authenticated)
    sender_email_val = st.text_input("보내는 이메일 주소 (ID)", value=email_settings.get("sender_email", ""), disabled=not st.session_state.authenticated)
    sender_password_val = st.text_input("보내는 이메일 비밀번호 (앱 비밀번호)", type="password", value=email_settings.get("sender_password", ""), disabled=not st.session_state.authenticated)
    receiver_email_val = st.text_input("받는 이메일 주소", value=email_settings.get("receiver_email", ""), disabled=not st.session_state.authenticated)
    send_on_trigger_val = st.checkbox("🚨 대시보드 스캔 완료 시 이메일 즉시 자동 발송", value=email_settings.get("send_on_trigger", True), disabled=not st.session_state.authenticated)
    
    # 설정 저장 및 테스트 버튼
    col_save, col_test = st.columns(2)
    with col_save:
        save_settings = st.button("💾 설정 저장하기", use_container_width=True, disabled=not st.session_state.authenticated)
    with col_test:
        test_email = st.button("📧 SMTP 테스트 이메일 발송", use_container_width=True)
        
    if save_settings:
        config["ma_settings"] = {
            "ma_a": ma_a_val,
            "ma_b": ma_b_val,
            "ma_c": ma_c_val,
            "ma_type": "SMA" if "SMA" in ma_type_val else "EMA",
            "condition_type": selected_cond_key
        }
        config["email_settings"] = {
            "smtp_server": smtp_server_val,
            "smtp_port": smtp_port_val,
            "sender_email": sender_email_val,
            "sender_password": sender_password_val,
            "receiver_email": receiver_email_val,
            "send_on_trigger": send_on_trigger_val
        }
        
        if az.save_config(config):
            st.success("세부 설정이 성공적으로 저장되었습니다!")
            st.session_state.config = config
        else:
            st.error("설정 저장 실패")
            
    if test_email:
        # 일시적 설정 적용하여 테스트 메일 전송
        test_smtp = {
            "smtp_server": smtp_server_val,
            "smtp_port": smtp_port_val,
            "sender_email": sender_email_val,
            "sender_password": sender_password_val,
            "receiver_email": receiver_email_val
        }
        
        # 더미 데이터 생성
        test_triggered = [
            {
                "name": "테스트 자산 (예제)",
                "ticker": "TEST",
                "category": "테스트",
                "close": 123.45,
                "change_pct": 1.5,
                "date": datetime.today().strftime('%Y-%m-%d'),
                "ma_a": {"val": 120.0, "prev_val": 119.5, "upward": True, "reversed": True},
                "ma_b": {"val": 115.0, "prev_val": 114.8, "upward": True, "reversed": True},
                "ma_c": {"val": 110.0, "prev_val": 109.9, "upward": True, "reversed": True}
            }
        ]
        
        st.toast("테스트 이메일을 전송 중입니다...")
        success, msg = az.send_notification_email(test_smtp, test_triggered, [])
        if success:
            st.success(f"테스트 성공: {msg}")
        else:
            st.error(f"테스트 실패: {msg}")

    # 관리자 비밀번호 변경/설정
    st.markdown("---")
    st.markdown("#### 🔑 3. 관리자 비밀번호 변경 및 설정")
    
    # 기존 해시 확인
    admin_settings = config.get("admin_settings", {})
    has_existing_pw = len(admin_settings.get("password_hash", "")) > 0
    
    col_cur, col_new, col_conf = st.columns(3)
    with col_cur:
        if has_existing_pw:
            cur_pw = st.text_input("현재 비밀번호 입력", type="password", disabled=not st.session_state.authenticated)
        else:
            st.info("현재 설정된 비밀번호가 없습니다. 아래에 새 비밀번호를 등록하세요.")
            cur_pw = ""
    with col_new:
        new_pw = st.text_input("새 비밀번호 입력 (초기화하려면 빈칸)", type="password", disabled=not st.session_state.authenticated)
    with col_conf:
        conf_pw = st.text_input("새 비밀번호 확인", type="password", disabled=not st.session_state.authenticated)
        
    change_pw_btn = st.button("🔑 비밀번호 설정 변경", use_container_width=True, disabled=not st.session_state.authenticated)
    
    if change_pw_btn:
        pw_hash = admin_settings.get("password_hash", "")
        # 검증 로직
        if has_existing_pw and az.hash_password(cur_pw) != pw_hash:
            st.error("현재 비밀번호가 일치하지 않습니다.")
        elif new_pw != conf_pw:
            st.error("새 비밀번호와 확인 입력이 일치하지 않습니다.")
        else:
            # 해시 저장
            new_hash = az.hash_password(new_pw) if new_pw else ""
            config["admin_settings"] = {
                "password_hash": new_hash
            }
            if az.save_config(config):
                st.success("비밀번호 설정이 변경되었습니다!")
                st.session_state.config = config
                # 만약 비밀번호를 설정했으면 로그인 상태 해제하고 새로 로그인 유도
                if new_hash:
                    st.session_state.authenticated = False
                st.rerun()
            else:
                st.error("설정 파일 저장 실패")

    # 백그라운드 스케줄러 가이드
    st.markdown("---")
    st.markdown("#### ⏰ 매일 자동 실행(스케줄링) 안내")
    st.markdown("""
    본 프로그램을 매일 자동으로 실행되게 하려면 윈도우 작업 스케줄러에 `scheduler.py`를 등록해야 합니다.
    
    1. **스케줄러 스크립트 경로**: `c:\\Users\\user\\.gemini\\antigravity\\stock_finder\\scheduler.py`
    2. **배치 파일 생성 예시** (`run.bat`):
       ```bat
       @echo off
       cd /d c:\\Users\\user\\.gemini\\antigravity\\stock_finder
       .venv\\Scripts\\python.exe scheduler.py
       ```
    3. **윈도우 작업 스케줄러 설정**:
       - '기본 작업 만들기'를 클릭하여 매일 실행하고 싶은 시간(예: 미국 시장 종료 후인 아침 7시)을 트리거로 지정합니다.
       - 작업 동작에서 프로그램/스크립트로 위에서 생성한 `run.bat` 파일을 지정합니다.
    """)
