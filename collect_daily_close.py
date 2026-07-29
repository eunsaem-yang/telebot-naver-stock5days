"""
장마감 직후 하루 1회 실행되는 스크립트.
관심종목(watchlist.csv)의 그날 최종 종가를 네이버 API로 조회해 Turso DB의 price_history
테이블에 누적 저장한다 (종목별 최근 15거래일치만 유지, 오래된 행은 삭제). notify_stock_price.py는
이 DB를 읽기만 하고 직접 API를 재조회하지 않는다 — 자세한 배경은 ROADMAP.md의 "기능 3"·"Turso
마이그레이션" 절 참고. 예전에는 price_history.json을 저장소에 직접 커밋해 상태를 유지했지만,
DB 자체가 영속 저장소이므로 이제 git 커밋 스텝이 필요 없다.
"""
from datetime import datetime

from stock_utils import (
    KST,
    is_trading_day,
    read_watchlist,
    update_price_history,
    fetch_naver_current_price,
    get_turso_client,
)

# 이 파일은 함수로 감싸지 않고 맨 위에서 아래로 순서대로 실행되는 "스크립트" 형태다
# (notify_stock_price.py처럼 함수로 감싸 재사용할 필요가 없어서 더 단순하게 작성했다).
if not is_trading_day():
    print("📅 오늘은 KRX 개장일이 아닙니다 (주말/공휴일). 종가 수집을 건너뜁니다.")
    # 휴장일은 실패가 아니라 "할 일이 없어 정상 종료"하는 경우이므로 종료 코드 0(exit())을 쓴다.
    exit()  # 스크립트를 여기서 즉시 종료한다 (아래 코드는 실행되지 않는다).

watchlist_codes = read_watchlist()
if watchlist_codes is None:
    # exit(1)은 "실패로 끝났다"는 종료 코드다. 그냥 exit()(=0)으로 끝내면 GitHub Actions가
    # 이 실행을 성공(녹색 체크)으로 표시해 버려서, 관심종목 파일을 못 읽는 장애를 알아챌 수 없다.
    exit(1)

print(f"🚀 종가 수집 시작... (실행 시각 {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST)")

collected = 0  # 실제로 저장에 성공한 종목 수를 센다.
# get_turso_client()를 루프 밖에서 딱 한 번만 호출해 클라이언트 하나를 만들고, 종목마다
# update_price_history()에 그 client를 넘겨 재사용한다 — 관심종목이 몇 개 안 될 때는 차이가
# 작지만, 종목 수가 늘어날수록(예: 20개) 종목마다 새로 연결을 맺고 매번 테이블 존재 확인
# 쿼리까지 반복하는 비용을 줄여준다. with 문이라 루프가 끝나면(예외가 나도) client.close()가
# 자동으로 호출된다.
with get_turso_client() as client:
    for code in watchlist_codes:
        info = fetch_naver_current_price(code)
        if info is None:
            continue

        if info["is_open"]:
            # 장마감 후 실행되어야 하는 스크립트인데 아직 장중이면 종가가 확정되지 않은
            # 상태이므로 히스토리에 반영하지 않는다 (실행 시각 설정을 다시 확인해야 함).
            print(f"⚠️ [{code}] 아직 장중입니다. 확정되지 않은 가격이라 기록하지 않습니다.")
            continue

        # 저장할 날짜는 "지금 몇 시인가"가 아니라 "이 가격이 언제 체결된 것인가"로 정한다.
        # datetime.now()를 쓰면 스케줄이 지연돼 자정을 넘겨 실행됐을 때 전날 종가가 다음날
        # 날짜로 저장된다(실제로 발생했던 문제다). traded_at은 체결 시각이라 실행 시각과
        # 무관하게 항상 옳은 거래일을 가리킨다.
        # "2026-07-29T16:10:20+09:00"에서 앞 10글자가 날짜("2026-07-29")이고, 하이픈을 빼면
        # DB의 date 컬럼 형식("20260729")이 된다.
        traded_at = info.get("traded_at") or ""
        if len(traded_at) >= 10:
            date_str = traded_at[:10].replace("-", "")
        else:
            # 네이버 응답에 이 필드가 없거나 형식이 바뀐 경우의 폴백 — 예전처럼 실행 시각을 쓴다.
            date_str = datetime.now(KST).strftime("%Y%m%d")
            print(f"⚠️ [{code}] 체결 시각을 읽지 못해 실행 시각 기준으로 날짜를 정합니다.")

        update_price_history(code, date_str, info["price"], client=client)
        collected += 1
        print(f"✅ [{code}] {info['name']} {date_str} 종가 {info['price']:,}원 기록")

if collected == 0:
    print("❌ 기록된 종가가 하나도 없습니다.")
    # 한 종목도 기록하지 못한 실패이므로 종료 코드 1로 끝낸다 — 그래야 GitHub Actions에 빨간
    # 실패 표시와 기본 실패 알림이 뜬다. 0으로 끝나면 네이버 차단 같은 장애가 묻혀버린다.
    exit(1)

print(f"🎉 종가 히스토리를 Turso DB에 저장했습니다 ({collected}/{len(watchlist_codes)}종목).")
