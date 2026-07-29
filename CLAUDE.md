# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

빅데이터 파이썬 수업용 주식 정보 프로젝트. 관심종목(`watchlist.csv`)의 현재가와 최근 15거래일
종가 추이를 확인하는 두 가지 경로를 제공한다. 관심종목 목록은 사용자가 수시로 직접 편집하는
가변 입력이므로, 종목 수나 구성이 고정이라고 가정하면 안 된다 — 방금 추가된 종목은 다음
`collect_daily_close.py` 실행 전까지 종가 히스토리가 0건이라는 점도 늘 염두에 둬야 한다.

- **push (텔레그램)**: 하루 세 번(장이 열리는 평일 오전 10시/12시/2시) 자동으로 텔레그램 봇 API로
  전송. GitHub Actions의 scheduled workflow로 실행되며, 사용자가 직접 스크립트를 실행할 필요가 없다.
- **pull (Streamlit 대시보드)**: `dashboard.py`를 Streamlit Community Cloud에 상시 배포해두고,
  사용자가 원할 때 웹페이지를 열어 즉시 확인한다. 별도 스케줄이 필요 없다.

두 경로 모두 같은 데이터·저장소(Turso DB, 아래 참고)를 공유한다. 원래는 텔레그램 push만 최종
목표였지만, GitHub Actions `schedule` 트리거가 예정 시각에 아예 실행 기록조차 남기지 않고
통째로 스킵되는 신뢰성 한계를 겪으며 "텔레그램으로 받는다"는 특정 구현 방식이 아니라 "원하는
시점에 데이터를 확인한다"가 진짜 목적임을 재확인해 pull 경로를 추가했다 — 스케줄이 가끔
스킵돼도 대시보드를 열면 최신 데이터가 보이므로 치명적이지 않다. 이 재검토 과정은
`ROADMAP.md`의 "전략적 재검토" 절 참고.

스크립트가 여러 개로 나뉘어 있다:
- `notify_stock_price.py`: 하루 3회(10/12/2시) 실행. 텍스트 메시지는 "내 관심종목 현재가" 헤더 +
  대표 종목 1개로 계산한 추이 설명(`describe_price_trend()`, 종목마다 거의 같은 문구라 반복 안 함)
  만 보낸다. 종목별 상세(가격·등락)는 사진 캡션에 담아 종목별 `sendPhoto`로 전송한다 — 캡션은
  종목명을 `<b>` 굵게(`send_telegram_photo()`가 `parse_mode="HTML"`로 보냄), 다음 줄에 4칸
  들여쓴 `format_rate_badge()`(가격+세모 이모지+등락률)를 붙인다. 그래프는 Turso DB에 저장된
  최근 15일 종가 뒤에 오늘 분봉(`fetch_naver_intraday_minutes()`, 네이버 API로 즉시 조회,
  저장하지 않음)을 이어붙여 그리되, 분봉/현재가 조회에 성공했을 때만 DB의 "오늘 날짜" 항목을
  제외하고 그린다(`build_price_chart()` 내부 dedup) — 장마감 후~다음 장 시작 전처럼 분봉도
  없고 장도 닫혀있으면(`is_open=False`) 현재가를 아예 넘기지 않아(`resolve_today_price()`),
  필연적으로 마지막 종가와 같은 값이 "오늘" 점으로 중복 표시되는 걸 막는다. 단 **그 종목의
  종가 히스토리가 하나도 없으면 이 "중복 방지" 예외를 적용하지 않고 현재가를 살린다** —
  중복될 종가 자체가 없는데 현재가마저 버리면 그릴 점이 하나도 남지 않아 축과 격자만 있는
  빈 그래프가 만들어지기 때문이다(새로 추가한 종목이나 `collect_daily_close.py` 최초 미실행
  시 실제로 발생했다). 과거 종가 자체는 직접 재조회하지 않는다.
  실제 로직은 `send_price_notification()` 함수로 감싸져 있어, 텔레그램 트리거로 실행된
  경우(`check_manual_trigger.yml`의 `notify` job)에도 동일한 스크립트(`python
  notify_stock_price.py`)를 그대로 실행해 재사용한다.
