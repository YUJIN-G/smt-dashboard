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

def highlight_type_cell(val):
    if val == "판매":
        return "background-color: rgba(173, 216, 230, 0.3)"  # 연파랑
    elif val == "비용":
        return "background-color: rgba(255, 255, 153, 0.3)"  # 연노랑
    elif val == "구매":
        return "background-color: rgba(255, 192, 203, 0.3)"  # 연분홍
    return ""


def filtered_order_table(df):
    import pandas as pd
    import streamlit as st

    # 대표 정보 추출
    rep_info = df[df["거래구분"] == "판매"].groupby("ORDER NO").agg({
        "업체명": "first",
        "선적일": "min"
    }).rename(columns={"업체명": "판매업체", "선적일": "대표선적일"}).dropna().reset_index()

    rep_info = rep_info.sort_values("대표선적일")

    # 드롭다운 라벨 생성
    rep_info["label"] = rep_info["판매업체"] + " " + rep_info["대표선적일"].astype(str)
    label_to_order = {"전체 보기": None}
    label_to_order.update(dict(zip(rep_info["label"], rep_info["ORDER NO"])))

    # 드롭다운 선택
    selected_label = st.selectbox("주문 선택", options=label_to_order.keys())
    selected_order_no = label_to_order[selected_label]

    # 필터링
    if selected_order_no is None:
        filtered_df = df.copy()
    else:
        filtered_df = df[df["ORDER NO"] == selected_order_no].copy()

    # 숫자 컬럼 변환 및 포맷
    for col in ["금액", "원화(선적일)", "원화(송금/입금일)"]:
        if col in filtered_df.columns:
            filtered_df[col] = pd.to_numeric(filtered_df[col], errors="coerce")

    # 컬럼명 변경
    filtered_df = filtered_df.rename(columns={
        "거래구분": "유형"
    })


    # 숫자 포맷 및 색상 스타일 적용
    styled_df = filtered_df.style \
        .format({
            "금액": "{:,.0f}",
            "원화(선적일)": "{:,.0f}",
            "원화(송금/입금일)": "{:,.0f}",
        }) \
        .set_properties(**{"text-align": "right"}) \
        .applymap(highlight_type_cell, subset=["유형"])

    st.dataframe(styled_df, use_container_width=True)


with st.expander("📋 매입/매출 내역 ", expanded=False):
    filtered_order_table(df)

