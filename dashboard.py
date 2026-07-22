"""
Streamlit 프로토타입: 텔레그램 push 대신, 사용자가 원할 때 웹페이지를 열어 확인하는 방식을
체험해보기 위한 가벼운 대시보드. price_history.json/네이버 API를 그대로 재사용하고, DB
연동 전 "Pull 방식이 실제로 어떤 느낌인지"만 빠르게 확인하는 용도라 아직 Turso는 붙이지 않았다.
"""
import streamlit as st

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