- `collect_daily_close.py`: 하루 1회, 장마감 직후 실행. 그날의 최종 종가를 조회해 Turso DB의
  `price_history` 테이블에 누적 저장(종목별 최근 15거래일치만 유지, 오래된 행은 자동 삭제)한다.
  저장할 날짜는 실행 시각(`datetime.now()`)이 아니라 네이버 응답의 체결 시각
  (`localTradedAt` → `fetch_naver_current_price()`의 `traded_at`)에서 뽑는다 — 실행 시각을
  쓰면 GitHub Actions 스케줄이 지연돼 자정을 넘겨 실행됐을 때 전날 종가가 다음날 날짜로
  저장되는데(실제로 발생했다), 체결 시각은 언제 조회하든 그 종목이 마지막으로 거래된 날을
  가리키므로 항상 올바른 거래일에 저장된다. 종목마다 따로 계산하므로 거래정지 등으로 마지막
  체결일이 다른 종목도 각자 맞는 날짜로 기록된다. 예전에는 JSON 파일(`price_history.json`)을
  저장소에 직접 커밋해 GitHub Actions의 상태 없는 실행 환경을 우회했지만, Turso DB 자체가
  영속 저장소 역할을 하므로 더 이상 git 커밋이 필요 없다 (`ROADMAP.md` "Turso 마이그레이션"
  절 참고).
- `dashboard.py`: Streamlit 대시보드. `read_watchlist()`/`load_price_history()`/
  `fetch_naver_current_price()`/`fetch_naver_intraday_minutes()`/`resolve_today_price()`/
  `dedupe_daily_closes()`/`build_price_chart()`를 `notify_stock_price.py`와 그대로 공유해서
  쓴다 — push/pull 두 경로가 같은 함수·같은 DB를 바라보므로 어느 쪽으로 확인해도 같은 내용을
  본다(오늘 날짜 dedup, current_price=None 처리 등 위 `notify_stock_price.py` 설명의 그래프
  관련 내용도 동일하게 적용됨). 종목명(코드)·가격·등락은 `st.metric()` 대신 `st.markdown()` +
  인라인 CSS로 직접 그려 글자 크기를 자유롭게 조정하고, 등락 색상은 **상승=빨강/하락=초록**으로
  지정한다 — Streamlit `st.metric()` 기본값(상승=초록/하락=빨강)이 한국 증시 관례와 반대라
  의도적으로 뒤집은 것. 색상이 필요해서 등락 표기만은 텔레그램용 `format_rate_badge()`를 쓰지
  않고 따로 그린다(아래 `stock_utils.py` 문단 참고). 추이 설명도 종목마다 반복하지 않고 제목
  아래 `st.empty()` 자리표시자로 한 번만 채운다. 로컬 실행은 `python -m streamlit run
  dashboard.py`.
- `check_manual_trigger.py`: 평일 장중 시간대(09~19시 KST)에 5분 간격으로 실행. 텔레그램에서
  수동 트리거가 있었는지(리플라이 키보드 버튼 `MANUAL_TRIGGER_TEXT` 또는 고정 메뉴 명령어
  `MANUAL_TRIGGER_COMMAND`="/notify" — 버튼이 붙은 메시지가 지워져도 명령어는 남아있음) `getUpdates`로
  확인만 한다. 실제 알림 전송(`send_price_notification()`)은 트리거가 감지됐을 때만 워크플로의
  별도 job이 맡는다 — 대부분의 폴링은 트리거 없이 끝나므로 무거운 의존성 설치를 아낀다. 하루 3회
  자동 스케줄(`notify.yml`)과는 별개로 동작하며 서로 대체하지 않는다. 한계와 배경은 `ROADMAP.md`
  "기능 4" 참고.
