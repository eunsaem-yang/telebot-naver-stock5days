"""
텔레그램에 수동 트리거 경로 두 가지를 준비해두는 1회성 설정 스크립트.
로컬에서 한 번만 실행하면 된다.

1. 채팅창에 리플라이 키보드 버튼을 노출 (다시 바꾸기 전까지 계속 남는다)
2. 채팅 입력창 옆 고정 메뉴에 /notify 명령어를 등록 (메시지를 지워도 안 사라지는 보험 경로)

사용법: python ./setup_telegram_button.py
"""
from stock_utils import (
    send_telegram_message,
    register_telegram_commands,
    MANUAL_TRIGGER_KEYBOARD,
    MANUAL_TRIGGER_TEXT,
    MANUAL_TRIGGER_COMMAND,
)

# f-string 안에 {MANUAL_TRIGGER_TEXT}/{MANUAL_TRIGGER_COMMAND}처럼 stock_utils.py의 상수를
# 그대로 끼워 넣어서, 실제 버튼 문구/명령어가 나중에 바뀌어도 이 안내 메시지가 자동으로 맞게 나온다.
text = (
    "✅ 설정 완료!\n"
    f"아래 <b>'{MANUAL_TRIGGER_TEXT}'</b> 버튼을 누르거나, 이 메시지가 안 보이면 채팅 입력창 옆 "
    f"메뉴에서 <b>{MANUAL_TRIGGER_COMMAND}</b>를 선택해도 언제든 관심종목 현재가를 확인할 수 "
    "있어요. 누르면 확인 작업이 그 요청을 감지해 현재가를 보내드려요."
)

# 두 가지를 각각 설정한다: (1) reply_markup으로 리플라이 키보드 버튼을 이 메시지에 붙여서 노출,
# (2) 채팅 입력창 옆 고정 메뉴에 /notify 명령어를 등록. 서로 독립적인 API 호출이라 결과도 각자
# 따로(button_ok, command_ok) 확인한다.
button_ok = send_telegram_message(text, reply_markup=MANUAL_TRIGGER_KEYBOARD)
command_ok = register_telegram_commands()

if button_ok:
    print("✅ 텔레그램에 버튼을 노출했습니다.")
else:
    print("❌ 버튼 설정 메시지 전송에 실패했습니다.")

if command_ok:
    print(f"✅ 고정 메뉴에 {MANUAL_TRIGGER_COMMAND} 명령어를 등록했습니다.")
else:
    print("❌ 명령어 메뉴 등록에 실패했습니다.")
