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
    """Secrets에서 액세스 토큰 직접 반환."""
    return st.secrets.get("CAFE24_ACCESS_TOKEN", "")


# ─────────────────────────────────────────
# 공통 API 요청 (페이지네이션 자동 처리)
# ─────────────────────────────────────────
def _cafe24_get(endpoint: str, params: dict = None) -> list:
    """
    카페24 REST API GET 요청 래퍼.
    limit/offset 페이지네이션을 자동으로 순회해 전체 데이터 반환.
    카페24 API offset 최대값(10,000) 초과 시 자동 종료.
    """
    mall_id = st.secrets["CAFE24_MALL_ID"]
    base_url = f"https://{mall_id}.cafe24api.com/api/v2"
    headers  = {
        "Authorization": f"Bearer {get_valid_token()}",
        "Content-Type":  "application/json",
        "X-Cafe24-Api-Version": "2026-03-01",
    }
    params = params or {}
    params.setdefault("limit", 100)

    MAX_OFFSET = 10000  # 카페24 API offset 최대값 (초과 시 422 오류)

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

        # offset 최대값 초과 시 종료 (카페24 422 오류 방지)
        if offset >= MAX_OFFSET:
            break

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
    raw = _cafe24_get("/admin/orders", params={
        "start_date": start_date,
        "end_date":   end_date,
    })
    if not raw:
        return pd.DataFrame()

    rows = []
    for o in raw:
        member_type = "비회원" if o.get("member_type") == "guest" else "회원"
        grade_no_map = {
            "1": "FAMILY",
            "2": "VVIP",
            "3": "VIP",
            "4": "GOLD",
            "5": "SILVER",
        }
        grade_no  = str(o.get("group_no_when_ordering", "1") or "1")
        grade_raw = grade_no_map.get(grade_no, "FAMILY") if member_type == "회원" else "-"

        pay_amt = o.get("payment_amount") or o.get("actual_price") or 0
        pt_amt  = o.get("points_spent_amount") or o.get("use_point") or 0

        rows.append({
            "order_id":       o.get("order_id"),
            "order_date":     pd.to_datetime(o.get("order_date")),
            "member_type":    member_type,
            "grade":          grade_raw,
            "member_id":      o.get("member_id", "GUEST"),
            "payment_amount": int(float(str(pay_amt).replace(",","") or 0)),
            "used_point":     int(float(str(pt_amt).replace(",","") or 0)),
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
    # 카페24 /admin/customers는 가입일 범위가 필수
    from datetime import datetime
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")  # 최근 5년
    raw = _cafe24_get("/admin/customers", params={
        "created_start_date": start,
        "created_end_date": end,
    })
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
            "prev_grade":      str(grade_m),
            "point_balance":   int(float(m.get("available_mileage", 0))),
            "last_order_date": pd.to_datetime(m.get("last_login_date")),
            "total_orders":    int(m.get("order_count", 0)),
            "total_payment":   int(float(m.get("total_order_amount", 0))),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────
# 주간 KPI 집계 (주문 DF에서 계산)
# ─────────────────────────────────────────
def build_weekly_kpi(df_orders: pd.DataFrame) -> pd.DataFrame:
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
