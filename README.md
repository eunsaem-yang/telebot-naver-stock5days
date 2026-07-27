# 관심종목 텔레그램 알림 봇 — 학생용 설치 가이드

관심종목의 현재가와 최근 종가 추이 그래프를 내 텔레그램으로 받아보는 실습 프로젝트입니다.
이 코드는 그대로 복사해서 실행하면 되고, 각자 자기 텔레그램 봇/챗ID, 자기 Turso DB를 발급받아
`.env`에 채워 넣으면 동일하게 동작합니다.

과거 종가 히스토리는 Turso(클라우드 SQLite) DB에 저장됩니다. **텔레그램 봇 토큰/챗ID와
마찬가지로 Turso DB 접속 정보(`TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`)도 각자 자기 계정으로
직접 발급받아야 합니다** — 코드를 그대로 받아도 이 부분만큼은 자동화가 안 되고 아래 4번 단계를
직접 따라 해야 합니다.

## 0. 준비물

- Python 3.11 이상
- 텔레그램 앱 (봇을 만들고 메시지를 받을 계정)
- Turso 계정 (무료 — GitHub 계정으로 가입 가능)

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

## 4. 내 Turso DB 만들기

**이 단계는 자동화할 수 없습니다 — 각자 자기 Turso 계정에서 직접 DB를 만들고 접속 정보를
발급받아야 합니다.** (텔레그램 봇 토큰을 각자 발급받는 것과 동일한 이유입니다.)

1. Turso CLI 설치
   - Mac/Linux:
     ```
     curl -sSfL https://get.tur.so/install.sh | bash
     ```
   - Windows: 공식 설치 스크립트가 Mac/Linux용이라, WSL을 사용하거나 Mac이 있다면 그쪽에서
     이 단계(1~4)만 진행한 뒤 발급된 두 값을 Windows의 `.env`에 그대로 복사해도 됩니다 —
     한 번 발급받은 URL/토큰은 어느 OS에서든 동일하게 쓸 수 있습니다.
2. 가입/로그인 (대화형 — 브라우저가 열림, GitHub 계정으로 진행)
   - Turso 계정이 **처음**이면:
     ```
     turso auth signup
     ```
   - **이미** 계정이 있으면:
     ```
     turso auth login
     ```
   - 완료되면 아래로 확인:
     ```
     turso auth whoami
     ```
     본인 계정명이 출력되면 성공입니다.
3. DB 생성
   ```
   turso db create telebot-stock
   ```
4. 접속 정보 확인 — 각각 출력되는 값이 `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`입니다.
   ```
   turso db show telebot-stock --url
   turso db tokens create telebot-stock
   ```

### 2번(가입/로그인)이 멈추거나 타임아웃될 때

브라우저는 열렸는데 터미널이 "Waiting for authentication..."에서 멈추거나
`Error: authentication timed out, try again`가 뜨는 경우가 있습니다. CLI가 브라우저 응답을
받으려고 로컬호스트로 열어둔 포트를, 방화벽이나 보안 소프트웨어가 막아서 생기는 문제입니다.
이럴 땐 `--headless` 옵션을 붙여 재시도하세요.

```
turso auth signup --headless      # 또는 turso auth login --headless
```

이 방식은 로컬호스트 콜백을 아예 쓰지 않습니다. 대신:

1. 터미널에 출력된 URL을 브라우저에서 엽니다.
2. GitHub 로그인/가입을 완료하면 웹페이지에 "Access Token Generated"라는 화면과 함께
   `turso config set token "eyJ..."` 형태의 명령어가 뜹니다.
3. **그 명령어를 통째로 복사해서 본인 터미널에 직접 붙여넣고 실행**하세요.

> ⚠️ **주의**: 이 토큰은 Turso **계정 전체**를 제어할 수 있는 값입니다(비밀번호와 같은 급).
> 절대 카톡·디스코드·과제 제출물·AI 채팅 등 어디에도 붙여넣지 말고, 본인 터미널에서만
> 다루세요. 실수로 어딘가에 노출됐다면 GitHub 로그인 기반 계정이므로
> https://github.com/settings/applications 에서 Turso(또는 Clerk) 항목을 찾아 Revoke하면
> 그 인증 경로를 끊을 수 있습니다.

`turso auth whoami`로 로그인이 됐는지 다시 확인한 뒤 3번(DB 생성)으로 이어가면 됩니다.