- `telebot.py`: 로컬에서 1회만 실행하는 설정 스크립트. 봇에게 보낸 메시지를 `getUpdates`로
  조회해 `TELEGRAM_CHAT_ID`를 알아내는 데 쓴다 (최초 봇 설정 시 1회, `CURRICULUM.md` 5주차 참고).
- `setup_telegram_button.py`: 로컬에서 1회만 실행하는 설정 스크립트. 텔레그램 채팅창에 리플라이
  키보드 버튼을 노출시키고, 고정 메뉴에 `/notify` 명령어를 등록한다.
- `stock_utils.py`: 여러 스크립트가 공유하는 함수(네이버 현재가 조회, Turso DB 히스토리
  읽기/쓰기, 텔레그램 메시지·이미지·업데이트 조회, 그래프 생성, 거래일 판별) 모음. 그중
  `describe_price_trend()`(추이 설명 문구), `resolve_today_price()`("오늘" 점으로 쓸 현재가
  결정), `dedupe_daily_closes()`(오늘 날짜 종가 걸러내기)는 텔레그램과 대시보드가 **실제로
  같이 쓰는** 함수다 — push/pull 어느 쪽으로 봐도 그래프에 찍히는 점과 문구 속 "최근 N일"
  숫자가 일치해야 하므로 공용으로 뺐다. `describe_price_trend()`는 `daily_closes` 유무를
  먼저 확인해 분기하는데, 종가 히스토리가 없으면 "최근 0일"이라는 이상한 문구 대신 "오늘
  현재가 추이 (종가 히스토리 누적 전)"을 돌려준다.
  반면 `format_rate_badge()`(가격+세모 이모지+등락률 문자열)는 공용 함수가 아니라 **텔레그램
  사진 캡션 전용**이다 — 대시보드는 등락에 색상이 들어간 HTML(`<span style="color:...">`)이
  필요해 인라인으로 따로 구현했고, 그래서 기호도 다르다(텔레그램 `🔺`/`▼`/`▫️` vs 대시보드
  `▲`/`▼`/`▫` + 색상). 하나로 합치려면 색상 인자·HTML 모드 플래그 같은 분기를 함수 안에
  들여야 해서 오히려 복잡해지므로, 분리된 상태를 의도적으로 유지한다.
  `update_price_history()`는 `client` 인자를 선택적으로 받는다 — 안 넘기면 스스로 Turso
  클라이언트를 만들고 닫지만, `collect_daily_close.py`처럼 종목을 여러 개 순회하며 반복
  호출할 때는 `get_turso_client()`로 미리 만든 클라이언트를 넘겨 재사용해 종목마다 새
  연결을 맺지 않는다(관심종목 수가 늘어날수록 이득이 커지는 최적화).

과거 종가 히스토리는 `price_history.json` 파일 대신 **Turso**(libSQL 기반 서버리스 SQLite,
`libsql-client`로 연동)의 `price_history` 테이블에 저장한다. 자세한 배경은 아래 "환경 변수"와
`ROADMAP.md`의 "Turso 마이그레이션" 절 참고.

시세 데이터는 네이버 금융 비공식 API(`m.stock.naver.com/api/stock/{code}/basic`) 하나로 통합되어
있다. 이 엔드포인트는 장중이면 실시간 체결가를, 장 마감 후 호출하면 그날의 최종 종가를
`marketStatus`/`closePrice` 필드로 그대로 돌려주기 때문에 "현재가 조회"와 "종가 기록"을 모두
처리할 수 있다. `fetch_naver_current_price()`는 응답을 받았더라도 가격을 숫자로 읽지 못하면
(재시도 후에도 실패하면) 0원이 담긴 dict가 아니라 `None`을 반환해, 호출부 세 곳이 전부 "조회
실패"로 똑같이 처리하게 한다 — 0원이 그대로 흘러가면 텔레그램·대시보드에 "0원"이 멀쩡한 가격처럼
표시되고 Turso 히스토리까지 오염되므로, 값이 만들어지는 지점에서 아예 막는다.

