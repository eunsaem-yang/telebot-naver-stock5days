# 관심종목 텔레그램 알림 봇 — 학생용 설치 가이드

관심종목의 현재가와 최근 종가 추이 그래프를 내 텔레그램으로 받아보는 실습 프로젝트입니다.
이 코드는 그대로 복사해서 실행하면 되고, 각자 자기 텔레그램 봇/챗ID만 발급받아 `.env`에
채워 넣으면 동일하게 동작합니다.

## 0. 준비물

- Python 3.11 이상
- 텔레그램 앱 (봇을 만들고 메시지를 받을 계정)

## 1. 코드 받기 & 라이브러리 설치

```
pip install -r requirements.txt
```

## 2. 내 텔레그램 봇 만들기

1. 텔레그램 앱에서 `@BotFather` 검색 → 대화 시작
2. `/newbot` 입력 → 안내에 따라 봇 이름 설정
3. 발급된 **토큰**(`123456:ABC-DEF...` 형태 문자열)을 복사해둡니다 → 이게 `TELEGRAM_BOT_TOKEN`

## 3. 내 CHAT_ID 알아내기

1. 방금 만든 내 봇에게 아무 메시지나 하나 보냅니다 (예: "안녕").
2. `.env`에 우선 `TELEGRAM_BOT_TOKEN`만 채운 뒤 아래 명령 실행:
   ```
   python telebot.py
   ```
3. 출력된 JSON에서 `"chat":{"id": 123456789, ...}` 부분의 숫자가 `TELEGRAM_CHAT_ID`입니다.

## 4. `.env` 작성

`.env.example`을 복사해 `.env`로 이름을 바꾸고, 위에서 얻은 두 값을 채워 넣습니다.

```
TELEGRAM_BOT_TOKEN=발급받은_토큰
TELEGRAM_CHAT_ID=알아낸_챗ID
```

**`.env`는 절대 커밋하지 마세요.** (`.gitignore`에 이미 등록되어 있습니다.)

## 5. 실행

```
python notify_stock_price.py       # 현재가 알림
python collect_daily_close.py      # 종가 히스토리 수집 (장마감 후)
```

`notify_stock_price.py`를 실행하면 관심종목(`watchlist.csv`에 정의됨) 현재가가 텔레그램
텍스트 메시지로 옵니다. 관심종목을 바꾸고 싶으면 `watchlist.csv`의 종목코드를 수정하세요.

## 자주 겪는 문제

- **아무 메시지도 안 옴 (오류도 없음)**: 오늘이 주말/공휴일이면 `is_trading_day()`가 실행을
  건너뜁니다. 평일 개장일에 다시 실행해보세요.
- **텍스트는 오는데 그래프가 안 옴**: `notify_stock_price.py`는 `price_history.json`에 저장된
  과거 종가를 읽기만 하고 직접 조회하지 않습니다. 그래프까지 받으려면 장마감(15:30 이후) 후에
  `collect_daily_close.py`를 최소 한 번 실행해서 히스토리를 먼저 쌓아야 합니다.
- **`UnicodeEncodeError`가 남 (Windows)**: 터미널 인코딩이 UTF-8이 아니어서 이모지 출력에서
  발생합니다. 아래처럼 실행하세요.
  ```
  $env:PYTHONIOENCODING="utf-8"; python notify_stock_price.py
  ```
- **`❌ [코드] 네이버 현재가 조회 실패`**: 네이버 비공식 API라 일시적으로 응답이 바뀌거나
  막힐 수 있습니다. 잠시 후 다시 시도해보세요.

## (선택) GitHub Actions로 완전 자동화하기

하루 세 번(10/12/14시) 자동으로 알림을 받고 싶다면:

1. 이 코드를 자신의 GitHub 저장소로 push
2. 저장소 Settings → Secrets and variables → Actions에서 `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID` 등록 (`.env` 값과 동일)
3. Actions 탭에서 `.github/workflows/notify.yml`, `collect_close.yml`이 자동으로 인식됨
4. 스케줄을 기다리지 않고 바로 테스트하려면 Actions 탭 → 워크플로 선택 → **Run workflow** 버튼

### 스케줄 실행이 안 됐을 때 (예: 평일 10시가 지났는데 메시지가 안 옴)

저장소가 private이면 브라우저 로그인 없이는 Actions 실행 기록을 볼 수 없으므로, `gh`(GitHub
CLI)를 설치해두면 터미널에서 바로 확인할 수 있습니다.

1. 설치 (Windows, PowerShell)
   ```
   winget install --id GitHub.cli
   ```
   설치 직후에는 현재 열려 있던 터미널이 새 PATH를 인식하지 못할 수 있습니다. 새 터미널을
   열거나(또는 PowerShell을 재시작), 그래도 `gh`를 못 찾으면 아래로 PATH를 새로고침합니다.
   ```
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
   ```
2. 로그인 (대화형 — 브라우저가 열림)
   ```
   gh auth login
   ```
   `GitHub.com` → `HTTPS` → `Login with a web browser` 순서로 선택합니다. 터미널에 뜬 일회용
   코드를 브라우저의 GitHub 로그인 페이지에 입력하고 Authorize하면 인증이 끝납니다.
3. 최근 실행 기록 확인
   ```
   gh run list --workflow=notify.yml --limit 10
   gh run view <run-id> --log
   ```
   워크플로가 `disabled_manually`/`disabled_inactivity` 상태인지도 확인하려면:
   ```
   gh api repos/<owner>/<repo>/actions/workflows --jq ".workflows[] | {name, state}"
   ```

흔한 원인:
- 저장소 Secrets에 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`가 등록되지 않음 (2번 항목 참고)
- 오늘이 `is_trading_day()` 기준 개장일이 아님 (주말/공휴일)
- 워크플로 파일이 아직 기본 브랜치(main)에 push되지 않음
- **cron이 정시(0분)로 걸려 있음**: GitHub 공식 문서에 따르면 매 정시는 스케줄 요청이 몰려
  지연되거나 그 주기를 통째로 건너뛰기 쉽다. 실제로 이 프로젝트에서도 `0 1,3,5 * * 1-5`로
  걸어뒀던 스케줄이 며칠간 아예 발동하지 않는 문제가 있었고, 분을 정시에서 5분 뒤로 미루는
  것(`5 1,3,5 * * 1-5` 등)으로 완화했다.

더 자세한 배경(왜 이런 구조인지)은 `CLAUDE.md`, `ROADMAP.md`를 참고하세요.
