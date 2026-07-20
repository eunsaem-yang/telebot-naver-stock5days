"""
하루 3회(장이 열리는 날 오전 10시/12시/2시) 실행되는 알림 스크립트.
관심종목(watchlist.csv)의 현재가를 네이버 API로 조회해 텔레그램 텍스트 메시지로 보내고,
collect_daily_close.py가 미리 저장해 둔 price_history.json의 최근 15거래일 종가에 방금 조회한
현재가를 마지막 점으로 추가한 그래프를 종목별로 그려 sendPhoto로 전송한다.
과거 data.go.kr 기반 구현과 그 한계는 ROADMAP.md 참고.
"""
import html

from stock_utils import (
    is_trading_day,
    read_watchlist,
    load_price_history,
    fetch_naver_current_price,
    send_telegram_message,
    send_telegram_photo,
    build_price_chart,
)

if not is_trading_day():
    print("📅 오늘은 KRX 개장일이 아닙니다 (주말/공휴일). 알림을 건너뜁니다.")
    exit()

watchlist_codes = read_watchlist()
if watchlist_codes is None:
    exit()

# 1. 네이버 API로 현재가 조회 후 텔레그램 텍스트 메시지 전송
print("🚀 관심종목 현재가 조회 시작...")

current_prices = {}  # code -> fetch_naver_current_price() 결과
telegram_message = "📊 <b>내 관심종목 현재가</b>\n\n"

for code in watchlist_codes:
    info = fetch_naver_current_price(code)
    if info is None:
        continue

    current_prices[code] = info

    name = html.escape(info["name"])
    price = info["price"]
    rate = info["rate"]
    label = "현재가 (장중)" if info["is_open"] else "종가 (장마감 기준)"

    if rate > 0:
        sign, rate_str = "🔺", f"+{rate}%"
    elif rate < 0:
        sign, rate_str = "🔻", f"{rate}%"  # 자체적으로 마이너스가 붙어 나옴
    else:
        sign, rate_str = "▫️", "0.0%"

    telegram_message += f"▪️ <b>{name}</b> ({html.escape(code)})\n"
    telegram_message += f"  {label}: {price:,}원 ({sign} {rate_str})\n\n"

if not current_prices:
    print("❌ 관심종목의 현재가를 하나도 가져오지 못했습니다. 네이버 API 상태를 확인해 주세요.")
    exit()

if send_telegram_message(telegram_message):
    print("✅ 현재가 메시지를 텔레그램으로 전송했습니다!")
else:
    print("❌ 현재가 메시지 전송에 실패했습니다.")

# 2. collect_daily_close.py가 저장해 둔 최근 15거래일 종가를 읽어 그래프 생성 및 전송
price_history = load_price_history()

for code, info in current_prices.items():
    daily_closes = price_history.get(code, [])
    if not daily_closes:
        print(f"⚠️ [{code}] 저장된 종가 히스토리가 없어 현재가만으로 그래프를 그립니다. "
              f"collect_daily_close.py가 아직 한 번도 실행되지 않았을 수 있습니다.")

    chart_buffer = build_price_chart(code, info["name"], daily_closes, info["price"])
    if daily_closes:
        caption = f"📈 {info['name']} ({code}) 최근 {len(daily_closes)}일 종가 + 현재가 추이"
    else:
        caption = f"📈 {info['name']} ({code}) 현재가 (종가 히스토리 누적 전)"

    if send_telegram_photo(chart_buffer, caption):
        print(f"🎉 [{code}] 추이 그래프를 텔레그램으로 전송했습니다!")
    else:
        print(f"❌ [{code}] 추이 그래프 전송에 실패했습니다.")
