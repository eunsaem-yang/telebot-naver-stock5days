"""
장마감 직후 하루 1회 실행되는 스크립트.
관심종목(watchlist.csv)의 그날 최종 종가를 네이버 API로 조회해 price_history.json에
누적 저장한다 (종목별 최근 5거래일치만 유지). telebot_krx_stock.py는 이 파일을 읽기만
하고 직접 API를 재조회하지 않는다 — 자세한 배경은 ROADMAP.md의 "기능 3" 참고.
"""
from datetime import datetime
from dotenv import load_dotenv

from stock_utils import (
    is_trading_day,
    read_watchlist,
    load_price_history,
    save_price_history,
    update_price_history,
    fetch_naver_current_price,
)

load_dotenv()

if not is_trading_day():
    print("📅 오늘은 KRX 개장일이 아닙니다 (주말/공휴일). 종가 수집을 건너뜁니다.")
    exit()

watchlist_codes = read_watchlist()
if watchlist_codes is None:
    exit()

today_str = datetime.now().strftime("%Y%m%d")
history = load_price_history()

print(f"🚀 [{today_str}] 종가 수집 시작...")

collected = 0
for code in watchlist_codes:
    info = fetch_naver_current_price(code)
    if info is None:
        continue

    if info["is_open"]:
        # 장마감 후 실행되어야 하는 스크립트인데 아직 장중이면 종가가 확정되지 않은
        # 상태이므로 히스토리에 반영하지 않는다 (실행 시각 설정을 다시 확인해야 함).
        print(f"⚠️ [{code}] 아직 장중입니다. 확정되지 않은 가격이라 기록하지 않습니다.")
        continue

    update_price_history(history, code, today_str, info["price"])
    collected += 1
    print(f"✅ [{code}] {info['name']} 종가 {info['price']:,}원 기록")

if collected == 0:
    print("❌ 기록된 종가가 하나도 없습니다.")
    exit()

save_price_history(history)
print(f"🎉 종가 히스토리를 저장했습니다 ({collected}/{len(watchlist_codes)}종목).")
