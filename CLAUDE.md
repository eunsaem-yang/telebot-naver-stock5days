# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

빅데이터 파이썬 수업용 텔레그램 봇 프로젝트. 관심종목(`watchlist.csv`)의 현재가와 최근 15거래일
종가 추이 그래프를 하루 세 번(장이 열리는 평일 오전 10시/12시/2시) 자동으로 텔레그램 봇 API로
전송하는 것이 최종 목표다. GitHub Actions의 scheduled workflow로 실행되며, 사용자가 직접 스크립트를
실행할 필요가 없다.

스크립트가 두 개로 나뉘어 있다:
- `notify_stock_price.py`: 하루 3회(10/12/2시) 실행. 관심종목 현재가를 텔레그램 텍스트 메시지로
  보내고, `price_history.json`에 저장된 최근 15일 종가 뒤에 현재가를 붙여 종목별 추이 그래프를
  `sendPhoto`로 전송한다. 과거 종가를 직접 재조회하지 않는다.
- `collect_daily_close.py`: 하루 1회, 장마감 직후 실행. 그날의 최종 종가를 조회해
  `price_history.json`에 누적 저장(종목별 최근 15거래일치만 유지)한다. GitHub Actions 실행 환경은
  매번 초기화되므로 이 파일은 워크플로가 저장소에 직접 커밋해서 다음 실행 때 다시 읽는 방식으로
  상태를 유지한다.
- `stock_utils.py`: 두 스크립트가 공유하는 함수(네이버 현재가 조회, 히스토리 읽기/쓰기, 텔레그램
  전송, 그래프 생성, 거래일 판별) 모음.

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
```

의존성은 `requirements.txt`에 명시되어 있다 (`requests`, `python-dotenv`, `pandas`,
`matplotlib`, `holidays`).

## 자동 실행 (GitHub Actions)

`.github/workflows/notify.yml`(10/12/14시 KST, 평일)과 `.github/workflows/collect_close.yml`
(15:40 KST 장마감 직후, 평일)이 각 스크립트를 자동 실행한다. cron은 UTC 기준으로 작성되어
있으므로 시간을 수정할 때는 KST와의 9시간 차이를 감안해야 한다. `collect_close.yml`은 실행 후
`price_history.json` 변경분을 저장소에 직접 커밋·푸시한다 (`permissions: contents: write` 필요).

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
