import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")

sheet_url = st.secrets["google_sheets"]["url"]
CSV_URL = sheet_url

# 🔁 새로고침 버튼
st.title("매출/매입 요약 대시보드")
if st.button("새로고침"):
    st.cache_data.clear()

# st.write("🔍 원본 데이터")
# df_ = pd.read_csv(CSV_URL)
# st.dataframe(df_)

@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL)


    df.columns = df.columns.str.strip()
    # Unnamed 컬럼 제거
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    # 날짜 변환
    date_cols = ["선적일", "송금/입금예정일", "송금/입금일"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

    # 금액 숫자 변환
    money_cols = ["원화(송금/입금일)", "원화(선적일)", "금액"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].replace('[^\d.-]', '', regex=True).astype(float)

    return df


df = load_data()