### DB를 다시 만들고 싶을 때 (실수로 잘못 만들었거나 초기화하고 싶을 때)

기존 DB를 지우고 같은 이름으로 새로 만들 수 있습니다. 데이터(최근 15거래일 종가)만 사라질 뿐,
`collect_daily_close.py`가 다음 실행 때부터 다시 쌓아주므로 걱정 없이 진행해도 됩니다.

```
turso db list                     # 현재 DB 목록 확인
turso db destroy telebot-stock    # 기존 DB 삭제 (확인 메시지에 y 입력)
turso db create telebot-stock     # 같은 이름으로 재생성
turso db show telebot-stock --url        # 새 URL 확인
turso db tokens create telebot-stock     # 새 토큰 발급
```

새로 나온 URL/토큰으로 `.env`의 `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` 두 줄을 덮어쓰면
됩니다.

## 5. `.env` 작성

`.env.example`을 복사해 `.env`로 이름을 바꾸고, 위에서 얻은 값들을 채워 넣습니다.

```
TELEGRAM_BOT_TOKEN=발급받은_토큰
TELEGRAM_CHAT_ID=알아낸_챗ID
TURSO_DATABASE_URL=turso_db_show로_확인한_URL
TURSO_AUTH_TOKEN=turso_db_tokens_create로_발급한_토큰
```

**`.env`는 절대 커밋하지 마세요.** (`.gitignore`에 이미 등록되어 있습니다.)

## 6. 실행

```
python notify_stock_price.py       # 현재가 알림
python collect_daily_close.py      # 종가 히스토리 수집 (장마감 후)
```

`notify_stock_price.py`를 실행하면 관심종목(`watchlist.csv`에 정의됨) 현재가가 텔레그램
텍스트 메시지로 옵니다. 관심종목을 바꾸고 싶으면 `watchlist.csv`의 종목코드를 수정하세요.

### 관심종목을 모바일에서 바꾸고 싶을 때

로컬에서 파일을 열어 고쳐도 되지만, GitHub 웹(모바일 브라우저에서도 가능)에서 직접 편집할
수도 있습니다:

1. GitHub에서 본인 저장소 → `watchlist.csv` 파일 열기
2. 연필(편집) 아이콘 탭. 모바일 화면에서 안 보이면 브라우저를 **"데스크톱 사이트"로 전환**
   하거나(가장 확실함), 파일 화면의 **"···" 더보기 메뉴** 안에서 "Edit file"을 찾아보세요.
3. `종목코드,종목명` 형식으로 줄을 추가/수정합니다 (예: `035420,NAVER`). 종목코드 앞자리
   0은 그대로 둬도 됩니다.
4. "Commit changes" → **"Commit directly to the main branch"** 선택 후 저장합니다.

**주의**: GitHub에서 이렇게 바로 편집하면 GitHub Actions(하루 3회 자동 알림, 대시보드 등)에는
다음 실행 때 바로 반영됩니다 — 실행할 때마다 항상 최신 `main`을 그대로 가져다 쓰기 때문입니다.
하지만 **로컬 컴퓨터에서 직접 스크립트를 실행하는 경우**에는 자동으로 반영되지 않습니다. git은
GitHub(원격 저장소)과 내 컴퓨터(로컬 저장소)를 서로 독립된 별개의 사본으로 관리하기 때문에,
GitHub에서 바꾼 내용을 로컬로 가져오려면 아래 명령을 먼저 실행해야 합니다:
```
git pull origin main
```
그 후에 로컬의 `watchlist.csv`도 GitHub과 동일한 내용이 됩니다.

## 자주 겪는 문제

- **아무 메시지도 안 옴 (오류도 없음)**: 오늘이 주말/공휴일이면 `is_trading_day()`가 실행을
  건너뜁니다. 평일 개장일에 다시 실행해보세요.
- **그래프에 점이 하나뿐임 (현재가만 찍힘)**: `notify_stock_price.py`는 Turso DB(`price_history`
  테이블)에 저장된 과거 종가를 읽기만 하고 직접 조회하지 않습니다. `collect_daily_close.py`가
  아직 한 번도 실행되지 않았거나 그 종목의 히스토리가 없으면, 저장된 과거 종가 없이 현재가
  하나만으로 그래프를 그립니다. 장마감(15:30 이후) 후 `collect_daily_close.py`를 실행해
  히스토리를 쌓으면 이후부터는 추이 그래프로 채워집니다.
