from collections import deque
import streamlit as st
import pandas as pd
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


st.set_page_config(layout="wide")

sheet_url = st.secrets["google_sheets"]["url"]
CSV_URL = sheet_url
FX_USD_CSV_URL = st.secrets["google_sheets"]["fx_usd_url"]  
FX_JPY_CSV_URL = st.secrets["google_sheets"]["fx_jpy_url"]

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


# 📊 요약 로직
def make_summary(df, 기준="송금/입금일"):
    금액컬럼 = "원화(선적일)" if 기준 == "선적일" else "원화(송금/입금일)"
    filtered = df[df["ORDER NO"].notnull() & (df["ORDER NO"].astype(str).str.strip() != "")]
    grouped = filtered.groupby("ORDER NO")

    summary = []

    for order_no, group in grouped:
        group[금액컬럼] = pd.to_numeric(group[금액컬럼], errors="coerce")  
        판매 = group[group["거래구분"] == "판매"][금액컬럼].sum()
        구매 = group[group["거래구분"] == "구매"][금액컬럼].sum()
        비용 = group[group["거래구분"] == "비용"][금액컬럼].sum()
        판매업체 = group[group["거래구분"] == "판매"]["업체명"].head(1).values[0] if not group[group["거래구분"] == "판매"].empty else ""
        구매업체 = group[group["거래구분"] == "구매"]["업체명"].head(1).values[0] if not group[group["거래구분"] == "구매"].empty else ""
        기준일 = pd.to_datetime(group[기준], errors='coerce').min().date() if not group[기준].isnull().all() else None
        선적일 = pd.to_datetime(group["선적일"], errors='coerce').min().date() if not group["선적일"].isnull().all() else None
        매출총이익 = 판매 - 구매
        마진율 = (매출총이익 / 판매 * 100) if 판매 else None
        영업이익 = 매출총이익 - 비용
        영업이익율 = (영업이익 / 판매 * 100) if 판매 else None

        summary.append({
            "ORDER NO": order_no,
            기준: 기준일,
            "선적일": 선적일,
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

# 🧾 비용 항목별 피벗
def make_cost_pivot(df):
    df_cost = df[df["거래구분"] == "비용"].copy()
    df_cost["원화(송금/입금일)"] = df_cost["원화(송금/입금일)"].fillna(0)

    pivot = pd.pivot_table(
        df_cost,
        index=["ORDER NO", "업체명"],
        columns="항목",
        values="원화(송금/입금일)",
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    # 모든 값이 0인 항목 컬럼 제거
    항목컬럼 = [col for col in pivot.columns if col not in ["ORDER NO", "업체명"]]
    유효항목 = [col for col in 항목컬럼 if pivot[col].sum() != 0]
    pivot = pivot[["ORDER NO", "업체명"] + 유효항목]

    pivot["금액 합계"] = pivot[유효항목].sum(axis=1)

    # 숫자 포맷 적용
    for col in 유효항목 + ["금액 합계"]:
        pivot[col] = pivot[col].map(lambda x: f"{x:,.0f}")

    # 정렬
    pivot = pivot.sort_values(by=["업체명", "ORDER NO"]).reset_index(drop=True)
    return pivot

    
    
# 2️⃣ 요약표 탭
with st.expander("📊 요약표 및 비용 항목별 분석", expanded=False):
    tab1, tab2, tab3 = st.tabs([
        "📅 송금/입금일 기준",
        "🚢 선적일 기준",
        "🧾 비용 항목 요약"
    ])

    with tab1:
        st.dataframe(make_summary(df, 기준="송금/입금일"), use_container_width=True)

    with tab2:
        st.dataframe(make_summary(df, 기준="선적일"), use_container_width=True)

    with tab3:
        st.dataframe(make_cost_pivot(df), use_container_width=True)





def render_monthly_summary(df):
    # 📌 기준일 선택
    col1, col2, col3 = st.columns([1.2, 2, 2])
    with col1:
        date_basis = st.selectbox("기준일자", ["선적일", "송금/입금일"])
    with col2:
        start_date = st.date_input("시작일자", value=datetime(2025, 1, 1))
    with col3:
        end_date = st.date_input("종료일자", value=datetime.today())

    기준일자 = date_basis

    # 🔍 거래 필터 및 기준월 파생 (조회기간 포함)
    df_filtered = df[
        (df["거래구분"].isin(["판매", "비용", "구매"])) &
        (df[기준일자].notnull()) &
        (df[기준일자] >= start_date) &
        (df[기준일자] <= end_date)
    ].copy()

    df_filtered["기준월"] = pd.to_datetime(df_filtered[기준일자]).dt.to_period("M").astype(str)


    # 📊 월별 집계
    summary = df_filtered.groupby(["기준월", "거래구분"])["원화(송금/입금일)"].sum().unstack(fill_value=0).reset_index()
    summary = summary.rename(columns={"판매": "총 매출", "구매": "총 구매", "비용": "총 비용"})
    summary["영업이익"] = summary["총 매출"] - summary["총 구매"] - summary["총 비용"]


    # 숫자 포맷 전의 summary 재사용
    numeric_summary = df_filtered.groupby(["기준월", "거래구분"])["원화(송금/입금일)"].sum().unstack(fill_value=0).reset_index()
    numeric_summary["영업이익"] = numeric_summary["판매"] - numeric_summary["구매"] - numeric_summary["비용"]
    numeric_summary = numeric_summary.rename(columns={"판매": "총 매출", "구매": "총 구매", "비용": "총 비용"})

    # 💰 포맷 적용
    for col in ["총 매출", "총 구매", "총 비용", "영업이익"]:
        summary[col] = summary[col].map(lambda x: f"{x:,.0f}원")

    # ✅ 표 출력
    st.dataframe(summary, use_container_width=True)


    # 월을 인덱스로 설정
    chart_df = numeric_summary.set_index("기준월")[["총 매출", "영업이익"]]

    # 📊 스트림릿 내장 바 차트
    st.bar_chart(chart_df)
    


# 3️⃣ 월별 매출 및 영업이익 추이
with st.expander("📈 월별 매출 및 영업이익 추이", expanded=False):
    render_monthly_summary(df)
    
    
    
    
    
# 외환 차손 계산    

@st.cache_data
def load_fx_left_table():
    """두번째 탭(좌측 열: 입출금/내용/입금/출금/환율/원화/외화잔액) 불러오기"""
    fx = pd.read_csv(FX_USD_CSV_URL)
    fx.columns = fx.columns.str.strip()
    # Unnamed 제거
    fx = fx.loc[:, ~fx.columns.str.startswith("Unnamed")]
    # 날짜
    if "입출금" in fx.columns:
        fx["입출금"] = pd.to_datetime(fx["입출금"], errors="coerce")
    # 숫자(콤마/하이픈 제거)
    for col in ["입금", "출금", "환율"]:
        if col in fx.columns:
            fx[col] = fx[col].astype(str).str.replace(r"[^\d\.-]", "", regex=True).replace({"": "0", "-": "0"}).astype(float)
    # 설명 컬럼 표준화
    if "내용" not in fx.columns:
        fx["내용"] = ""
    return fx

from collections import deque
from decimal import Decimal, ROUND_HALF_UP

def _to_dec(x):
    if pd.isna(x): return Decimal("0")
    s = str(x).strip().replace(",", "")
    if s in ["", "-", "–"]: return Decimal("0")
    return Decimal(s)

def _round_krw(x: Decimal) -> int:
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def compute_fx_fifo_kor(fx: pd.DataFrame) -> pd.DataFrame:
    """
    입력: 컬럼 = 입출금(날짜), 내용, 입금, 출금, 환율  (좌측 표)
    규칙: 선입선출(FIFO), 같은 날 입금분으로 같은 날 출금된 금액은 환차손익 0
    출력: 거래별 환차손익 테이블
    """
    df = fx.copy()
    df = df.rename(columns={"입출금":"date", "내용":"desc", "입금":"deposit", "출금":"withdraw", "환율":"rate"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["deposit","withdraw","rate"]:
        df[c] = df[c].map(_to_dec)

    df = df.sort_values(["date"]).reset_index(drop=True)

    lots = deque()   # 보유 로트: {amount, rate, date, desc}
    out = []

    for _, r in df.iterrows():
        date, dep, wdr, rate, desc = r["date"], r["deposit"], r["withdraw"], r["rate"], r["desc"]

        if dep > 0:
            lots.append({"amount": dep, "rate": rate, "date": date, "desc": desc})
            out.append({
                "date": date.date(), "desc": desc, "type":"입금",
                "usd": float(dep), "book_rate": float(rate),
                "book_krw": _round_krw(dep*rate),
                "fifo_cost_krw": _round_krw(dep*rate),
                "fx_gain_krw": 0, "fifo_breakdown":""
            })
            continue

        if wdr > 0:
            remain = Decimal(wdr)
            book_krw = Decimal("0"); cost_krw = Decimal("0")
            breakdown = []

            # 1) 같은 날 입금분 우선 소진 (환차손익 0)
            i = 0
            while remain > 0 and i < len(lots):
                lot = lots[i]
                if lot["date"].date() != date.date():
                    i += 1; continue
                use = min(lot["amount"], remain)
                book_krw += use * rate
                cost_krw += use * rate      # 같은 날 매칭 → 0
                breakdown.append(f"{use:.2f}@same-day")
                lot["amount"] -= use; remain -= use
                if lot["amount"] == 0: del lots[i]
                else: i += 1

            # 2) 잔여는 순수 FIFO
            i = 0
            while remain > 0 and i < len(lots):
                lot = lots[i]
                use = min(lot["amount"], remain)
                book_krw += use * rate
                cost_krw += use * lot["rate"]
                breakdown.append(f"{use:.2f}@{float(lot['rate']):.2f}({lot['date'].date()})")
                lot["amount"] -= use; remain -= use
                if lot["amount"] == 0: del lots[i]
                else: i += 1

            out.append({
                "date": date.date(), "desc": desc, "type":"출금",
                "usd": float(wdr), "book_rate": float(rate),
                "book_krw": _round_krw(wdr*rate),
                "fifo_cost_krw": _round_krw(cost_krw),
                "fx_gain_krw": _round_krw(book_krw - cost_krw),
                "fifo_breakdown": " + ".join(breakdown)
            })

    res = pd.DataFrame(out)
    if not res.empty:
        res["cum_fx_gain_krw"] = res["fx_gain_krw"].cumsum()
    return res

# 💱 환차손익(FIFO) 계산 테이블  🔹 추가 블록
with st.expander("💱 환차손익(FIFO) 계산 테이블", expanded=False):
    fx_left = load_fx_left_table()
    st.caption("※ 두번째 탭(좌측 표: 입출금/내용/입금/출금/환율/원화/외화잔액)을 불러와 FIFO로 환차손익을 계산합니다.")
    fifo_table = compute_fx_fifo_kor(fx_left)


    if fifo_table.empty:
        st.info("두번째 탭에 데이터가 없거나 컬럼명이 맞지 않습니다. (필수: 입출금, 내용, 입금, 출금, 환율)")
    else:
        # 🔹 1) 컬럼 한글명으로 변경
        col_map = {
            "date": "일자",
            "desc": "내용",
            "type": "구분",                 # 입금/출금
            "usd": "금액(USD)",
            "book_rate": "적용환율",
            "book_krw": "장부원화",
            "fifo_cost_krw": "FIFO원가",
            "fx_gain_krw": "환차익(원)",
            "fifo_breakdown": "차감내역(FIFO)",
            "cum_fx_gain_krw": "누적환차익(원)"
        }
        fifo_table = fifo_table.rename(columns=col_map)

        # 🔹 2) 컬럼 순서 통일(원하면)
        display_cols = [
            "일자","내용","구분","금액(USD)","적용환율",
            "장부원화","FIFO원가","환차익(원)","누적환차익(원)","차감내역(FIFO)"
        ]
        # 존재하는 컬럼만 유지 (안전장치)
        display_cols = [c for c in display_cols if c in fifo_table.columns]
        show = fifo_table[display_cols].copy()

        # 🔹 3) 숫자 포맷
        for c in ["금액(USD)","적용환율","장부원화","FIFO원가","환차익(원)","누적환차익(원)"]:
            if c in show.columns:
                show[c] = pd.to_numeric(show[c], errors="coerce")
        # 쉼표 포맷(원화/환차익 계열)
        for c in ["장부원화","FIFO원가","환차익(원)","누적환차익(원)"]:
            if c in show.columns:
                show[c] = show[c].map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
        # 달러/환율은 소수 표시 원하면 아래 유지, 아니면 주석 처리
        if "금액(USD)" in show.columns:
            show["금액(USD)"] = show["금액(USD)"].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")
        if "적용환율" in show.columns:
            show["적용환율"] = show["적용환율"].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")

        st.dataframe(show, use_container_width=True)

        # 🔹 4) 총 환차손익 metric (원본 컬럼명 기준으로 계산)
        total_gain = int(fifo_table["환차익(원)"].str.replace(',', '', regex=True)
                         .astype(float).sum()
                         if fifo_table["환차익(원)"].dtype == object
                         else fifo_table["환차익(원)"].sum())
        st.metric("총 환차손익(원)", f"{total_gain:,.0f}")

    