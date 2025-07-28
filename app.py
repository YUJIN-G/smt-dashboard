import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

sheet_url = st.secrets["google_sheets"]["url"]

CSV_URL = sheet_url

# 🔁 새로고침 버튼
st.title("📦 매출/매입 요약 대시보드")
if st.button("🔄 새로고침"):
    st.cache_data.clear()

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL)

    # 날짜 컬럼 변환
    date_cols = ["선적일", "송금/입금예정일", "송금/입금일"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

    # 금액 숫자 변환
    money_cols = ["원화(송금/입금일)", "금액"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].replace('[^\d.-]', '', regex=True).astype(float)

    return df

df = load_data()

st.subheader("🧾 원본 데이터 (Google Sheets)")
st.dataframe(df, use_container_width=True)

# 요약 로직 함수 (기준일 지정 가능)
def make_summary(df, 기준="송금/입금일"):
    filtered = df[df["ORDER NO"].notnull() & (df["ORDER NO"].astype(str).str.strip() != "")]
    grouped = filtered.groupby("ORDER NO")

    summary = []

    for order_no, group in grouped:
        판매 = group[group["거래구분"] == "판매"]["원화(송금/입금일)"].sum()
        구매 = group[group["거래구분"] == "구매"]["원화(송금/입금일)"].sum()
        비용 = group[group["거래구분"] == "비용"]["원화(송금/입금일)"].sum()
        판매업체 = group[group["거래구분"] == "판매"]["업체명"].head(1).values[0] if not group[group["거래구분"] == "판매"].empty else ""
        구매업체 = group[group["거래구분"] == "구매"]["업체명"].head(1).values[0] if not group[group["거래구분"] == "구매"].empty else ""
        기준일 = pd.to_datetime(group[기준], errors='coerce').min().date() if not group[기준].isnull().all() else None
        매출총이익 = 판매 - 구매
        마진율 = (매출총이익 / 판매 * 100) if 판매 else None
        영업이익 = 매출총이익 - 비용
        영업이익율 = (영업이익 / 판매 * 100) if 판매 else None

        summary.append({
            "ORDER NO": order_no,
            기준: 기준일,
            "판매업체": 판매업체,
            "구매업체": 구매업체,
            "총 판매가": 판매,
            "총 구매가": 구매,
            "총 비용": 비용,
            "매출총이익": 매출총이익,
            "마진율(%)": round(마진율, 2) if 마진율 is not None else None,
            "영업이익": 영업이익,
            "영업이익 비율(%)": round(영업이익율, 2) if 영업이익율 is not None else None,
        })

    df_summary = pd.DataFrame(summary)

    # 금액 형식 적용
    money_format_cols = ["총 판매가", "총 구매가", "총 비용", "매출총이익", "영업이익"]
    for col in money_format_cols:
        if col in df_summary.columns:
            df_summary[col] = df_summary[col].map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")

    return df_summary

# 🔀 기준별 탭 전환
tab1, tab2 = st.tabs(["📅 송금/입금일 기준", "🚢 선적일 기준"])

with tab1:
    st.subheader("📊 요약표 (송금/입금일 기준)")
    st.dataframe(make_summary(df, 기준="송금/입금일"), use_container_width=True)

with tab2:
    st.subheader("📊 요약표 (선적일 기준)")
    st.dataframe(make_summary(df, 기준="선적일"), use_container_width=True)
