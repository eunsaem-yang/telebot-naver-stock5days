# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

빅데이터 파이썬 수업용 텔레그램 봇 프로젝트. 관심종목(`watchlist.csv`)의 현재가와 최근 15거래일
종가 추이 그래프를 하루 세 번(장이 열리는 평일 오전 10시/12시/2시) 자동으로 텔레그램 봇 API로
전송하는 것이 최종 목표다. GitHub Actions의 scheduled workflow로 실행되며, 사용자가 직접 스크립트를
실행할 필요가 없다.

스크립트가 여러 개로 나뉘어 있다:
- `notify_stock_price.py`: 하루 3회(10/12/2시) 실행. 관심종목 현재가를 텔레그램 텍스트 메시지로
  보내고, `price_history.json`에 저장된 최근 15일 종가 뒤에 오늘 분봉(`fetch_naver_intraday_minutes()`,
  네이버 API로 즉시 조회, 저장하지 않음)을 이어붙인 추이 그래프를 종목별로 `sendPhoto`로 전송한다.
  과거 종가 자체는 직접 재조회하지 않는다. 실제 로직은 `send_price_notification()` 함수로 감싸져
  있어, 텔레그램 트리거로 실행된 경우(`check_manual_trigger.yml`의 `notify` job)에도 동일한
  스크립트(`python notify_stock_price.py`)를 그대로 실행해 재사용한다.
- `collect_daily_close.py`: 하루 1회, 장마감 직후 실행. 그날의 최종 종가를 조회해
  `price_history.json`에 누적 저장(종목별 최근 15거래일치만 유지)한다. GitHub Actions 실행 환경은
  매번 초기화되므로 이 파일은 워크플로가 저장소에 직접 커밋해서 다음 실행 때 다시 읽는 방식으로
  상태를 유지한다.
- `check_manual_trigger.py`: 평일 장중 시간대(09~19시 KST)에 5분 간격으로 실행. 텔레그램에서
  수동 트리거가 있었는지(리플라이 키보드 버튼 `MANUAL_TRIGGER_TEXT` 또는 고정 메뉴 명령어
  `MANUAL_TRIGGER_COMMAND`="/notify" — 버튼이 붙은 메시지가 지워져도 명령어는 남아있음) `getUpdates`로
  확인만 한다. 실제 알림 전송(`send_price_notification()`)은 트리거가 감지됐을 때만 워크플로의
  별도 job이 맡는다 — 대부분의 폴링은 트리거 없이 끝나므로 무거운 의존성 설치를 아낀다. 하루 3회
  자동 스케줄(`notify.yml`)과는 별개로 동작하며 서로 대체하지 않는다. 한계와 배경은 `ROADMAP.md`
  "기능 4" 참고.
- `setup_telegram_button.py`: 로컬에서 1회만 실행하는 설정 스크립트. 텔레그램 채팅창에 리플라이
  키보드 버튼을 노출시키고, 고정 메뉴에 `/notify` 명령어를 등록한다.
- `stock_utils.py`: 여러 스크립트가 공유하는 함수(네이버 현재가 조회, 히스토리 읽기/쓰기, 텔레그램
  메시지·이미지·업데이트 조회, 그래프 생성, 거래일 판별) 모음.

시세 데이터는 네이버 금융 비공식 API(`m.stock.naver.com/api/stock/{code}/basic`) 하나로 통합되어
있다. 이 엔드포인트는 장중이면 실시간 체결가를, 장 마감 후 호출하면 그날의 최종 종가를
`marketStatus`/`closePrice` 필드로 그대로 돌려주기 때문에 "현재가 조회"와 "종가 기록"을 모두
처리할 수 있다.

**공공데이터포털(data.go.kr) API는 더 이상 사용하지 않는다.** 활용신청 승인 여부와 무관하게
`basDd` 날짜 필터가 항상 무시되고 고정된 데이터만 반환되는 문제를 확인했기 때문이다
(자세한 진단 과정과 원인은 `ROADMAP.md`의 "알려진 이슈" 절 참고).

