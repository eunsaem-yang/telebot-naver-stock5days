"""
telebot_krx_stock.py(하루 3회 알림)와 collect_daily_close.py(하루 1회 종가 수집)가
공통으로 쓰는 함수 모음.

네이버 금융 비공식 API(m.stock.naver.com)는 장중이면 실시간 체결가를, 장 시작 전/마감
후에는 가장 최근 종가를 marketStatus/closePrice 필드로 그대로 돌려주므로, 이 하나의
엔드포인트로 "현재가 조회"와 "일별 종가 기록"을 모두 처리한다. (공공데이터포털 API는
basDd 날짜 필터가 정상 동작하지 않아 더 이상 사용하지 않는다. ROADMAP.md 참고)
"""
import os
import io
import json
import requests
import pandas as pd
import holidays
import matplotlib
matplotlib.use("Agg")  # 화면 출력 없이 이미지 파일(버퍼)로만 저장
import matplotlib.pyplot as plt
from datetime import datetime

plt.rcParams["font.family"] = "Malgun Gothic"  # 그래프 한글 표시
plt.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지

WATCHLIST_FILE = "watchlist.csv"
PRICE_HISTORY_FILE = "price_history.json"
NUM_HISTORY_DAYS = 5

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

_KR_HOLIDAYS = holidays.KR()


def is_trading_day(date: datetime = None) -> bool:
    """평일이면서 한국 공휴일이 아닌 날(=KRX 개장일)인지 확인합니다."""
    date = date or datetime.now()
    if date.weekday() >= 5:  # 5=토요일, 6=일요일
        return False
    return date.date() not in _KR_HOLIDAYS


def read_watchlist(path: str = WATCHLIST_FILE) -> list:
    """watchlist.csv를 읽어 종목코드 리스트를 반환합니다. 실패 시 None."""
    if not os.path.exists(path):
        print(f"❌ '{path}' 파일이 존재하지 않습니다.")
        return None

    try:
        # 앞자리에 0이 있는 종목코드(예: 005930)가 깨지지 않도록 str(문자열) 타입으로 읽습니다.
        watchlist_df = pd.read_csv(path, dtype={"code": str})

        # 컬럼명의 공백을 제거하고 소문자로 통일하여 'code' 컬럼을 찾습니다.
        watchlist_df.columns = [col.strip().lower() for col in watchlist_df.columns]

        if "code" not in watchlist_df.columns:
            print("❌ CSV 파일에 'code' 컬럼이 존재하지 않습니다.")
            return None

        codes = watchlist_df["code"].tolist()
        print(f"📋 읽어온 관심 종목 리스트: {codes}")
        return codes

    except Exception as e:
        print(f"❌ CSV 파일을 읽는 동안 오류가 발생했습니다: {e}")
        return None


def load_price_history(path: str = PRICE_HISTORY_FILE) -> dict:
    """{code: [{"date": "YYYYMMDD", "close": 가격}, ...]} 형태의 종가 히스토리를 읽습니다."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ '{path}' 읽기 실패: {e}")
        return {}


def save_price_history(history: dict, path: str = PRICE_HISTORY_FILE) -> None:
    """종가 히스토리를 JSON 파일로 저장합니다."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_price_history(history: dict, code: str, date_str: str, close_price: int,
                          num_days: int = NUM_HISTORY_DAYS) -> None:
    """종목의 종가 히스토리에 오늘자 종가를 추가합니다. 같은 날짜가 이미 있으면 덮어쓰고,
    최근 num_days개만 남깁니다."""
    entries = {entry["date"]: entry["close"] for entry in history.get(code, [])}
    entries[date_str] = close_price
    sorted_dates = sorted(entries.keys())[-num_days:]
    history[code] = [{"date": d, "close": entries[d]} for d in sorted_dates]


def fetch_naver_current_price(code: str) -> dict:
    """네이버 금융 비공식 API로 종목의 현재가(장중) 또는 최근 종가(장마감)를 조회합니다."""
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code != 200:
            print(f"❌ [{code}] 네이버 현재가 조회 실패 (응답 코드: {response.status_code})")
            return None

        data = response.json()
        price_str = data.get("closePrice", "0").replace(",", "")
        return {
            "code": code,
            "name": data.get("stockName", "알 수 없음"),
            "price": int(price_str) if price_str.isdigit() else 0,
            "rate": float(data.get("fluctuationsRatio", "0") or "0"),
            "is_open": data.get("marketStatus") == "OPEN",
        }
    except Exception as e:
        print(f"❌ [{code}] 네이버 현재가 조회 중 오류 발생: {e}")
        return None


def send_telegram_message(text: str) -> bool:
    """텔레그램 sendMessage API로 텍스트 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=data, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 중 오류 발생: {e}")
        return False


def send_telegram_photo(photo_buffer: io.BytesIO, caption: str) -> bool:
    """텔레그램 sendPhoto API로 이미지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("chart.png", photo_buffer, "image/png")}
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
    try:
        response = requests.post(url, data=data, files=files, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 텔레그램 이미지 전송 중 오류 발생: {e}")
        return False


def build_price_chart(code: str, name: str, daily_closes: list, current_price: int) -> io.BytesIO:
    """종목별 최근 N일 종가 + 현재가 추이를 선 그래프로 그려 PNG 이미지 버퍼로 반환합니다.
    daily_closes는 [{"date": "YYYYMMDD", "close": 가격}, ...] (날짜 오름차순)."""
    labels = [f"{entry['date'][4:6]}/{entry['date'][6:]}" for entry in daily_closes] + ["현재"]
    prices = [entry["close"] for entry in daily_closes] + [current_price]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(labels, prices, marker="o", color="#1f77b4")
    for x, y in zip(labels, prices):
        ax.annotate(f"{y:,}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)

    ax.set_title(f"{name} ({code}) 최근 {len(daily_closes)}일 종가 + 현재가")
    ax.set_ylabel("가격 (원)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer
