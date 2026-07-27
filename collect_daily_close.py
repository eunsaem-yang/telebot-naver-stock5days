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
)

# 이 파일은 함수로 감싸지 않고 맨 위에서 아래로 순서대로 실행되는 "스크립트" 형태다
# (notify_stock_price.py처럼 함수로 감싸 재사용할 필요가 없어서 더 단순하게 작성했다).
if not is_trading_day():
    print("📅 오늘은 KRX 개장일이 아닙니다 (주말/공휴일). 종가 수집을 건너뜁니다.")
    exit()  # 스크립트를 여기서 즉시 종료한다 (아래 코드는 실행되지 않는다).

watchlist_codes = read_watchlist()
if watchlist_codes is None:
    exit()

# datetime.now(KST): 지금 이 순간의 날짜+시각(한국 시간 기준). GitHub Actions는 UTC로 돌기
# 때문에 시간대를 명시하지 않으면 수동/야간 실행 시 날짜가 하루 어긋날 수 있다.
# .strftime("%Y%m%d")로 "20260723" 같은 8자리 문자열로 바꾼다 — Turso DB의 date 컬럼과
# 같은 형식을 맞추기 위해서다.
today_str = datetime.now(KST).strftime("%Y%m%d")

print(f"🚀 [{today_str}] 종가 수집 시작...")

collected = 0  # 실제로 저장에 성공한 종목 수를 센다.
for code in watchlist_codes:
    info = fetch_naver_current_price(code)
    if info is None:
        continue

    if info["is_open"]:
        # 장마감 후 실행되어야 하는 스크립트인데 아직 장중이면 종가가 확정되지 않은
        # 상태이므로 히스토리에 반영하지 않는다 (실행 시각 설정을 다시 확인해야 함).
        print(f"⚠️ [{code}] 아직 장중입니다. 확정되지 않은 가격이라 기록하지 않습니다.")
        continue

    if info["price"] <= 0:
        # 네이버 응답 파싱 실패 시 fetch_naver_current_price()가 조용히 0을 반환하는데,
        # 이걸 그대로 저장하면 히스토리가 0원으로 오염된다 (그래프·전일 대비 계산이 깨짐).
        print(f"⚠️ [{code}] 종가 조회 실패(0원). 기록하지 않습니다.")
        continue

    update_price_history(code, today_str, info["price"])
    collected += 1
    print(f"✅ [{code}] {info['name']} 종가 {info['price']:,}원 기록")

if collected == 0:
    print("❌ 기록된 종가가 하나도 없습니다.")
    exit()

print(f"🎉 종가 히스토리를 Turso DB에 저장했습니다 ({collected}/{len(watchlist_codes)}종목).")
