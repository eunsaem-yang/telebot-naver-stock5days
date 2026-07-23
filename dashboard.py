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
    read_watchlist_names,
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
watchlist_names = read_watchlist_names()

for code in codes or []:
    current = fetch_naver_current_price(code)
    daily_closes = history.get(code, [])

    if current is None:
        # 네이버 API 조회 실패(예: Streamlit Cloud → 네이버 도메인 연결 차단, ROADMAP.md
        # "알려진 이슈" 참고) 시에도 DB에 저장된 과거 종가가 있으면 그거라도 보여준다.
        # 종목명은 원래 네이버 API 응답에서만 오므로, 조회 실패 시엔 watchlist.csv의
        # name 컬럼에서 찾고 그마저 없으면 종목코드를 그대로 쓴다.
        name = watchlist_names.get(code, code)
        if not daily_closes:
            st.warning(f"{name}({code}): 현재가 조회 실패 (저장된 과거 종가도 없음)")
            continue
        st.warning(f"{name}({code}): 현재가 조회 실패 — 저장된 과거 종가만 표시합니다")
        st.subheader(f"{name} ({code})")
        chart_buffer = build_price_chart(code, name, daily_closes)
        st.image(chart_buffer)
        continue

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