**공공데이터포털(data.go.kr) API는 더 이상 사용하지 않는다.** 활용신청 승인 여부와 무관하게
`basDd` 날짜 필터가 항상 무시되고 고정된 데이터만 반환되는 문제를 확인했기 때문이다
(자세한 진단 과정과 원인은 `ROADMAP.md`의 "알려진 이슈" 절 참고).

거래일 판별은 `holidays`(`country="KR"`) 패키지로 주말/공휴일을 걸러낸다. API의 빈 응답으로
휴장일을 추측하던 방식보다 안정적이다.

## 실행 방법

```
python ./notify_stock_price.py            # 현재가 알림 (하루 3회 스케줄)
python ./collect_daily_close.py           # 종가 히스토리 수집 (하루 1회, 장마감 후)
python ./telebot.py                       # TELEGRAM_CHAT_ID 확인 (최초 1회만)
python ./setup_telegram_button.py         # 수동 트리거 버튼 노출 (최초 1회만)
python ./check_manual_trigger.py          # 수동 트리거 버튼 확인 (평일 장중 5분 간격 스케줄)
python -m streamlit run dashboard.py      # Pull 방식 대시보드 (원할 때 직접 실행/접속)
```

의존성은 `requirements.txt`에 명시되어 있다 (`requests`, `python-dotenv`, `pandas`,
`matplotlib`, `holidays`, `streamlit`, `libsql-client`).

Streamlit Community Cloud에 배포해둔 대시보드는 `origin/main` 푸시를 감지해 보통 몇십 초~1분
내로 자동 재배포되지만, 반영이 늦거나 안 될 때는 https://share.streamlit.io 에 직접 로그인해서
앱 목록에서 해당 앱을 찾으면 Reboot에 접근할 수 있다.

## 자동 실행 (GitHub Actions + cron-job.org 이중 트리거)

`.github/workflows/notify.yml`(10:05/12:05/14:05시 KST, 평일), `.github/workflows/collect_close.yml`
(15:45 KST 장마감 직후, 평일), `.github/workflows/check_manual_trigger.yml`(평일 09~19시 KST,
5분 간격)이 각 스크립트를 자동 실행한다. cron은 UTC 기준으로 작성되어 있으므로 시간을 수정할
때는 KST와의 9시간 차이를 감안해야 한다. 정시(0분)는 GitHub Actions 스케줄이 몰리는 시간대라
지연·스킵되기 쉬우므로 일부러 정시를 피해 분(5분/45분/2~57분)을 지정했다. 다만 이 완화책에도
불구하고 스케줄이 통째로 미발동하는 경우가 관측됐다 — 자세한 내용은 `ROADMAP.md`의 "알려진 이슈"
참고. `collect_close.yml`은 실행 후 Turso DB에 직접 저장하므로(별도의 저장소 커밋 불필요)
`permissions: contents: write`가 필요 없다 — Turso 마이그레이션 이전에는 `price_history.json`
변경분을 저장소에 커밋·푸시하는 방식이었다. `check_manual_trigger.yml`은 `check`/`notify` 두 job으로
나뉘어 있다 — 대부분의 폴링은 트리거가 없어 `check` job(가벼운 의존성만 설치)에서 끝나고,
버튼이 눌렸을 때만 `notify` job(`requirements.txt` 전체 설치)이 이어서 실행된다.

GitHub Actions 네이티브 `schedule`이 예정 시각에 통째로 스킵되는 신뢰성 문제 때문에, **세 워크플로
모두**(`notify.yml`/`collect_close.yml`/`check_manual_trigger.yml`)에 대해 **cron-job.org**에 같은
시각의 외부 작업을 별도로 등록해 **이중으로 트리거**하고 있다. 방식은 cron-job.org가 GitHub API의
`.../actions/workflows/<파일명>/dispatches` 엔드포인트를 PAT(`Authorization: Bearer <PAT>`)로
POST하는 것이고, 그러면 `workflow_dispatch` 이벤트로 실행된다 — 그래서 세 워크플로 모두
`workflow_dispatch:` 트리거를 갖고 있어야 한다(빠지면 그 워크플로만 외부 트리거를 못 받는다).

