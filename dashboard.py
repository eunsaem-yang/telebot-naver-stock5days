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
    # st.secrets.items(): Streamlit Cloud의 Secrets 설정을 (키, 값) 쌍으로 순회한다.
    # os.environ.setdefault(key, value): 이미 그 이름의 환경변수가 있으면 그대로 두고,
    # 없을 때만 새로 설정한다 — 로컬 .env로 이미 설정된 값을 덮어쓰지 않기 위해서다.
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

# st.set_page_config(): 브라우저 탭 제목/아이콘 등 페이지 전체 설정. 스크립트에서 다른
# st.* 호출보다 먼저 딱 한 번만 호출해야 한다.
st.set_page_config(page_title="관심종목 대시보드", page_icon="📈")
st.title("📈 관심종목 현재가 대시보드")  # 화면 맨 위 큰 제목.

# st.button(): 버튼을 화면에 그리고, "이번 실행에서 방금 눌렸는지"를 True/False로 돌려준다.
# 중요한 건 Streamlit의 실행 모델이다 — 이 파일은 한 번 실행되고 끝나는 게 아니라, 페이지를
# 새로고침하거나 버튼을 누르는 등 뭔가와 상호작용할 때마다 맨 위(import문)부터 이 파일 전체가
# 다시 통째로 실행된다. 즉 아래의 "종목 조회 → 그래프 생성" 코드도 버튼을 누를 때마다 매번
# 새로 실행되어 최신 데이터를 다시 가져온다. st.rerun()은 "지금 즉시 이 스크립트를 처음부터
# 다시 실행해줘"라고 명시적으로 요청하는 것이다(안 불러도 상호작용 자체가 재실행을 유발하지만,
# 버튼을 누른 즉시 화면을 깔끔하게 다시 그리기 위해 명시적으로 호출했다).
if st.button("🔄 새로고침"):
    st.rerun()

codes = read_watchlist()
history = load_price_history()
watchlist_names = read_watchlist_names()

# codes or []: read_watchlist()가 실패해서 None을 반환해도, None을 순회하려다 에러가 나는 대신
# 빈 리스트로 대체해 그냥 "표시할 종목이 없다"는 상태로 조용히 넘어간다.
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

    st.subheader(f"{current['name']} ({code})")  # 종목명(코드) 형태의 소제목.
    # st.metric(): 라벨 + 큰 숫자(value) + 증감(delta)을 카드 형태로 보여주는 위젯.
    # delta 값이 양수/음수면 Streamlit이 자동으로 초록/빨강 화살표까지 붙여준다.
    st.metric(
        label=describe_price_trend(daily_closes, intraday),
        value=f"{current['price']:,}원",
        delta=f"{current['rate']}%",
    )

    chart_buffer = build_price_chart(
        code, current["name"], daily_closes, current["price"], intraday
    )
    st.image(chart_buffer)  # build_price_chart()가 만든 PNG 바이트 버퍼를 그대로 화면에 그린다.
