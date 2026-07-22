"""
notify_stock_price.py(하루 3회 알림), collect_daily_close.py(하루 1회 종가 수집),
check_manual_trigger.py·setup_telegram_button.py(텔레그램 수동 트리거)가 공통으로 쓰는
함수 모음.

네이버 금융 비공식 API(m.stock.naver.com)는 장중이면 실시간 체결가를, 장 시작 전/마감
후에는 가장 최근 종가를 marketStatus/closePrice 필드로 그대로 돌려주므로, 이 하나의
엔드포인트로 "현재가 조회"와 "일별 종가 기록"을 모두 처리한다. (공공데이터포털 API는
basDd 날짜 필터가 정상 동작하지 않아 더 이상 사용하지 않는다. ROADMAP.md 참고)
"""
import os
import io
import json
import re
import requests
import holidays
from datetime import datetime
from dotenv import load_dotenv

# pandas/matplotlib은 read_watchlist()/build_price_chart() 안에서 그때그때 import한다.
# check_manual_trigger.py처럼 이 모듈에서 텔레그램 관련 함수만 가져다 쓰는 스크립트는 이 두
# (설치·로딩이 무거운) 패키지가 아예 필요 없는데, 모듈 최상단에서 import하면 이런 스크립트를
# 실행할 때도 강제로 설치돼 있어야 한다 — GitHub Actions의 가벼운 "check" job이 requests/
# python-dotenv/holidays만 설치하는 것도 이 때문에 가능해진다 (ROADMAP.md "기능 4" 참고).

WATCHLIST_FILE = "watchlist.csv"
NUM_HISTORY_DAYS = 15
MANUAL_TRIGGER_TEXT = "📊 지금 현재가 확인"  # 리플라이 키보드 버튼 라벨이자 트리거 판별 문자열
MANUAL_TRIGGER_KEYBOARD = {"keyboard": [[{"text": MANUAL_TRIGGER_TEXT}]], "resize_keyboard": True}
MANUAL_TRIGGER_COMMAND = "/notify"  # 채팅 입력창 옆 고정 메뉴에 등록하는 명령어 (메시지를 지워도 안 사라짐)

# 이 모듈이 임포트되는 시점에 바로 .env를 로드해야, 아래 os.environ.get() 호출이
# 호출 스크립트의 import 순서와 무관하게 항상 올바른 값을 읽는다.
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

_KR_HOLIDAYS = holidays.KR()


def is_trading_day(date: datetime = None) -> bool:
    """평일이면서 한국 공휴일이 아닌 날(=KRX 개장일)인지 확인합니다."""
    date = date or datetime.now()
    if date.weekday() >= 5:  # 5=토요일, 6=일요일
        return False
    return date.date() not in _KR_HOLIDAYS


def read_watchlist(path: str = WATCHLIST_FILE) -> list:
    """watchlist.csv를 읽어 종목코드 리스트를 반환합니다. 실패 시 None."""
    import pandas as pd

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


def _get_turso_client():
    """Turso(libSQL) DB 클라이언트를 생성하고, price_history 테이블이 없으면 만듭니다.
    libsql_client는 여기서만 필요한 무거운(네트워크 연결) 의존성이라 모듈 최상단이 아니라
    이 함수 안에서 import한다 (pandas/matplotlib과 동일한 이유, 파일 상단 주석 참고)."""
    import libsql_client

    if not TURSO_DATABASE_URL:
        raise RuntimeError("TURSO_DATABASE_URL 환경변수가 설정되지 않았습니다.")

    # turso db show --url이 돌려주는 libsql:// 스킴은 WebSocket(wss://)으로 연결되는데,
    # 학교/사내 방화벽이나 일부 실행 환경에서 WebSocket이 막혀 있으면 에러조차 없이 그냥
    # 멈춰버린다(타임아웃 없이 무한 대기). transaction() API를 쓰지 않아 HTTP만으로도 충분하므로,
    # 항상 https://로 바꿔 접속해 이 문제를 원천적으로 피한다.
    url = TURSO_DATABASE_URL.replace("libsql://", "https://", 1)
    client = libsql_client.create_client_sync(url, auth_token=TURSO_AUTH_TOKEN)
    client.execute(
        "CREATE TABLE IF NOT EXISTS price_history ("
        "code TEXT NOT NULL, date TEXT NOT NULL, close INTEGER NOT NULL, "
        "PRIMARY KEY (code, date))"
    )
    return client


