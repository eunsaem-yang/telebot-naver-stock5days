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

로컬에서 직접 실행하면 감지 결과만 출력한다. 감지됐을 때 바로 알림까지 보내보고 싶다면
`python notify_stock_price.py`를 이어서 실행하면 된다.
"""
import os

from stock_utils import (
    fetch_telegram_updates,
    is_trading_day,
    MANUAL_TRIGGER_TEXT,
    MANUAL_TRIGGER_COMMAND,
    TELEGRAM_CHAT_ID,
)


def _is_trigger_message(update: dict) -> bool:
    message = update.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None or str(chat_id) != str(TELEGRAM_CHAT_ID):
        return False
    return message.get("text") in (MANUAL_TRIGGER_TEXT, MANUAL_TRIGGER_COMMAND)


def _report_triggered(triggered: bool) -> None:
    """GitHub Actions에서 실행 중이면 GITHUB_OUTPUT에 기록해 다음 job이 참조할 수 있게 한다."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
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
last_update_id = updates[-1]["update_id"]
fetch_telegram_updates(offset=last_update_id + 1)

button_pressed = any(_is_trigger_message(update) for update in updates)

if not button_pressed:
    print("🔍 수동 트리거 메시지는 없었습니다.")
    _report_triggered(False)
elif not is_trading_day():
    print("📅 트리거는 감지됐지만 오늘은 KRX 개장일이 아니라 알림을 건너뜁니다.")
    _report_triggered(False)
else:
    print("🚀 수동 트리거 감지!")
    _report_triggered(True)
