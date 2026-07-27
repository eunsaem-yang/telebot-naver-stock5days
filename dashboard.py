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
st.subheader("관심종목 현재가 대시보드")  # 화면 맨 위 제목. st.title()(h1)보다 두 단계 작은 크기.

# st.empty(): 지금은 빈 자리만 잡아두고, 나중에(종목 루프에서 첫 종목 데이터를 확인한 뒤)
# .markdown()으로 내용을 채워 넣을 수 있는 자리표시자. 종목마다 반복되던 추이 설명 문구를
# 제목 바로 아래에 한 번만 표시하기 위해 쓴다.
trend_placeholder = st.empty()

# st.cache_data: 이 함수의 반환값을 ttl(유효 시간) 동안 기억해뒀다가, 같은 인자로 다시 호출되면
# 실제로 다시 실행하지 않고 기억해둔 값을 즉시 돌려준다. Streamlit은 상호작용마다 스크립트
# 전체를 처음부터 다시 실행하는데, 캐싱이 없으면 그때마다 네이버 API·Turso DB를 매번 다시
# 호출하게 된다 — 현재가/분봉은 자주 바뀌니 짧게(1분), DB 히스토리는 하루 1회만 바뀌니
# 조금 더 길게(5분) 기억해둔다.
@st.cache_data(ttl="1m")
def _cached_current_price(code):
    return fetch_naver_current_price(code)


@st.cache_data(ttl="1m")
def _cached_intraday(code):
    return fetch_naver_intraday_minutes(code)


@st.cache_data(ttl="5m")
def _cached_history():
    return load_price_history()


# st.button(): 버튼을 화면에 그리고, "이번 실행에서 방금 눌렸는지"를 True/False로 돌려준다.
# 중요한 건 Streamlit의 실행 모델이다 — 이 파일은 한 번 실행되고 끝나는 게 아니라, 페이지를
# 새로고침하거나 버튼을 누르는 등 뭔가와 상호작용할 때마다 맨 위(import문)부터 이 파일 전체가
# 다시 통째로 실행된다. st.rerun()은 "지금 즉시 이 스크립트를 처음부터 다시 실행해줘"라고
# 명시적으로 요청하는 것이다. 다만 캐싱을 넣은 뒤로는 재실행만으로는 ttl이 지나기 전까지
# 기억해둔 값을 그대로 쓰게 되므로, 버튼을 눌렀을 때만큼은 "진짜 최신 값"을 보여주기 위해
# .clear()로 캐시를 직접 비운 뒤 재실행한다.
# st.columns([5, 1]): 가로 폭을 5:1 비율의 두 칸으로 나눈다. 첫 칸은 비워두고 버튼을 좁은
# 두 번째 칸에 넣으면, 버튼이 그 칸 안에 꽉 차게 그려지면서 결과적으로 화면 오른쪽 끝으로
# 밀려나 보인다.
_, button_col = st.columns([5, 1])
with button_col:
    if st.button("🔄 새로고침"):
        _cached_current_price.clear()
        _cached_intraday.clear()
        _cached_history.clear()
        st.rerun()

codes = read_watchlist()
history = _cached_history()
watchlist_names = read_watchlist_names()

trend_shown = False  # 추이 설명 문구를 이미 한 번 표시했는지 (첫 성공한 종목에서만 채운다).

# codes or []: read_watchlist()가 실패해서 None을 반환해도, None을 순회하려다 에러가 나는 대신
# 빈 리스트로 대체해 그냥 "표시할 종목이 없다"는 상태로 조용히 넘어간다.
for code in codes or []:
    current = _cached_current_price(code)
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
        st.markdown(f"##### 📈 {name} ({code})")  # st.subheader(h3)보다 작은 h5.
        chart_buffer = build_price_chart(code, name, daily_closes)
        st.image(chart_buffer)
        continue

    intraday = _cached_intraday(code)

    if not trend_shown:
        # 종목마다 거의 동일한 문구가 반복되므로, 첫 종목 데이터로 한 번만 제목 아래에 채운다.
        trend_placeholder.markdown(
            f'<div style="font-size:1.1rem;color:gray;">'
            f'{describe_price_trend(daily_closes, intraday)}</div>',
            unsafe_allow_html=True,
        )
        trend_shown = True

    # 종목명(코드)은 한 줄, 가격·등락은 그 다음 줄(4칸 들여쓰기)에 표시한다. 한 줄에 다 넣으니
    # 폭이 좁은 화면에서 넘쳐서 줄을 나눴다. 종목명만 <b>로 굵게 강조한다. 색상은 한국 증시
    # 관례(상승=빨강/하락=초록)를 따른다.
    rate = current["rate"]
    if rate > 0:
        delta_arrow, delta_color = "▲", "#ff2b2b"
    elif rate < 0:
        delta_arrow, delta_color = "▼", "#09ab3b"
    else:
        delta_arrow, delta_color = "▫", "#888888"
    st.markdown(
        f"""
        <div style="font-size:14.8pt;">
            📈 <b>{current['name']}</b> ({code})<br>
            &nbsp;&nbsp;&nbsp;&nbsp;{current['price']:,}원
            <span style="color:{delta_color};font-size:11pt;">{delta_arrow} {rate}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 분봉도 없고(intraday 비어있음) 장도 닫혀있으면(is_open=False), 지금 조회한 "현재가"는
    # 장마감 후~다음 장 시작 전이라 필연적으로 daily_closes의 마지막 종가와 같은 값이다(네이버
    # API가 장이 안 열려있으면 최근 종가를 그대로 돌려주기 때문). 그대로 넘기면 "어제 종가" 점과
    # "현재가" 점이 같은 값으로 중복 표시되므로, 이 경우엔 None을 넘겨 별도 점을 추가하지 않는다.
    today_price = current["price"] if (current["is_open"] or intraday) else None
    chart_buffer = build_price_chart(
        code, current["name"], daily_closes, today_price, intraday
    )
    st.image(chart_buffer)  # build_price_chart()가 만든 PNG 바이트 버퍼를 그대로 화면에 그린다.
