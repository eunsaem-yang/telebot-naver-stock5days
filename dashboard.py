"""
Streamlit 대시보드: 텔레그램 push 대신, 사용자가 원할 때 웹페이지를 열어 확인하는 Pull 방식.
watchlist.csv·네이버 API·Turso DB(load_price_history)를 notify_stock_price.py와 그대로
공유해서 쓴다 — push(텔레그램)와 pull(대시보드) 두 경로가 동일한 데이터·저장소를 바라보므로
어느 쪽으로 확인해도 같은 내용을 본다.
"""
import os
import streamlit as st

# Streamlit Community Cloud의 Secrets는 st.secrets로 들어오는데, stock_utils.py는 로컬 .env와
# 동일하게 os.environ만 읽으므로 여기서 미리 os.environ에 반영해준다. 반드시 stock_utils import
# 이전에 실행해야 한다 — stock_utils가 모듈 로드 시점에 환경변수를 읽기 때문이다.
try:
    for key, value in st.secrets.items():
        os.environ.setdefault(key, str(value))
except Exception:
    pass  # secrets.toml이 없는 로컬 실행 등에서는 조용히 건너뛴다 (.env로 대체됨)

from stock_utils import (
    read_watchlist,
    load_price_history,
    fetch_naver_current_price,
    fetch_naver_intraday_minutes,
    build_price_chart,
    describe_price_trend,
)

st.set_page_config(page_title="관심종목 대시보드", page_icon="📈")
st.title("📈 관심종목 현재가 대시보드")

if st.button("🔄 새로고침"):
    st.rerun()

codes = read_watchlist()
history = load_price_history()

for code in codes or []:
    current = fetch_naver_current_price(code)
    if current is None:
        st.warning(f"{code}: 현재가 조회 실패")
        continue

    daily_closes = history.get(code, [])
    intraday = fetch_naver_intraday_minutes(code)

    st.subheader(f"{current['name']} ({code})")
    st.metric(
        label=describe_price_trend(daily_closes, intraday),
        value=f"{current['price']:,}원",
        delta=f"{current['rate']}%",
    )

    chart_buffer = build_price_chart(
        code, current["name"], daily_closes, current["price"], intraday
    )
    st.image(chart_buffer)