def load_price_history() -> dict:
    """Turso DB에서 종목별 종가 히스토리를 읽어 {code: [{"date": "YYYYMMDD", "close": 가격}, ...]}
    형태(날짜 오름차순)로 반환합니다. 예전에는 이 함수가 price_history.json을 읽었지만, Turso
    마이그레이션 이후로는 DB에서 직접 SELECT한다 (ROADMAP.md 참고)."""
    try:
        with _get_turso_client() as client:
            result = client.execute("SELECT code, date, close FROM price_history ORDER BY code, date")
    except Exception as e:
        print(f"❌ Turso DB에서 종가 히스토리를 읽지 못했습니다: {e}")
        return {}

    history: dict = {}
    for code, date, close in result.rows:
        history.setdefault(code, []).append({"date": date, "close": close})
    return history


def update_price_history(code: str, date_str: str, close_price: int,
                          num_days: int = NUM_HISTORY_DAYS) -> None:
    """종목의 종가 히스토리에 오늘자 종가를 Turso DB에 즉시 저장합니다. 같은 날짜가 이미 있으면
    덮어쓰고, 종목별로 최근 num_days개만 남기고 오래된 행은 삭제합니다.

    JSON 파일 방식과 달리 이 함수 호출 자체가 DB에 바로 반영되므로(트랜잭션 커밋), 예전의
    load_price_history() → 메모리에서 수정 → save_price_history()로 파일 통째로 다시 쓰기 같은
    별도의 "저장" 단계가 필요 없다 — 이것이 파일 기반 저장과 DB 기반 저장의 핵심 차이다."""
    try:
        with _get_turso_client() as client:
            client.execute(
                "INSERT INTO price_history (code, date, close) VALUES (?, ?, ?) "
                "ON CONFLICT (code, date) DO UPDATE SET close = excluded.close",
                [code, date_str, close_price],
            )
            client.execute(
                "DELETE FROM price_history WHERE code = ? AND date NOT IN ("
                "SELECT date FROM price_history WHERE code = ? ORDER BY date DESC LIMIT ?)",
                [code, code, num_days],
            )
    except Exception as e:
        print(f"❌ [{code}] Turso DB에 종가 저장 실패: {e}")


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


def fetch_naver_intraday_minutes(code: str, date_str: str = None) -> list:
    """네이버 API로 당일 1분 단위 종가를 조회합니다. 반환값은 시간 오름차순
    [{"time": "HHMM", "price": 가격}, ...]. 실패하거나 아직 장이 시작 전이면 빈 리스트.

    이 API는 과거 데이터를 저장해두는 게 아니라 그 시점까지의 당일 흐름을 즉시 다시 계산해
    돌려주는 방식이라, 우리 쪽에 별도로 저장할 필요가 없다 (자세한 배경은 ROADMAP.md "기능 5" 참고).
    응답이 EUC-KR 인코딩과 표준이 아닌 JSON이 섞여 있어 json.loads 대신 데이터 행만 정규식으로
    추출한다 (헤더의 한글 라벨은 깨지지만 숫자로 된 데이터 행은 영향받지 않는다)."""
    date_str = date_str or datetime.now().strftime("%Y%m%d")
    url = "https://api.finance.naver.com/siseJson.naver"
    params = {"symbol": code, "requestType": 1, "startTime": date_str, "endTime": date_str, "timeframe": "minute"}
    try:
        response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code != 200:
            print(f"❌ [{code}] 당일 분봉 조회 실패 (응답 코드: {response.status_code})")
            return []
        rows = re.findall(r'\["(\d{12})",\s*null,\s*null,\s*null,\s*(\d+),\s*\d+,\s*null\]', response.text)
        if not rows and re.search(r'\["\d{12}"', response.text):
            # 타임스탬프가 찍힌 행은 있는데 우리가 기대한 형식(위 정규식)과 안 맞는 경우 —
            # 장이 아직 안 열려서 데이터가 없는 것과는 다른, API 응답 형식 자체가 바뀐 상황일 수 있다.
            print(f"⚠️ [{code}] 당일 분봉 응답 형식이 예상과 달라 파싱하지 못했습니다. "
                  f"네이버 API 응답 형식이 바뀌었을 수 있습니다.")
        minutes = [{"time": timestamp[8:], "price": int(price)} for timestamp, price in rows]
        minutes.reverse()  # 응답이 최신순이라 시간 오름차순으로 뒤집는다
        return minutes
    except Exception as e:
        print(f"❌ [{code}] 당일 분봉 조회 중 오류 발생: {e}")
        return []


