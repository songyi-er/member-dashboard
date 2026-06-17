"""
=============================================================
  유아동 자사몰 회원지표 MVP 대시보드  (Streamlit)
  - 1단계: CSV 업로드 기반 프로토타입
  - 가상 데이터 자동 생성 모드 포함
=============================================================
실행:
  pip install streamlit pandas numpy plotly
  streamlit run member_dashboard.py
=============================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────
# 0. 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(
    page_title="회원지표 대시보드",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# 0-1. 글로벌 CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
/* ── 기본 배경 ── */
[data-testid="stAppViewContainer"] { background: #F7F8FC; }
[data-testid="stSidebar"]          { background: #1B2340; }
[data-testid="stSidebar"] * { color: #E8EBF5 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label { color: #A9B4D6 !important; }

/* ── KPI 카드 ── */
.kpi-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 22px 20px 18px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    border-left: 5px solid #4F6AF6;
    margin-bottom: 4px;
}
.kpi-label  { font-size: 12px; color: #8892A4; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; margin-bottom: 6px; }
.kpi-value  { font-size: 28px; font-weight: 800; color: #1B2340; line-height: 1; }
.kpi-delta  { font-size: 12px; margin-top: 6px; }
.kpi-delta.up   { color: #22C55E; }
.kpi-delta.down { color: #EF4444; }

/* ── 경고 배너 ── */
.warn-box {
    background: #FFF3CD;
    border: 1.5px solid #FACC15;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    color: #7A5700;
    margin-bottom: 10px;
}
.danger-box {
    background: #FEE2E2;
    border: 1.5px solid #EF4444;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    color: #7F1D1D;
    margin-bottom: 10px;
}

/* ── 섹션 헤더 ── */
.section-header {
    font-size: 15px;
    font-weight: 700;
    color: #1B2340;
    border-bottom: 2px solid #4F6AF6;
    padding-bottom: 6px;
    margin-bottom: 14px;
    margin-top: 10px;
}

/* ── 테이블 스타일 ── */
.stDataFrame thead th { background: #1B2340 !important; color: #fff !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 1. 가상 데이터 생성 함수들
# ─────────────────────────────────────────
GRADE_ORDER  = ["일반", "실버", "골드", "VIP", "VVIP"]
GRADE_COLORS = {"일반": "#A9B4D6", "실버": "#7EC8E3", "골드": "#FCD34D", "VIP": "#F97316", "VVIP": "#A855F7"}

@st.cache_data
def generate_orders(n=5000, seed=42):
    """주문 데이터 (orders.csv 구조)"""
    rng = np.random.default_rng(seed)
    base = datetime(2024, 1, 1)
    order_dates = [base + timedelta(days=int(d)) for d in rng.integers(0, 365, n)]
    member_type = rng.choice(["회원", "비회원"], n, p=[0.96, 0.04])
    grade = rng.choice(GRADE_ORDER, n, p=[0.45, 0.25, 0.17, 0.09, 0.04])
    payment = np.where(
        member_type == "비회원",
        rng.integers(20000, 80000, n),
        np.select(
            [grade == g for g in GRADE_ORDER],
            [rng.integers(30000, 80000, n),
             rng.integers(50000, 130000, n),
             rng.integers(80000, 200000, n),
             rng.integers(150000, 400000, n),
             rng.integers(300000, 800000, n)],
        ),
    ).astype(int)
    df = pd.DataFrame({
        "order_id":    [f"ORD{i:06d}" for i in range(n)],
        "order_date":  order_dates,
        "member_type": member_type,
        "grade":       np.where(member_type == "비회원", "-", grade),
        "member_id":   np.where(member_type == "비회원", "GUEST", [f"MEM{rng.integers(1000,9999)}" for _ in range(n)]),
        "payment_amount": payment,
        "used_point":  np.where(
            (member_type == "회원") & (rng.random(n) > 0.55),
            rng.integers(1000, 15000, n), 0
        ).astype(int),
    })
    return df


@st.cache_data
def generate_members(n=8000, seed=42):
    """회원 데이터 (members.csv 구조)"""
    rng = np.random.default_rng(seed)
    base = datetime(2022, 1, 1)
    join_dates = [base + timedelta(days=int(d)) for d in rng.integers(0, 730, n)]
    grade = rng.choice(GRADE_ORDER, n, p=[0.45, 0.25, 0.17, 0.09, 0.04])
    point_balance = np.select(
        [grade == g for g in GRADE_ORDER],
        [rng.integers(0, 5000, n),
         rng.integers(1000, 20000, n),
         rng.integers(5000, 60000, n),
         rng.integers(20000, 200000, n),
         rng.integers(80000, 500000, n)],
    ).astype(int)
    last_order = [base + timedelta(days=int(d)) for d in rng.integers(0, 730, n)]
    df = pd.DataFrame({
        "member_id":     [f"MEM{i:06d}" for i in range(n)],
        "join_date":     join_dates,
        "grade":         grade,
        "point_balance": point_balance,
        "last_order_date": last_order,
        "total_orders":  rng.integers(1, 40, n),
        "total_payment": rng.integers(30000, 5000000, n),
    })
    # 등급 전환 이력
    df["prev_grade"] = rng.choice(GRADE_ORDER, n)
    return df


@st.cache_data
def generate_weekly_kpi(seed=42):
    """주간 KPI 시계열 (weekly_kpi.csv 구조) - 52주"""
    rng = np.random.default_rng(seed)
    base = datetime(2023, 6, 1)
    weeks = pd.date_range(base, periods=52, freq="W")
    trend = np.linspace(1.0, 1.35, 52) + rng.normal(0, 0.03, 52)
    df = pd.DataFrame({
        "week_start":       weeks,
        "total_payment":    (rng.integers(80, 150, 52) * 100000 * trend).astype(int),
        "member_payment":   (rng.integers(77, 145, 52) * 100000 * trend).astype(int),
        "non_member_payment": (rng.integers(3, 7, 52) * 100000).astype(int),
        "new_members":      (rng.integers(60, 200, 52) * trend).astype(int),
        "avg_order_value":  (rng.integers(55000, 95000, 52) * trend).astype(int),
        "member_avg_order": (rng.integers(58000, 100000, 52) * trend).astype(int),
    })
    # 의도적 급락 삽입 (경고 테스트용)
    df.loc[45, "new_members"] = 30
    df.loc[46, "total_payment"] = int(df.loc[46, "total_payment"] * 0.55)
    return df


# ─────────────────────────────────────────
# 2. 헬퍼 함수
# ─────────────────────────────────────────
def fmt_krw(v):
    """원화 포맷"""
    if v >= 1_0000_0000:
        return f"{v/1_0000_0000:.1f}억원"
    elif v >= 10000:
        return f"{v/10000:.0f}만원"
    return f"{v:,}원"

def delta_html(cur, prev, unit="", reverse=False):
    if prev == 0:
        return ""
    pct = (cur - prev) / prev * 100
    arrow = "▲" if pct >= 0 else "▼"
    cls   = "up" if (pct >= 0) != reverse else "down"
    sign  = "+" if pct >= 0 else ""
    return f'<span class="kpi-delta {cls}">{arrow} {sign}{pct:.1f}%{unit} (전주 대비)</span>'

def kpi_card(label, value, delta_html_str="", accent="#4F6AF6"):
    return f"""
    <div class="kpi-card" style="border-left-color:{accent}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      {delta_html_str}
    </div>"""


# ─────────────────────────────────────────
# 3. 사이드바 – 데이터 소스 선택 & 업로드
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👶 회원지표 대시보드")
    st.markdown("---")
    data_mode = st.radio(
        "데이터 소스",
        ["🎲 가상 데이터 (데모)", "📂 CSV 파일 업로드", "🔗 카페24 API 연동"],
        index=0,
    )
    st.markdown("---")

    if data_mode == "📂 CSV 파일 업로드":
        st.markdown("**필수 CSV 파일 업로드**")
        up_orders  = st.file_uploader("① 주문 데이터 (orders.csv)",  type="csv")
        up_members = st.file_uploader("② 회원 데이터 (members.csv)", type="csv")
        up_kpi     = st.file_uploader("③ 주간 KPI (weekly_kpi.csv)", type="csv")
        st.caption("컬럼 형식은 하단 '컬럼 가이드' 참조")

    elif data_mode == "🔗 카페24 API 연동":
        up_orders = up_members = up_kpi = None
        st.markdown("**카페24 API 연동**")

        # Secrets 설정 여부 확인
        secrets_ok = all(k in st.secrets for k in [
            "CAFE24_MALL_ID", "CAFE24_CLIENT_ID", "CAFE24_CLIENT_SECRET"
        ])

        if not secrets_ok:
            st.error("⚠️ Streamlit Secrets 설정이 필요해요!\n\nStreamlit Cloud → 앱 Settings → Secrets에 카페24 키를 입력해주세요.")
        else:
            mall_id = st.secrets["CAFE24_MALL_ID"]
            st.success(f"✅ 쇼핑몰 연결됨: {mall_id}")

            # 토큰 발급 여부 확인
            token_ok = "CAFE24_ACCESS_TOKEN" in st.secrets and st.secrets["CAFE24_ACCESS_TOKEN"] != ""

            if not token_ok:
                st.warning("카페24 인증이 필요해요.")
                try:
                    from cafe24_api import get_auth_url
                    auth_url = get_auth_url()
                    st.markdown(f"[🔐 카페24 인증하기]({auth_url})", unsafe_allow_html=False)
                    st.caption("버튼 클릭 → 쇼핑몰 관리자 로그인 → 완료")
                except Exception as e:
                    st.error(f"인증 URL 생성 실패: {e}")
            else:
                # 조회 기간 설정
                st.markdown("**조회 기간**")
                start_date = st.date_input("시작일", value=datetime.now() - timedelta(days=90))
                end_date   = st.date_input("종료일", value=datetime.now())

                if st.button("🔄 데이터 새로고침", use_container_width=True):
                    st.cache_data.clear()
                    st.rerun()

                st.session_state["api_start"] = str(start_date)
                st.session_state["api_end"]   = str(end_date)

    else:
        up_orders = up_members = up_kpi = None

    st.markdown("---")
    st.markdown("**조회 기준 주 설정**")
    ref_week_offset = st.slider("최근 N주 기준", 1, 52, 4)
    st.markdown("---")
    st.caption("© 2025 자사몰 회원지표 MVP v1.0")


# ─────────────────────────────────────────
# 4. 데이터 로딩
# ─────────────────────────────────────────
@st.cache_data
def load_csv(file):
    return pd.read_csv(file, encoding="utf-8-sig", parse_dates=True)

if data_mode == "📂 CSV 파일 업로드" and up_orders and up_members and up_kpi:
    df_orders  = load_csv(up_orders)
    df_members = load_csv(up_members)
    df_kpi     = load_csv(up_kpi)
    for col in ["order_date"]:
        if col in df_orders.columns:
            df_orders[col] = pd.to_datetime(df_orders[col])
    for col in ["join_date", "last_order_date"]:
        if col in df_members.columns:
            df_members[col] = pd.to_datetime(df_members[col])
    df_kpi["week_start"] = pd.to_datetime(df_kpi["week_start"])
    st.sidebar.success("✅ CSV 로딩 완료")

elif data_mode == "🔗 카페24 API 연동" and "CAFE24_ACCESS_TOKEN" in st.secrets and st.secrets["CAFE24_ACCESS_TOKEN"] != "":
    try:
        from cafe24_api import fetch_orders, fetch_members, build_weekly_kpi, build_weekly_new_members
        start = st.session_state.get("api_start", str(datetime.now() - timedelta(days=90)))
        end   = st.session_state.get("api_end",   str(datetime.now()))
        with st.spinner("카페24에서 데이터 불러오는 중..."):
            df_orders  = fetch_orders(start, end)
            df_members = fetch_members()
            df_kpi     = build_weekly_kpi(df_orders)
            new_mem_weekly = build_weekly_new_members(df_members)
            if not df_kpi.empty and not new_mem_weekly.empty:
                df_kpi = df_kpi.merge(new_mem_weekly, on="week_start", how="left", suffixes=("","_m"))
                if "new_members_m" in df_kpi.columns:
                    df_kpi["new_members"] = df_kpi["new_members_m"].fillna(0).astype(int)
                    df_kpi.drop(columns=["new_members_m"], inplace=True)
        st.sidebar.success("✅ 카페24 실데이터 연동 완료!")
    except Exception as e:
        st.sidebar.error(f"API 오류: {e}")
        df_orders  = generate_orders()
        df_members = generate_members()
        df_kpi     = generate_weekly_kpi()

else:
    df_orders  = generate_orders()
    df_members = generate_members()
    df_kpi     = generate_weekly_kpi()
    if data_mode == "📂 CSV 파일 업로드":
        st.sidebar.warning("⚠️ 파일 미업로드 → 가상 데이터로 실행")


# ─────────────────────────────────────────
# 5. 공통 전처리
# ─────────────────────────────────────────
latest_week  = df_kpi["week_start"].max()
target_weeks = df_kpi[df_kpi["week_start"] >= (latest_week - timedelta(weeks=ref_week_offset))]
cur_row  = df_kpi.iloc[-1]
prev_row = df_kpi.iloc[-2] if len(df_kpi) >= 2 else cur_row

# 경고 임계값
WARN_DROP_PCT = -20   # -20% 이하면 경고
DANGER_DROP_PCT = -35  # -35% 이하면 위험

def drop_pct(cur, prev):
    if prev == 0:
        return 0
    return (cur - prev) / prev * 100


# ─────────────────────────────────────────
# 6. 탭 레이아웃
# ─────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📊 요약 대시보드",
    "👥 회원 등급 & 구매 분석",
    "💰 적립금 & 락인 전략",
])


# ╔══════════════════════════════════════════╗
# ║  TAB 1 – 요약 대시보드                     ║
# ╚══════════════════════════════════════════╝
with tab1:
    st.markdown("### 📊 요약 대시보드")
    st.caption(f"기준 주: {latest_week.strftime('%Y년 %m월 %d일')} | 최근 {ref_week_offset}주 집계")

    # ── 경고 배너 ──────────────────────────
    alerts = []
    checks = [
        ("총 결제금액", "total_payment", False),
        ("신규 가입자",  "new_members",   False),
        ("평균 객단가",  "avg_order_value", False),
    ]
    for label, col, rev in checks:
        if col in cur_row.index:
            dp = drop_pct(cur_row[col], prev_row[col])
            if dp <= DANGER_DROP_PCT:
                alerts.append(("danger", f"🚨 {label} 전주 대비 {dp:.1f}% 급락 – 즉시 점검 필요"))
            elif dp <= WARN_DROP_PCT:
                alerts.append(("warn",   f"⚠️ {label} 전주 대비 {dp:.1f}% 하락 – 모니터링 필요"))
    for typ, msg in alerts:
        cls = "danger-box" if typ == "danger" else "warn-box"
        st.markdown(f'<div class="{cls}">{msg}</div>', unsafe_allow_html=True)

    # ── KPI 카드 ───────────────────────────
    total_pay    = int(cur_row["total_payment"])
    member_pay   = int(cur_row["member_payment"])
    member_ratio = member_pay / total_pay * 100 if total_pay else 0
    new_members  = int(cur_row["new_members"])
    avg_order    = int(cur_row["avg_order_value"])

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        st.markdown(kpi_card(
            "총 결제금액 (최근 주)",
            fmt_krw(total_pay),
            delta_html(total_pay, int(prev_row["total_payment"])),
            "#4F6AF6"
        ), unsafe_allow_html=True)
    with kc2:
        st.markdown(kpi_card(
            "회원 매출 비중",
            f"{member_ratio:.1f}%",
            delta_html(member_ratio, int(prev_row["member_payment"])/int(prev_row["total_payment"])*100),
            "#22C55E"
        ), unsafe_allow_html=True)
    with kc3:
        st.markdown(kpi_card(
            "전체 객단가",
            fmt_krw(avg_order),
            delta_html(avg_order, int(prev_row["avg_order_value"])),
            "#F97316"
        ), unsafe_allow_html=True)
    with kc4:
        st.markdown(kpi_card(
            "신규 가입자 수",
            f"{new_members:,}명",
            delta_html(new_members, int(prev_row["new_members"])),
            "#A855F7"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 매출 트렌드 차트 ────────────────────
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown('<div class="section-header">📈 주간 총 결제금액 추이</div>', unsafe_allow_html=True)
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=target_weeks["week_start"], y=target_weeks["total_payment"],
            mode="lines+markers", name="총 결제금액",
            line=dict(color="#4F6AF6", width=2.5),
            fill="tozeroy", fillcolor="rgba(79,106,246,0.08)"
        ))
        fig_trend.add_trace(go.Scatter(
            x=target_weeks["week_start"], y=target_weeks["member_payment"],
            mode="lines", name="회원 결제금액",
            line=dict(color="#22C55E", width=2, dash="dot")
        ))
        fig_trend.update_layout(
            height=280, margin=dict(l=0,r=0,t=10,b=0),
            legend=dict(orientation="h", y=1.1),
            paper_bgcolor="white", plot_bgcolor="white",
            yaxis=dict(tickformat=",d", title=""),
            xaxis=dict(title=""),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-header">🍩 회원/비회원 매출 비중</div>', unsafe_allow_html=True)
        mem_total    = target_weeks["member_payment"].sum()
        non_mem_total = target_weeks["non_member_payment"].sum()
        fig_donut = go.Figure(go.Pie(
            labels=["회원", "비회원"],
            values=[mem_total, non_mem_total],
            hole=0.62,
            marker_colors=["#4F6AF6", "#E5E7EB"],
            textinfo="label+percent",
            textfont_size=13,
        ))
        fig_donut.add_annotation(
            text=f"<b>{mem_total/(mem_total+non_mem_total)*100:.1f}%</b><br>회원",
            x=0.5, y=0.5, font_size=18, showarrow=False
        )
        fig_donut.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                                paper_bgcolor="white", showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── 신규 가입자 추이 ────────────────────
    col_nl, col_nr = st.columns([3, 2])
    with col_nl:
        st.markdown('<div class="section-header">🆕 주간 신규 가입자 추이</div>', unsafe_allow_html=True)
        fig_new = px.bar(
            target_weeks, x="week_start", y="new_members",
            color_discrete_sequence=["#A855F7"],
        )
        fig_new.update_layout(height=230, margin=dict(l=0,r=0,t=10,b=0),
                               paper_bgcolor="white", plot_bgcolor="white",
                               xaxis_title="", yaxis_title="신규 가입자(명)")
        st.plotly_chart(fig_new, use_container_width=True)

    with col_nr:
        st.markdown('<div class="section-header">🏬 경쟁 플랫폼 회원 성장 비교</div>', unsafe_allow_html=True)
        comp = pd.DataFrame({
            "플랫폼": ["자사몰", "키디키디", "보리보리", "마미톡"],
            "월 신규 회원 증가율(%)": [8.2, 5.1, 6.4, 4.7],
            "추정 활성 회원수(만)": [12.3, 28.5, 19.2, 8.9],
        })
        fig_comp = px.bar(
            comp, x="플랫폼", y="월 신규 회원 증가율(%)",
            color="플랫폼",
            color_discrete_map={"자사몰": "#4F6AF6", "키디키디": "#F97316",
                                 "보리보리": "#22C55E", "마미톡": "#A9B4D6"},
            text="월 신규 회원 증가율(%)",
        )
        fig_comp.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_comp.update_layout(height=230, margin=dict(l=0,r=0,t=10,b=0),
                                paper_bgcolor="white", plot_bgcolor="white",
                                showlegend=False, yaxis_title="")
        st.plotly_chart(fig_comp, use_container_width=True)
        st.caption("⚠️ 경쟁사 데이터는 추정치입니다. 실제 데이터로 교체 필요.")


# ╔══════════════════════════════════════════╗
# ║  TAB 2 – 회원 등급 & 구매 분석              ║
# ╚══════════════════════════════════════════╝
with tab2:
    st.markdown("### 👥 회원 등급 & 구매 행동 분석")

    mem_orders = df_orders[df_orders["member_type"] == "회원"].copy()

    # ── 등급별 분포 & 매출 기여 ─────────────
    grade_pay = mem_orders.groupby("grade")["payment_amount"].agg(["sum","count","mean"]).reset_index()
    grade_pay.columns = ["grade","total_payment","order_count","avg_payment"]
    grade_pay["payment_pct"] = grade_pay["total_payment"] / grade_pay["total_payment"].sum() * 100
    grade_pay["grade"] = pd.Categorical(grade_pay["grade"], categories=GRADE_ORDER, ordered=True)
    grade_pay = grade_pay.sort_values("grade")

    grade_mem = df_members.groupby("grade").size().reset_index(name="member_count")
    grade_mem["grade"] = pd.Categorical(grade_mem["grade"], categories=GRADE_ORDER, ordered=True)
    grade_mem = grade_mem.sort_values("grade")
    grade_mem["member_pct"] = grade_mem["member_count"] / grade_mem["member_count"].sum() * 100

    st.markdown('<div class="section-header">📊 등급별 회원 수 & 매출 기여도</div>', unsafe_allow_html=True)
    g1, g2, g3 = st.columns(3)

    with g1:
        fig_mem_dist = px.pie(
            grade_mem, names="grade", values="member_count",
            color="grade",
            color_discrete_map=GRADE_COLORS,
            title="등급별 회원 수 비중",
        )
        fig_mem_dist.update_traces(textinfo="label+percent", hole=0.4)
        fig_mem_dist.update_layout(height=300, margin=dict(l=0,r=0,t=40,b=0),
                                    paper_bgcolor="white", showlegend=False)
        st.plotly_chart(fig_mem_dist, use_container_width=True)

    with g2:
        fig_pay_dist = px.pie(
            grade_pay, names="grade", values="payment_pct",
            color="grade",
            color_discrete_map=GRADE_COLORS,
            title="등급별 매출 기여도(%)",
        )
        fig_pay_dist.update_traces(textinfo="label+percent", hole=0.4)
        fig_pay_dist.update_layout(height=300, margin=dict(l=0,r=0,t=40,b=0),
                                    paper_bgcolor="white", showlegend=False)
        st.plotly_chart(fig_pay_dist, use_container_width=True)

    with g3:
        fig_avg = px.bar(
            grade_pay, x="grade", y="avg_payment",
            color="grade",
            color_discrete_map=GRADE_COLORS,
            text="avg_payment",
            title="등급별 평균 객단가(원)",
        )
        fig_avg.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_avg.update_layout(height=300, margin=dict(l=0,r=0,t=40,b=0),
                               paper_bgcolor="white", plot_bgcolor="white",
                               showlegend=False, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_avg, use_container_width=True)

    # ── 등급별 구매 금액 박스플롯 ──────────
    st.markdown('<div class="section-header">📦 등급별 구매 금액 분포</div>', unsafe_allow_html=True)
    mem_ord_g = mem_orders.copy()
    mem_ord_g["grade"] = pd.Categorical(mem_ord_g["grade"], categories=GRADE_ORDER, ordered=True)
    fig_box = px.box(
        mem_ord_g.sort_values("grade"),
        x="grade", y="payment_amount",
        color="grade",
        color_discrete_map=GRADE_COLORS,
        points="outliers",
    )
    fig_box.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                           paper_bgcolor="white", plot_bgcolor="white",
                           showlegend=False, xaxis_title="등급", yaxis_title="결제금액(원)")
    st.plotly_chart(fig_box, use_container_width=True)

    # ── 등급 전환 매트릭스 ─────────────────
    st.markdown('<div class="section-header">🔄 등급 전환 추이 (이전 등급 → 현재 등급)</div>', unsafe_allow_html=True)
    trans = df_members.groupby(["prev_grade", "grade"]).size().reset_index(name="count")
    pivot = trans.pivot(index="prev_grade", columns="grade", values="count").fillna(0)
    pivot = pivot.reindex(index=GRADE_ORDER, columns=GRADE_ORDER, fill_value=0)
    fig_heat = px.imshow(
        pivot,
        color_continuous_scale=[[0,"#F8FAFC"],[0.5,"#93C5FD"],[1,"#1E3A8A"]],
        text_auto=True,
        aspect="auto",
    )
    fig_heat.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0),
                            paper_bgcolor="white",
                            xaxis_title="현재 등급", yaxis_title="이전 등급")
    st.plotly_chart(fig_heat, use_container_width=True)

    # ── 재구매 주기 & 빈도 ─────────────────
    st.markdown('<div class="section-header">🔁 등급별 재구매 주기 & 빈도</div>', unsafe_allow_html=True)
    repurchase = df_members.copy()
    repurchase["avg_days_between_orders"] = np.where(
        repurchase["total_orders"] > 1,
        (datetime(2024,12,31) - repurchase["join_date"]).dt.days / repurchase["total_orders"],
        np.nan
    )
    rep_summary = repurchase.groupby("grade").agg(
        avg_orders=("total_orders","mean"),
        avg_cycle=("avg_days_between_orders","mean"),
    ).reset_index()
    rep_summary["grade"] = pd.Categorical(rep_summary["grade"], categories=GRADE_ORDER, ordered=True)
    rep_summary = rep_summary.sort_values("grade")

    r1, r2 = st.columns(2)
    with r1:
        fig_freq = px.bar(rep_summary, x="grade", y="avg_orders",
                           color="grade", color_discrete_map=GRADE_COLORS,
                           text="avg_orders", title="등급별 평균 주문 횟수")
        fig_freq.update_traces(texttemplate="%{text:.1f}회", textposition="outside")
        fig_freq.update_layout(height=280, margin=dict(l=0,r=0,t=40,b=0),
                                paper_bgcolor="white", plot_bgcolor="white",
                                showlegend=False, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_freq, use_container_width=True)
    with r2:
        fig_cyc = px.bar(rep_summary, x="grade", y="avg_cycle",
                          color="grade", color_discrete_map=GRADE_COLORS,
                          text="avg_cycle", title="등급별 평균 재구매 주기(일)")
        fig_cyc.update_traces(texttemplate="%{text:.0f}일", textposition="outside")
        fig_cyc.update_layout(height=280, margin=dict(l=0,r=0,t=40,b=0),
                               paper_bgcolor="white", plot_bgcolor="white",
                               showlegend=False, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_cyc, use_container_width=True)


# ╔══════════════════════════════════════════╗
# ║  TAB 3 – 적립금 & 락인 전략               ║
# ╚══════════════════════════════════════════╝
with tab3:
    st.markdown("### 💰 적립금 & 락인(Lock-in) 전략 분석")

    # ── 포인트 사용자 vs 미사용자 객단가 비교
    st.markdown('<div class="section-header">⚖️ 포인트 사용 여부별 평균 객단가 비교</div>', unsafe_allow_html=True)

    mem_ord = df_orders[df_orders["member_type"] == "회원"].copy()
    mem_ord["point_used"] = mem_ord["used_point"] > 0
    pt_compare = mem_ord.groupby("point_used")["payment_amount"].agg(["mean","count"]).reset_index()
    pt_compare["label"] = pt_compare["point_used"].map({True: "포인트 사용", False: "포인트 미사용"})
    pt_compare.columns = ["point_used","avg_payment","order_count","label"]

    c1, c2 = st.columns([2, 3])
    with c1:
        for _, row in pt_compare.iterrows():
            accent = "#4F6AF6" if row["point_used"] else "#A9B4D6"
            st.markdown(kpi_card(
                row["label"],
                fmt_krw(int(row["avg_payment"])),
                f'<span class="kpi-delta">주문 건수: {int(row["order_count"]):,}건</span>',
                accent
            ), unsafe_allow_html=True)

        # 리프트 효과
        if len(pt_compare) == 2:
            use_avg  = pt_compare.loc[pt_compare["point_used"]==True,  "avg_payment"].values[0]
            no_avg   = pt_compare.loc[pt_compare["point_used"]==False, "avg_payment"].values[0]
            lift_pct = (use_avg - no_avg) / no_avg * 100
            st.info(f"💡 포인트 사용 시 객단가 **{lift_pct:.1f}%** 높음 → 적립금 활성화 정책 효과 확인됨")

    with c2:
        fig_pt = px.bar(
            pt_compare, x="label", y="avg_payment",
            color="label",
            color_discrete_sequence=["#4F6AF6","#A9B4D6"],
            text="avg_payment",
        )
        fig_pt.update_traces(texttemplate="%{text:,.0f}원", textposition="outside")
        fig_pt.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                              paper_bgcolor="white", plot_bgcolor="white",
                              showlegend=False, xaxis_title="", yaxis_title="평균 객단가(원)")
        st.plotly_chart(fig_pt, use_container_width=True)

    # ── 미사용 포인트 보유자 분석 ────────────
    st.markdown('<div class="section-header">😴 1,000원 이상 포인트 보유 & 1년 미구매 회원</div>', unsafe_allow_html=True)

    cutoff = datetime.now() - timedelta(days=365)
    sleepers = df_members[
        (df_members["point_balance"] >= 1000) &
        (df_members["last_order_date"] <= cutoff)
    ].copy()
    sleepers["dormant_days"] = (datetime.now() - sleepers["last_order_date"]).dt.days
    sleepers_by_grade = sleepers.groupby("grade").agg(
        count=("member_id","count"),
        avg_point=("point_balance","mean"),
        total_point=("point_balance","sum"),
    ).reset_index()
    sleepers_by_grade["grade"] = pd.Categorical(sleepers_by_grade["grade"], categories=GRADE_ORDER, ordered=True)
    sleepers_by_grade = sleepers_by_grade.sort_values("grade")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(kpi_card(
            "미사용 잠재 이탈 회원",
            f"{len(sleepers):,}명",
            f'<span class="kpi-delta down">전체 회원의 {len(sleepers)/len(df_members)*100:.1f}%</span>',
            "#EF4444"
        ), unsafe_allow_html=True)
    with s2:
        st.markdown(kpi_card(
            "묶인 포인트 총합",
            fmt_krw(int(sleepers["point_balance"].sum())),
            '<span class="kpi-delta">재활성화 시 매출 전환 가능</span>',
            "#F97316"
        ), unsafe_allow_html=True)
    with s3:
        st.markdown(kpi_card(
            "평균 미활동 기간",
            f"{int(sleepers['dormant_days'].mean())}일",
            "",
            "#A9B4D6"
        ), unsafe_allow_html=True)

    sl1, sl2 = st.columns([3, 2])
    with sl1:
        fig_sl = px.bar(
            sleepers_by_grade, x="grade", y="count",
            color="grade", color_discrete_map=GRADE_COLORS,
            text="count", title="등급별 잠재 이탈 회원 수"
        )
        fig_sl.update_traces(texttemplate="%{text:,}명", textposition="outside")
        fig_sl.update_layout(height=280, margin=dict(l=0,r=0,t=40,b=0),
                              paper_bgcolor="white", plot_bgcolor="white",
                              showlegend=False, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig_sl, use_container_width=True)

    with sl2:
        st.markdown("**등급별 잠재 이탈 회원 상세**")
        disp = sleepers_by_grade[["grade","count","avg_point","total_point"]].copy()
        disp.columns = ["등급","인원(명)","평균 보유 포인트","총 보유 포인트"]
        disp["평균 보유 포인트"] = disp["평균 보유 포인트"].map("{:,.0f}P".format)
        disp["총 보유 포인트"]   = disp["총 보유 포인트"].map("{:,.0f}P".format)
        st.dataframe(disp, hide_index=True, use_container_width=True)

    # ── 포인트 최소 사용 기준 준수 점검 ──────
    st.markdown('<div class="section-header">🔍 포인트 최소 사용 기준(1,000원) 준수 현황</div>', unsafe_allow_html=True)

    pt_used = mem_ord[mem_ord["used_point"] > 0].copy()
    below_min = pt_used[pt_used["used_point"] < 1000]
    above_min = pt_used[pt_used["used_point"] >= 1000]

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(kpi_card(
            "포인트 사용 총 건수",
            f"{len(pt_used):,}건",
            "", "#22C55E"
        ), unsafe_allow_html=True)
    with p2:
        ok_pct = len(above_min)/len(pt_used)*100 if len(pt_used) else 0
        st.markdown(kpi_card(
            "기준 준수 건수 (≥1,000P)",
            f"{len(above_min):,}건 ({ok_pct:.1f}%)",
            "", "#4F6AF6"
        ), unsafe_allow_html=True)
    with p3:
        fail_pct = len(below_min)/len(pt_used)*100 if len(pt_used) else 0
        color = "#EF4444" if fail_pct > 5 else "#22C55E"
        st.markdown(kpi_card(
            "기준 미달 건수 (<1,000P)",
            f"{len(below_min):,}건 ({fail_pct:.1f}%)",
            '<span class="kpi-delta down">정책 재점검 필요</span>' if fail_pct > 5 else "",
            color
        ), unsafe_allow_html=True)

    if fail_pct > 5:
        st.error(f"🚨 포인트 최소 사용 기준 미달 건이 {fail_pct:.1f}%입니다. 시스템 설정을 재확인하세요.")
    else:
        st.success(f"✅ 포인트 최소 사용 기준 준수율 {ok_pct:.1f}% — 정상 운영 중입니다.")

    # 분포 히스토그램
    if len(pt_used) > 0:
        fig_hist = px.histogram(
            pt_used, x="used_point", nbins=40,
            color_discrete_sequence=["#4F6AF6"],
            title="포인트 사용 금액 분포",
        )
        fig_hist.add_vline(x=1000, line_dash="dash", line_color="#EF4444",
                           annotation_text="최소 기준 1,000P", annotation_position="top right")
        fig_hist.update_layout(height=260, margin=dict(l=0,r=0,t=40,b=0),
                                paper_bgcolor="white", plot_bgcolor="white",
                                xaxis_title="사용 포인트(원)", yaxis_title="건수")
        st.plotly_chart(fig_hist, use_container_width=True)


# ─────────────────────────────────────────
# 7. 하단 – CSV 컬럼 가이드
# ─────────────────────────────────────────
with st.expander("📋 필수 CSV 파일 컬럼 가이드 (카페24 데이터 추출 기준)"):
    st.markdown("""
