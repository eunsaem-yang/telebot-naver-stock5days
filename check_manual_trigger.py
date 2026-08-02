"""
텔레그램 채팅에서 수동 트리거가 있었는지 getUpdates로 확인만 하는 스크립트. 실제 알림 전송은
이 스크립트가 아니라 notify_stock_price.py가 맡는다 — GitHub Actions 워크플로에서 "확인"과
"전송"을 별도 job으로 나눠, 트리거가 실제로 감지됐을 때만 무거운 의존성(pandas/matplotlib 등)을
설치하기 위해서다. 배경과 스케줄 관련 한계는 ROADMAP.md "기능 4" 참고.

트리거는 두 가지 방식 중 하나로 온다 — 둘 다 일반 텍스트 메시지라 판별 로직은 동일하다:
1. 리플라이 키보드 버튼(MANUAL_TRIGGER_TEXT)을 눌렀을 때
2. 채팅 입력창 옆 고정 메뉴에서 MANUAL_TRIGGER_COMMAND(/notify)를 선택했을 때 — 버튼이 붙어있던
   메시지를 사용자가 지워서 버튼 자체가 없어졌을 때를 대비한 보험 경로다 (ROADMAP.md "기능 4" 참고).

휴장일(주말/공휴일)에 버튼을 눌러도 notify_stock_price.py는 어차피 아무것도 안 보내고 조용히
끝나므로, 여기서 is_trading_day()로 미리 걸러 무거운 notify job 자체가 켜지지 않게 한다.
다만 그 경우에도 "쉬는 날이라 보낼 시세가 없다"는 안내 메시지 한 건은 보낸다 — 버튼을 누른 것은
사용자의 명시적 요청이고, 요청에 아무 응답이 없으면 정상 종료와 고장을 구별할 수 없기 때문이다.
안내에 대시보드를 함께 언급하는 이유는, 휴장일에 "쌓인 과거 종가를 본다"는 것은 push(텔레그램)가
아니라 pull(대시보드)이 맡는 일이기 때문이다 — 새 시세는 push, 쌓인 데이터는 pull.

로컬에서 직접 실행하면 감지 결과만 출력한다. 감지됐을 때 바로 알림까지 보내보고 싶다면
`python notify_stock_price.py`를 이어서 실행하면 된다.
"""
import os

from stock_utils import (
    fetch_telegram_updates,
    send_telegram_message,
    is_trading_day,
    MANUAL_TRIGGER_TEXT,
    MANUAL_TRIGGER_COMMAND,
    TELEGRAM_CHAT_ID,
)


def _is_trigger_message(update: dict) -> bool:
    """텔레그램 update 하나가 "수동 트리거" 메시지인지 판별한다."""
    # update.get("message") or {}: "message" 키가 없거나 값이 None이면 빈 딕셔너리를 대신
    # 쓴다 — 뒤에서 .get()을 또 호출해도 에러 없이 안전하게 넘어가기 위해서다.
    message = update.get("message") or {}
    # 메시지 안의 chat.id를 딕셔너리 접근을 두 번 연달아 해서 꺼낸다: message["chat"]가 다시
    # 딕셔너리이고, 그 안에 "id"가 있다.
    chat_id = message.get("chat", {}).get("id")
    # 내 텔레그램 채팅(TELEGRAM_CHAT_ID)에서 온 메시지가 아니면 무시한다 (다른 사람이 이
    # 봇에게 말을 걸어도 반응하지 않도록). str()로 감싸는 건 두 값의 타입(문자열/정수)이
    # 다를 수 있어 비교 전에 형태를 맞추기 위해서다.
    if chat_id is None or str(chat_id) != str(TELEGRAM_CHAT_ID):
        return False
    # 메시지 텍스트가 버튼 문구 또는 /notify 명령어 중 하나와 정확히 같으면 트리거로 인정한다.
    return message.get("text") in (MANUAL_TRIGGER_TEXT, MANUAL_TRIGGER_COMMAND)


def _report_triggered(triggered: bool) -> None:
    """GitHub Actions에서 실행 중이면 GITHUB_OUTPUT에 기록해 다음 job이 참조할 수 있게 한다."""
    # GITHUB_OUTPUT은 GitHub Actions가 실행 중에만 만들어주는 환경변수(파일 경로)다.
    # 로컬 실행일 땐 이 값이 없어서(None) 아래 if가 거짓이 되어 아무 일도 하지 않는다.
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        # "a" 모드: 파일 내용을 지우지 않고 끝에 이어서 쓴다(append). 이 파일에
        # "이름=값" 형식으로 한 줄 추가하면, 같은 워크플로의 다음 job이
        # `needs.check.outputs.triggered`로 이 값을 읽을 수 있다.
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"triggered={'true' if triggered else 'false'}\n")


updates = fetch_telegram_updates()

if not updates:
    print("🔍 새 텔레그램 메시지가 없습니다.")
    _report_triggered(False)
    exit()

# 이번에 받아온 업데이트는 트리거 여부와 상관없이 모두 확인 처리한다.
# (텔레그램 서버에 offset을 넘겨 다음 폴링 때 동일 메시지가 중복으로 돌아오지 않게 함 — 이 스크립트는
# 매 실행마다 새로 시작되므로 로컬에 offset을 따로 저장하지 않고 텔레그램 서버 쪽 상태만 사용한다.)
last_update_id = updates[-1]["update_id"]  # updates[-1]: 리스트의 마지막(가장 최근) 항목.
fetch_telegram_updates(offset=last_update_id + 1)

# any(...)는 괄호 안 조건이 하나라도 True면 즉시 True를 반환한다(제너레이터 표현식과 함께 쓰면
# 리스트를 다 순회하지 않고도 도중에 멈출 수 있어 효율적이다). 즉 "받아온 메시지들 중 트리거로
# 인정되는 게 하나라도 있는가?"를 확인한다.
button_pressed = any(_is_trigger_message(update) for update in updates)

if not button_pressed:
    print("🔍 수동 트리거 메시지는 없었습니다.")
    _report_triggered(False)
elif not is_trading_day():
    print("📅 트리거는 감지됐지만 오늘은 KRX 개장일이 아니라 알림을 건너뜁니다.")
    # 버튼을 눌렀다는 것은 사용자의 명시적 요청이므로, 아무것도 보내지 않으면 "눌렀는데 반응이
    # 없다"가 되어 정상 종료와 고장을 사용자가 구별할 수 없다. 그래서 여기서만 안내를 보낸다 —
    # 하루 3회 자동으로 도는 notify_stock_price.py의 같은 가드에는 붙이지 않는다. 아무도
    # 요청하지 않았는데 공휴일마다 세 번씩 오게 되기 때문이다(판단 기준은 "사용자가 요청했는가").
    send_telegram_message(
        "📅 오늘은 증시가 열리지 않는 날이라 새로 보내드릴 시세가 없습니다.\n"
        "최근 종가 추이는 대시보드에서 언제든 보실 수 있습니다.\n"
        "평일 개장일에 다시 눌러주세요."
    )
    _report_triggered(False)
else:
    print("🚀 수동 트리거 감지!")
    _report_triggered(True)