**운영상 주의: 실행 시각을 바꿀 때는 `.github/workflows/*.yml`의 cron과 cron-job.org 쪽 작업
스케줄을 둘 다 고쳐야 한다.** 한쪽만 고치면 의도와 다른 시각에 이중으로 돌거나 아예 안 돈다.
이때 표기 기준이 서로 다르다는 점도 주의할 것 — 워크플로의 cron은 UTC인 반면, cron-job.org 쪽
작업은 Timezone이 `Asia/Seoul`로 설정돼 있어 KST 시각을 그대로 적는다. PAT 발급부터 작업 등록,
검증, 401 트러블슈팅까지의 자세한 절차는 `ROADMAP.md`의 "cron-job.org 이중 트리거 실제 도입",
"collect_close.yml에 cron-job.org 이중 트리거 추가" 절 참고.

### 알림이 안 왔을 때 원인 찾는 법

"텔레그램이 안 왔다"는 사실 하나만으로는 원인을 알 수 없다. 스케줄 스킵·네이버 차단·텔레그램
장애·공휴일이 겉으로는 모두 똑같이 "조용함"으로만 보이기 때문이다. **GitHub Actions 실행 결과를
같이 봐야** 구분된다 (저장소 → Actions 탭 → "관심종목 현재가 알림"):

| 텔레그램 | Actions | 해석 |
|---|---|---|
| 안 옴 | **실행 기록이 아예 없음** | 스케줄이 통째로 스킵됨. 이 저장소에서 **가장 흔한 원인**이고, cron-job.org 이중 트리거를 걸어 둔 이유이기도 하다 |
| 안 옴 | **빨간 ✗ (실패)** | 실행은 됐는데 아무것도 못 했다. 로그의 `❌` 문구로 네이버 조회 실패인지 텔레그램 전송 실패인지 구분한다 |
| 안 옴 | **녹색 ✓ (성공)** | 공휴일이라 보낼 게 없었던 정상 종료다 |

세 번째 줄이 "공휴일 하나"로 확정되는 건 `notify_stock_price.py`/`collect_daily_close.py`가
**아무것도 못 했으면 반드시 종료 코드 1로 끝나기** 때문이다. 예전에는 조회에 전부 실패하거나
텔레그램 전송에 전부 실패해도 0으로 끝나 Actions에 녹색 체크만 남았고, 그 경우와 공휴일이
구분되지 않았다 — 녹색 체크가 "정상 동작 중"이라고 잘못 알려주던 셈이라 침묵보다 나빴다.
휴장일·부분 실패(일부 종목만 조회/전송 실패)는 정상이므로 0을 유지한다.

> 이 표는 `notify_stock_price.py` 맨 위 docstring에도 같은 내용이 있다(디버깅할 때 코드부터
> 여는 경우를 위해서다). **한쪽을 고치면 다른 쪽도 같이 고칠 것.**

## 환경 변수

`.env`에서 `python-dotenv`로 로드한다 (로컬 실행용). GitHub Actions에서는 저장소 Secrets에,
Streamlit Community Cloud에서는 앱 Settings → Secrets에 동일한 이름으로 등록해서 사용한다.
필수 값: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`.
- `TELEGRAM_BOT_TOKEN`: 텔레그램 `@BotFather`에서 `/newbot`으로 발급
- `TELEGRAM_CHAT_ID`: 봇에게 메시지를 보낸 뒤 `telebot.py`를 실행해 `getUpdates` 응답에서 확인
- `TURSO_DATABASE_URL`: `turso db create <db이름>` 후 `turso db show <db이름> --url`로 확인
  (`libsql://...` 형태)
- `TURSO_AUTH_TOKEN`: `turso db tokens create <db이름>`로 발급

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
린트는 `ruff`를 사용한다. 다만 환경에 따라 설치돼 있지 않을 수 있고(아래 명령이
`No module named ruff`로 끝나면 그 경우다), 그럴 때는 `pip install ruff`로 먼저 설치한다:

```
python -m ruff check .
```