### ① orders.csv – 주문 데이터
| 컬럼명 | 설명 | 예시값 |
|---|---|---|
| `order_id` | 주문번호 | ORD000001 |
| `order_date` | 주문일시 | 2024-03-15 |
| `member_type` | 회원/비회원 구분 | 회원 |
| `grade` | 회원 등급 | 골드 |
| `member_id` | 회원 ID (비회원=GUEST) | MEM0001 |
| `payment_amount` | 실 결제금액(원) | 85000 |
| `used_point` | 사용한 포인트(원) | 3000 |

### ② members.csv – 회원 데이터
| 컬럼명 | 설명 | 예시값 |
|---|---|---|
| `member_id` | 회원 ID | MEM0001 |
| `join_date` | 가입일 | 2022-05-10 |
| `grade` | 현재 등급 | 실버 |
| `prev_grade` | 이전 등급 | 일반 |
| `point_balance` | 현재 보유 포인트(원) | 12000 |
| `last_order_date` | 최근 주문일 | 2023-11-20 |
| `total_orders` | 총 주문 횟수 | 8 |
| `total_payment` | 누적 결제금액(원) | 650000 |

### ③ weekly_kpi.csv – 주간 집계 KPI
| 컬럼명 | 설명 | 예시값 |
|---|---|---|
| `week_start` | 주 시작일 | 2024-01-01 |
| `total_payment` | 총 결제금액(원) | 12000000 |
| `member_payment` | 회원 결제금액(원) | 11500000 |
| `non_member_payment` | 비회원 결제금액(원) | 500000 |
| `new_members` | 신규 가입자 수 | 142 |
| `avg_order_value` | 전체 평균 객단가(원) | 78000 |
| `member_avg_order` | 회원 평균 객단가(원) | 82000 |
""")