- **`❌ Turso DB에서 종가 히스토리를 읽지 못했습니다` / `저장 실패`**: 대부분 `TURSO_DATABASE_URL`
  또는 `TURSO_AUTH_TOKEN`이 `.env`에 없거나 잘못된 경우입니다. "4. 내 Turso DB 만들기" 단계를
  다시 확인하세요. 이 오류가 나도 스크립트 자체가 멈추지는 않고(현재가 메시지는 정상 전송),
  히스토리/추이 그래프만 비어 있게 됩니다.
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

2. **Secrets 4개 등록** — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TURSO_DATABASE_URL`,
   `TURSO_AUTH_TOKEN`을 `.env`에 있는 값과 동일하게 등록합니다. 이 등록도 자동화 대상이 아니라
   **각자 자기 저장소에 직접** 해야 합니다 — 이 중 하나라도 빠지면 해당 워크플로가 실패합니다.

   **방법 A — 웹 화면에서 등록 (설치 없이 가능)**
   1. 자기 GitHub 저장소 페이지로 이동
   2. 상단 **Settings** 탭 클릭 (저장소 소유자만 보입니다 — 안 보이면 fork/push가
      제대로 안 된 것일 수 있음)
   3. 왼쪽 메뉴에서 **Secrets and variables → Actions** 클릭
   4. **New repository secret** 버튼 클릭
   5. **Name**에 `TELEGRAM_BOT_TOKEN`, **Secret**에 `.env`의 해당 값을 그대로 붙여넣고
      **Add secret**
   6. 4~5번을 `TELEGRAM_CHAT_ID`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`에도 반복 —
      총 4개가 목록에 뜨면 완료 (값 자체는 등록 후 다시 볼 수 없고 이름만 보입니다 —
      정상입니다)

   **방법 B — `gh`(GitHub CLI)로 등록 (설치돼 있다면 더 빠름)**
   ```
   gh secret set TELEGRAM_BOT_TOKEN
   gh secret set TELEGRAM_CHAT_ID
   gh secret set TURSO_DATABASE_URL
   gh secret set TURSO_AUTH_TOKEN
   ```
   각 명령을 실행하면 값을 입력하라는 프롬프트가 뜹니다 — `.env`의 값을 붙여넣고 Enter,
   그다음 (Mac/Linux는 `Ctrl+D`, Windows는 `Ctrl+Z` 후 Enter)로 마칩니다. 등록 목록은
   `gh secret list`로 확인할 수 있습니다(여기서도 값은 안 보이고 이름만 보임).
   `gh` 설치 방법은 아래 "스케줄 실행이 안 됐을 때" 절 참고.

3. Actions 탭에서 `.github/workflows/notify.yml`, `collect_close.yml`이 자동으로 인식됨
4. 스케줄을 기다리지 않고 바로 테스트하려면 Actions 탭 → 워크플로 선택 → **Run workflow** 버튼
   → 실행 로그에 `✅`/`🎉`가 뜨면 Secrets 4개가 모두 제대로 등록된 것입니다. `❌`가 뜨면 어느
   Secret이 빠졌는지 로그 메시지로 확인하세요 (예: Turso 관련 에러면 Turso 두 값을 다시 확인).

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
- 저장소 Secrets에 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`/`TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`
  중 하나라도 등록되지 않음 (2번 항목 참고) — Turso 값이 빠지면 알림 메시지는 가지만 추이
  그래프가 현재가 한 점만 찍힌 채로 옵니다.
- 오늘이 `is_trading_day()` 기준 개장일이 아님 (주말/공휴일)
- 워크플로 파일이 아직 기본 브랜치(main)에 push되지 않음
- **cron이 정시(0분)로 걸려 있음**: GitHub 공식 문서에 따르면 매 정시는 스케줄 요청이 몰려
  지연되거나 그 주기를 통째로 건너뛰기 쉽다. 실제로 이 프로젝트에서도 `0 1,3,5 * * 1-5`로
  걸어뒀던 스케줄이 며칠간 아예 발동하지 않는 문제가 있었고, 분을 정시에서 5분 뒤로 미루는
  것(`5 1,3,5 * * 1-5` 등)으로 완화했다.

더 자세한 배경(왜 이런 구조인지)은 `CLAUDE.md`, `ROADMAP.md`를 참고하세요.
