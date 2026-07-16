---
name: get-chat-id
description: 새 텔레그램 봇 토큰의 TELEGRAM_CHAT_ID를 알아낼 때 사용. telegram_bot.py를 실행해 getUpdates 응답을 조회하고 결과를 해석해준다.
---

새 텔레그램 봇을 만들었거나 `TELEGRAM_CHAT_ID`를 다시 확인해야 할 때 다음 순서로 진행한다.

1. 사용자에게 텔레그램에서 대상 봇과 대화를 시작하고 아무 메시지(예: "안녕")를 보냈는지 확인한다.
   아직 안 보냈다면 먼저 보내달라고 안내한다.
2. `.env`에 `TELEGRAM_BOT_TOKEN`이 설정되어 있는지 확인한다.
3. `python ./telegram_bot.py`를 실행한다. 이 스크립트는 `getUpdates` API를 호출해 raw JSON을 출력한다.
4. 출력된 JSON에서 `result[].message.chat.id` 값을 찾아 사용자에게 알려주고,
   `.env`의 `TELEGRAM_CHAT_ID`에 그 값을 넣도록 안내한다.
5. `result`가 빈 배열이면 2번 단계(봇에게 메시지 보내기)부터 다시 확인하도록 안내한다.
