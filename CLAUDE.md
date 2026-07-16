# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

빅데이터 파이썬 수업용 텔레그램 봇 프로젝트. 현재 `telebot_krx_stock.py`는 대한민국 정부에서 운영하는 공공데이터포털(data.go.kr)을 활용해 금융위원회가 제공하는 KRX 주식 데이터를 가져와 결과를 하나의 메시지로 만들어 텔레그램 봇 API(`api.telegram.org/bot<TOKEN>/sendMessage`)로 전송하는 대화형 CLI 스크립트다.

데이터는 `watchlist.csv`(종목코드 목록)를 읽어 실시간 주가를 조회하고 텔레그램으로 전송합니다. 공공데이터포털(금융위원회 주식시세) API는 특정 주말이나 공휴일 날짜를 지정해서 요청하면 데이터가 아예 비어 있는([]) 응답을 반환합니다.
이를 해결하기 위해, 지정한 날짜(basDd)에 데이터가 없다면 
데이터가 발견될 때까지 하루씩 과거로 돌아가며(최대 10일 전까지) 자동으로 재요청을 시도합니다. 
이렇게 하면 주말이나 공휴일, 혹은 당일 장 마감 전 시간대에 코드를 실행하더라도 
가장 최근에 마감된 최종 영업일 기준의 종가를 안전하게 받아올 수 있습니다.

## 실행 방법

```
python ./telebot_krx_stock.py
```

의존성은 `requests`, `python-dotenv`이며 별도 `requirements.txt`는 없다(수동 설치됨).

## 환경 변수

`.env`에서 `python-dotenv`로 로드한다. 필수 값: `PUBLIC_DATA_PORTAL_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- `PUBLIC_DATA_PORTAL_KEY`: data.go.kr(공공데이터포털)에서 금융위원회_주식시세정보 서비스 신청 후 발급받는 디코딩 서비스키
- `TELEGRAM_BOT_TOKEN`: 텔레그램 `@BotFather`에서 `/newbot`으로 발급
- `TELEGRAM_CHAT_ID`: 봇에게 메시지를 보낸 뒤 `telegram_bot.py`를 실행해 `getUpdates` 응답에서 확인

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