def send_telegram_message(text: str, reply_markup: dict = None) -> bool:
    """텔레그램 sendMessage API로 텍스트 메시지를 전송합니다.
    reply_markup을 넘기면 커스텀 키보드(버튼) 등을 함께 첨부합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        response = requests.post(url, data=data, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 중 오류 발생: {e}")
        return False


def register_telegram_commands() -> bool:
    """채팅 입력창 옆 고정 메뉴에 MANUAL_TRIGGER_COMMAND(/notify)를 등록합니다. 특정 메시지에
    딸린 게 아니라 봇 자체에 등록되는 것이라, 메시지를 아무리 지워도 사라지지 않습니다. 1회만
    실행하면 계속 유지됩니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    command_name = MANUAL_TRIGGER_COMMAND.lstrip("/")
    commands = [{"command": command_name, "description": "지금 관심종목 현재가 확인"}]
    try:
        response = requests.post(url, json={"commands": commands}, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 명령어 메뉴 등록 중 오류 발생: {e}")
        return False


def fetch_telegram_updates(offset: int = None) -> list:
    """텔레그램 getUpdates API로 새 메시지 목록을 가져옵니다.
    offset을 넘기면 그보다 작은 update_id는 텔레그램 서버에서 확인 처리되어,
    다음 호출부터는 다시 돌아오지 않습니다 (별도 로컬 상태 저장 없이 중복 처리를 방지)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            print(f"❌ 텔레그램 업데이트 조회 실패 (응답 코드: {response.status_code})")
            return []
        return response.json().get("result", [])
    except Exception as e:
        print(f"❌ 텔레그램 업데이트 조회 중 오류 발생: {e}")
        return []


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


def describe_price_trend(daily_closes: list, intraday_minutes: list) -> str:
    """그래프에 어떤 데이터가 담겼는지 설명하는 문구를 반환합니다. 그래프 제목과 텔레그램
    캡션이 동일한 문구를 쓰도록 공용으로 뺐습니다."""
    if intraday_minutes:
        return f"최근 {len(daily_closes)}일 종가 + 오늘 분봉 추이"
    if daily_closes:
        return f"최근 {len(daily_closes)}일 종가 + 현재가 추이"
    return "현재가 (종가 히스토리 누적 전)"


def build_price_chart(code: str, name: str, daily_closes: list, current_price: int,
                       intraday_minutes: list = None) -> io.BytesIO:
    """종목별 최근 N일 종가 + 오늘 추이를 선 그래프로 그려 PNG 이미지 버퍼로 반환합니다.
    daily_closes는 [{"date": "YYYYMMDD", "close": 가격}, ...] (날짜 오름차순).
    intraday_minutes를 넘기면(오늘 분봉, 시간 오름차순) 오늘 구간을 분 단위 선으로 그리고,
    없으면 현재가 한 점만 표시합니다(기존 동작과 동일)."""
    import matplotlib
    matplotlib.use("Agg")  # 화면 출력 없이 이미지 파일(버퍼)로만 저장
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Malgun Gothic", "NanumGothic", "AppleGothic"]  # 그래프 한글 표시
    # Windows 로컬은 맑은 고딕, GitHub Actions(Ubuntu, fonts-nanum 설치)는 나눔고딕, macOS는 애플고딕이
    # 순서대로 탐색되어 설치된 첫 폰트가 사용된다.
    plt.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지

    daily_labels = [f"{entry['date'][4:6]}/{entry['date'][6:]}" for entry in daily_closes]
    daily_prices = [entry["close"] for entry in daily_closes]

    if intraday_minutes:
        today_prices = [m["price"] for m in intraday_minutes]
    else:
        today_prices = [current_price]

    prices = daily_prices + today_prices
    x = list(range(len(prices)))
    daily_x = x[:len(daily_prices)]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, prices, color="#1f77b4", linewidth=1.5)

    # 과거 종가는 점 + 값 라벨로 강조한다 (분봉까지 전부 라벨을 붙이면 수백 개가 겹쳐 안 보인다).
    if daily_x:
        ax.plot(daily_x, daily_prices, marker="o", linestyle="None", color="#1f77b4")
        for xi, yi in zip(daily_x, daily_prices):
            ax.annotate(f"{yi:,}", (xi, yi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)

    # 마지막 지점(현재가)은 항상 강조 표시한다.
    ax.plot(x[-1], prices[-1], marker="o", color="#d62728")
    ax.annotate(f"{prices[-1]:,}", (x[-1], prices[-1]), textcoords="offset points",
                xytext=(0, 8), ha="center", fontsize=9, color="#d62728")

    # x축 눈금: 과거 일자는 전부, 오늘 분봉은 정시(HH:00)만 골라 표시한다 (전부 표시하면 겹침).
    tick_positions = list(daily_x)
    tick_labels = list(daily_labels)
    if intraday_minutes:
        offset = len(daily_prices)
        for i, m in enumerate(intraday_minutes):
            if m["time"].endswith("00"):
                tick_positions.append(offset + i)
                tick_labels.append(f"{m['time'][:2]}:{m['time'][2:]}")
    else:
        tick_positions.append(x[-1])
        tick_labels.append("현재")
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

    ax.set_title(f"{name} ({code}) {describe_price_trend(daily_closes, intraday_minutes)}")
    ax.set_ylabel("가격 (원)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer
