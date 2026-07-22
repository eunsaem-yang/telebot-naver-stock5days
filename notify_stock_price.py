"""
하루 3회(장이 열리는 날 오전 10시/12시/2시) 실행되는 알림 스크립트.
관심종목(watchlist.csv)의 현재가를 네이버 API로 조회해 텔레그램 텍스트 메시지로 보내고,
collect_daily_close.py가 미리 저장해 둔 Turso DB의 최근 15거래일 종가에 오늘 분봉
(네이버 API로 즉시 조회, 저장하지 않음)을 이어붙인 추이 그래프를 종목별로 그려 sendPhoto로
전송한다. 과거 종가 자체는 매번 재조회하지 않는다.
과거 data.go.kr 기반 구현과 그 한계는 ROADMAP.md 참고.

send_price_notification()으로 로직을 감싸 둔 이유는 check_manual_trigger.py(텔레그램 버튼
수동 트리거)가 동일한 알림 로직을 그대로 재사용하기 위해서다. `python notify_stock_price.py`로
직접 실행했을 때의 동작(하루 3회 자동 스케줄)은 이전과 동일하다.
"""
import html

from stock_utils import (
    is_trading_day,
    read_watchlist,
    load_price_history,
    fetch_naver_current_price,
    fetch_naver_intraday_minutes,
    send_telegram_message,
    send_telegram_photo,
    build_price_chart,
    describe_price_trend,
    MANUAL_TRIGGER_KEYBOARD,
)


def send_price_notification() -> None:
    """관심종목 현재가 텍스트 메시지와 종목별 추이 그래프를 텔레그램으로 전송합니다."""
    if not is_trading_day():
        print("📅 오늘은 KRX 개장일이 아닙니다 (주말/공휴일). 알림을 건너뜁니다.")
        return

    watchlist_codes = read_watchlist()
    if watchlist_codes is None:
        return

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
        return

    # reply_markup으로 수동 트리거 버튼을 매번 같이 보내, 텔레그램 클라이언트가 어떤 이유로든
    # 버튼을 숨겨도 다음 알림에서 다시 노출되도록 한다.
    if send_telegram_message(telegram_message, reply_markup=MANUAL_TRIGGER_KEYBOARD):
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

        intraday_minutes = fetch_naver_intraday_minutes(code)
        chart_buffer = build_price_chart(code, info["name"], daily_closes, info["price"], intraday_minutes)
        caption = f"📈 {info['name']} ({code}) {describe_price_trend(daily_closes, intraday_minutes)}"

        if send_telegram_photo(chart_buffer, caption):
            print(f"🎉 [{code}] 추이 그래프를 텔레그램으로 전송했습니다!")
        else:
            print(f"❌ [{code}] 추이 그래프 전송에 실패했습니다.")


if __name__ == "__main__":
    send_price_notification()
