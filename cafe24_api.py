"""
카페24 API 연동 모듈
- OAuth 2.0 액세스 토큰 발급 및 자동 갱신
- 주문 데이터 / 회원 데이터 / 회원 등급 fetch
- Streamlit session_state 캐시 활용
"""

import requests
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import time


# ─────────────────────────────────────────
# 카페24 OAuth 2.0 토큰 발급
# ─────────────────────────────────────────
def get_access_token(mall_id: str, client_id: str, client_secret: str, code: str) -> dict:
    """
    인증 코드(code)로 액세스 토큰 발급
    - 카페24 개발자센터 앱 등록 후 발급받은 client_id / client_secret 사용
    - Redirect URI 에서 code 파라미터 추출 후 이 함수에 전달
    """
    url = f"https://{mall_id}.cafe24api.com/api/v2/oauth/token"
    resp = requests.post(url, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  st.secrets["CAFE24_REDIRECT_URI"],
        "client_id":     client_id,
        "client_secret": client_secret,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(mall_id: str, client_id: str, client_secret: str, refresh_token: str) -> dict:
    """리프레시 토큰으로 액세스 토큰 갱신"""
    url = f"https://{mall_id}.cafe24api.com/api/v2/oauth/token"
    resp = requests.post(url, data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     client_id,
        "client_secret": client_secret,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_valid_token() -> str:
    """액세스 토큰 반환. 만료 시 리프레시 토큰으로 자동 갱신."""
    # 세션에 토큰 없으면 Secrets에서 초기화
    if "access_token" not in st.session_state:
        st.session_state["access_token"]  = st.secrets.get("CAFE24_ACCESS_TOKEN", "")
        st.session_state["refresh_token"] = st.secrets.get("CAFE24_REFRESH_TOKEN", "")

    # 리프레시 토큰으로 새 액세스 토큰 발급 시도
    try:
        mall_id       = st.secrets["CAFE24_MALL_ID"]
        client_id     = st.secrets["CAFE24_CLIENT_ID"]
        client_secret = st.secrets["CAFE24_CLIENT_SECRET"]
        refresh_token = st.session_state.get("refresh_token", st.secrets.get("CAFE24_REFRESH_TOKEN", ""))

        import base64 as _b64
        pair    = f"{client_id}:{client_secret}".encode()
        b64auth = _b64.b64encode(pair).decode()

        resp = requests.post(
            f"https://{mall_id}.cafe24api.com/api/v2/oauth/token",
            headers={
                "Authorization": f"Basic {b64auth}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data=f"grant_type=refresh_token&refresh_token={refresh_token}",
            timeout=10,
        )
        if resp.status_code == 200:
            token_data = resp.json()
            st.session_state["access_token"]  = token_data.get("access_token", st.session_state["access_token"])
            st.session_state["refresh_token"] = token_data.get("refresh_token", refresh_token)
    except Exception:
        pass

    return st.session_state.get("access_token", "")


# ─────────────────────────────────────────
# 공통 API 요청 (페이지네이션 자동 처리)
# ─────────────────────────────────────────
def _cafe24_get(endpoint: str, params: dict = None) -> list:
    """
    카페24 REST API GET 요청 래퍼.
    limit/offset 페이지네이션을 자동으로 순회해 전체 데이터 반환.
    """
    mall_id = st.secrets["CAFE24_MALL_ID"]
    base_url = f"https://{mall_id}.cafe24api.com/api/v2"
    headers  = {
        "Authorization": f"Bearer {get_valid_token()}",
        "Content-Type":  "application/json",
        "X-Cafe24-Api-Version": "2024-06-01",
    }
    params = params or {}
    params.setdefault("limit", 100)

    all_items, offset = [], 0
    while True:
        params["offset"] = offset
        resp = requests.get(f"{base_url}{endpoint}", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # 응답 최상위 키 자동 탐지 (orders / members / customer_grade 등)
        key = next((k for k in data if isinstance(data[k], list)), None)
        if not key:
            break
        batch = data[key]
        all_items.extend(batch)

        # 다음 페이지 없으면 종료
        if len(batch) < params["limit"]:
            break
        offset += params["limit"]
        time.sleep(0.2)   # API 레이트 리밋 대비

    return all_items


# ─────────────────────────────────────────
# 주문 데이터 fetch
# ─────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="카페24 주문 데이터 불러오는 중...")
def fetch_orders(start_date: str, end_date: str) -> pd.DataFrame:
    """
    주문 내역 조회 → orders.csv 와 동일한 컬럼 구조로 반환
    start_date / end_date : "YYYY-MM-DD"
    필요 권한 스코프: mall.read_order
    """
    raw = _cafe24_get("/orders", params={
        "start_date": start_date,
        "end_date":   end_date,
    })
    if not raw:
        return pd.DataFrame()

    rows = []
    for o in raw:
        member_type = "비회원" if o.get("member_type") == "guest" else "회원"
        # 카페24 API 등급 필드명 여러 경우 시도
        grade_raw = (
            o.get("member_grade_name") or
            o.get("group_no_default") or
            o.get("member_group_no") or
            "FAMILY"
        ) if member_type == "회원" else "-"
        rows.append({
            "order_id":        o.get("order_id"),
            "order_date":      pd.to_datetime(o.get("order_date")),
            "member_type":     member_type,
            "grade":           str(grade_raw) if member_type == "회원" else "-",
            "member_id":       o.get("member_id", "GUEST"),
            "payment_amount":  int(float(o.get("actual_price", 0) or 0)),
            "used_point":      int(float(o.get("use_point", 0) or 0)),
            "_raw_keys":       list(o.keys()),  # 디버깅용
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 회원 데이터 fetch
# ─────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="카페24 회원 데이터 불러오는 중...")
def fetch_members() -> pd.DataFrame:
    """
    전체 회원 목록 조회 → members.csv 와 동일한 컬럼 구조로 반환
    필요 권한 스코프: mall.read_customer
    """
    raw = _cafe24_get("/customers", params={"member_type": "member"})
    if not raw:
        return pd.DataFrame()

    rows = []
    for m in raw:
        grade_m = (
            m.get("member_grade_name") or
            m.get("group_no_default") or
            "FAMILY"
        )
        rows.append({
            "member_id":       m.get("member_id"),
            "join_date":       pd.to_datetime(m.get("created_date")),
            "grade":           str(grade_m),
            "prev_grade":      str(grade_m),   # 전환 이력은 별도 API
            "point_balance":   int(float(m.get("available_mileage", 0))),
            "last_order_date": pd.to_datetime(m.get("last_login_date")),  # 주문일 대체
            "total_orders":    int(m.get("order_count", 0)),
            "total_payment":   int(float(m.get("total_order_amount", 0))),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 주간 KPI 집계 (주문 DF에서 계산)
# ─────────────────────────────────────────
def build_weekly_kpi(df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    fetch_orders() 결과로 weekly_kpi 테이블 생성
    (카페24 통계 API 대신 클라이언트 사이드 집계)
    """
    if df_orders.empty:
        return pd.DataFrame()

    df = df_orders.copy()
    df["week_start"] = df["order_date"].dt.to_period("W").apply(lambda p: p.start_time)

    weekly = df.groupby("week_start").apply(lambda g: pd.Series({
        "total_payment":       g["payment_amount"].sum(),
        "member_payment":      g.loc[g["member_type"]=="회원", "payment_amount"].sum(),
        "non_member_payment":  g.loc[g["member_type"]=="비회원","payment_amount"].sum(),
        "avg_order_value":     int(g["payment_amount"].mean()),
        "member_avg_order":    int(g.loc[g["member_type"]=="회원","payment_amount"].mean())
                               if (g["member_type"]=="회원").any() else 0,
    })).reset_index()

    # 신규 가입자는 members 데이터 필요 → 여기선 0으로 채움 (별도 merge)
    weekly["new_members"] = 0
    return weekly


# ─────────────────────────────────────────
# 신규 가입자 주간 집계 (회원 DF에서)
# ─────────────────────────────────────────
def build_weekly_new_members(df_members: pd.DataFrame) -> pd.DataFrame:
    df = df_members.copy()
    df["week_start"] = df["join_date"].dt.to_period("W").apply(lambda p: p.start_time)
    return df.groupby("week_start").size().reset_index(name="new_members")


# ─────────────────────────────────────────
# OAuth 인증 URL 생성 (최초 1회 브라우저 인증)
# ─────────────────────────────────────────
def get_auth_url() -> str:
    mall_id     = st.secrets.get("CAFE24_MALL_ID", "yourmall")
    client_id   = st.secrets.get("CAFE24_CLIENT_ID", "")
    redirect    = st.secrets.get("CAFE24_REDIRECT_URI", "")
    scopes      = "mall.read_order,mall.read_customer"
    return (
        f"https://{mall_id}.cafe24api.com/api/v2/oauth/authorize"
        f"?response_type=code&client_id={client_id}"
        f"&redirect_uri={redirect}&scope={scopes}"
    )