거래일 판별은 `holidays`(`country="KR"`) 패키지로 주말/공휴일을 걸러낸다. API의 빈 응답으로
휴장일을 추측하던 방식보다 안정적이다.

## 실행 방법

```
python ./notify_stock_price.py       # 현재가 알림 (하루 3회 스케줄)
python ./collect_daily_close.py      # 종가 히스토리 수집 (하루 1회, 장마감 후)
python ./setup_telegram_button.py    # 수동 트리거 버튼 노출 (최초 1회만)
python ./check_manual_trigger.py     # 수동 트리거 버튼 확인 (평일 장중 5분 간격 스케줄)
```

의존성은 `requirements.txt`에 명시되어 있다 (`requests`, `python-dotenv`, `pandas`,
`matplotlib`, `holidays`).

## 자동 실행 (GitHub Actions)

`.github/workflows/notify.yml`(10:05/12:05/14:05시 KST, 평일), `.github/workflows/collect_close.yml`
(15:45 KST 장마감 직후, 평일), `.github/workflows/check_manual_trigger.yml`(평일 09~19시 KST,
5분 간격)이 각 스크립트를 자동 실행한다. cron은 UTC 기준으로 작성되어 있으므로 시간을 수정할
때는 KST와의 9시간 차이를 감안해야 한다. 정시(0분)는 GitHub Actions 스케줄이 몰리는 시간대라
지연·스킵되기 쉬우므로 일부러 정시를 피해 분(5분/45분/2~57분)을 지정했다. 다만 이 완화책에도
불구하고 스케줄이 통째로 미발동하는 경우가 관측됐다 — 자세한 내용은 `ROADMAP.md`의 "알려진 이슈"
참고. `collect_close.yml`은 실행 후 `price_history.json` 변경분을 저장소에 직접 커밋·푸시한다
(`permissions: contents: write` 필요). `check_manual_trigger.yml`은 `check`/`notify` 두 job으로
나뉘어 있다 — 대부분의 폴링은 트리거가 없어 `check` job(가벼운 의존성만 설치)에서 끝나고,
버튼이 눌렸을 때만 `notify` job(`requirements.txt` 전체 설치)이 이어서 실행된다.

## 환경 변수

`.env`에서 `python-dotenv`로 로드한다 (로컬 실행용). GitHub Actions에서는 저장소 Secrets에
동일한 이름으로 등록해서 사용한다. 필수 값: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- `TELEGRAM_BOT_TOKEN`: 텔레그램 `@BotFather`에서 `/newbot`으로 발급
- `TELEGRAM_CHAT_ID`: 봇에게 메시지를 보낸 뒤 `telegram_bot.py`를 실행해 `getUpdates` 응답에서 확인

네이버 API는 별도 인증키가 필요 없어 `PUBLIC_DATA_PORTAL_KEY`, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`는
더 이상 필요하지 않다.

**`.env`에는 실제 비밀키가 평문으로 들어있다. 절대 커밋하거나 출력/로그에 노출하지 말 것** (`.gitignore`에 등록됨).

## 코드 규칙

- 응답 언어: 한국어
- 코드 주석: 한국어
- 커밋 메시지: 한국어
- 변수명·함수명: 영어 (snake_case)
- 성공/실패/상태 로그는 이모지 접두사로 표시하는 기존 관례를 따를 것 (✅ 성공, ❌ 실패·오류, ⚠️ 경고·빈 데이터, 🚀 시작, 🔍 조회 중, 📋 목록, 🎉 최종 성공, 📊 헤더)

## 테스트/린트

테스트, 포매터는 설정되어 있지 않다. 문법 오류는 편집 후 자동으로 `python -m py_compile`이 실행되어 확인된다.
린트는 `ruff`(pip로 설치됨)를 사용한다:

```
python -m ruff check .
```
