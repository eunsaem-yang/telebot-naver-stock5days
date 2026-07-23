# 관심종목 텔레그램 알림 봇 — 수업 기획서 (Turso DB 연동 포함)

이 프로젝트를 처음부터 Turso DB 연동까지 완성하는 것을 목표로 한 13주 과정 기획서다.
실습 대상 코드는 `notify_stock_price.py`, `collect_daily_close.py`, `check_manual_trigger.py`,
`setup_telegram_button.py`, `stock_utils.py`, `dashboard.py`, `.github/workflows/*.yml`이며,
최종적으로 `price_history.json` 파일 저장 방식을 Turso DB로 전환하는 것까지 포함한다.

(원래 12주로 설계했으나, 실제 구현 과정에서 나온 텔레그램 수동 트리거 기능을 반영하며 13주로
늘렸다 — 아래 "설계 의도" 마지막 문단 참고.)

**설계 배경 (2026-07-22 갱신)**: 실제 구현을 진행하며 GitHub Actions `schedule` 트리거가
예정 시각에 아예 실행 기록조차 남기지 않고 스킵되는 신뢰성 한계를 겪었다. 이 문제를 계기로
"텔레그램으로 받는다(push)"는 특정 구현이 아니라 "원하는 시점에 데이터를 확인한다"가 프로젝트의
진짜 목적임을 재확인했고, 사용자가 원할 때 직접 열어보는 **Streamlit 대시보드(pull, `dashboard.py`)**
를 push와 나란히 두는 방향으로 프로젝트 범위가 넓어졌다. push와 pull 두 경로가 13주차에 만드는
동일한 Turso DB를 공유하므로, 이 문서의 주차 구성 자체는 바뀌지 않는다 — `dashboard.py`는
`stock_utils.py`가 이미 제공하는 함수(`read_watchlist`/`load_price_history`/
`fetch_naver_current_price`/`build_price_chart` 등)를 그대로 재사용하는 얇은 레이어라 함수
재사용 자체는 텔레그램 알림 로직을 다루는 6~8주차 실습을 마친 학생이라면 추가 개념 없이 읽을
수 있다. 다만 **Streamlit이 상호작용마다 스크립트 전체를 처음부터 다시 실행한다는 실행 모델**은
지금까지 만든 "한 번 실행되고 끝"인 스크립트들과는 다른, 이 프로젝트에서 처음 접하는 개념이라
13주차에서 별도로 짚는다. 자세한 논의 과정은 `ROADMAP.md`의 "전략적 재검토" 절 참고.

## 1. 수업 개요

빅데이터 파이썬 수업의 실습 프로젝트로, "관심종목의 현재가와 최근 거래일 종가 추이를
텔레그램으로 자동 전송하고, 대시보드로도 확인할 수 있는 봇"을 처음부터 끝까지 직접 만든다.
단순 문법 실습에 그치지 않고, **외부 API 연동 → 자동화 배포(GitHub Actions) → 클라우드 DB
연동(Turso)**까지 이어지는 실무형 데이터 파이프라인의 축소판을 13주에 걸쳐 단계적으로 완성한다.
"수집(collection) → 저장(DB) → 확인(push 또는 pull)"이 데이터의 출처·경로와 무관하게 하나의
파이프라인으로 이어진다는 것을 체감하는 것이 핵심이다.

수업은 "한 번에 완성된 코드"를 보여주는 대신, 실제 개발 과정에서 마주치는 문제(오류 메시지,
예상과 다른 실행 결과, 환경 차이로 인한 버그)를 학생이 직접 겪고 해결하는 방식으로 진행한다.

## 2. 얻을 수 있는 지식

- REST API의 개념과 요청/응답 구조 (네이버 금융 비공식 API, 텔레그램 Bot API)
- 환경변수와 비밀정보 관리 개념 (`.env`, GitHub Secrets, `.gitignore`)
- Git/GitHub의 기본 개념 (커밋, 원격 저장소, push, 저장소를 상태 저장 수단으로 쓰는 아이디어)
- CI/CD의 기초 개념 (GitHub Actions, cron 스케줄, `workflow_dispatch`, 권한(permissions))
- 파일 기반 저장(JSON) vs 관계형 DB 저장(SQL/Turso)의 구조적 차이
- SQL 기본 문법 (`CREATE TABLE`, `INSERT`, `SELECT`, `DELETE`, `PRIMARY KEY`)과, 실전에서
  자주 쓰이는 두 응용 패턴 — upsert(`INSERT ... ON CONFLICT DO UPDATE`: 같은 키가 이미 있으면
  덮어쓰고 없으면 새로 넣기)와 서브쿼리를 활용한 정리(`DELETE ... WHERE ... NOT IN (SELECT ...
  ORDER BY ... LIMIT ?)`: 최근 N개만 남기고 나머지를 지우기)
- 코드 모듈화/관심사 분리 개념 (`stock_utils.py`가 두 스크립트의 공용 함수를 담당하는 구조)
- 시간대(UTC/KST), 거래일 판별 등 도메인 지식과 이것이 실제 버그로 이어지는 사례
- 텔레그램 봇의 인터랙티브 컴포넌트(리플라이 키보드, 고정 메뉴 명령어)와 각각의 한계
- 다중 job GitHub Actions 워크플로에서 job 간 의존성(`needs`)·결과 전달(`outputs`)·조건부
  실행(`if`)·동시 실행 제어(`concurrency`)라는 개념
- API가 항상 깔끔한 JSON을 주지는 않는다는 것과, 그럴 때 정규식으로 방어적으로 파싱하는 접근

## 3. 얻을 수 있는 기술

- `requests`로 외부 API를 호출하고 JSON 응답을 파싱하는 능력
- `pandas`로 CSV 파일(`watchlist.csv`)을 읽고 다루는 능력
- `matplotlib`으로 그래프를 생성해 메모리 버퍼(`io.BytesIO`)로 전송하는 능력
- 텔레그램 봇을 생성하고 `sendMessage`/`sendPhoto` API로 메시지·이미지를 전송하는 능력
- Git/GitHub 기본 조작(clone, add, commit, push, remote)과 GitHub Actions 워크플로(YAML) 작성
- 환경변수·Secrets를 로컬(`.env`)과 클라우드(Secrets) 양쪽에서 안전하게 관리하는 능력
- SQL 쿼리 작성 및 `libsql-client` 같은 DB 클라이언트 라이브러리 사용 능력
- 실행 로그를 읽고 원인을 추적하는 디버깅 능력 (exit code, 스택 트레이스 해석 포함)
- 프로젝트 문서화 능력 (README, 주석, 트러블슈팅 가이드 작성)
- `getUpdates`를 폴링해 사용자 입력을 감지하고, 여러 개의 job으로 나뉜 워크플로를 설계하는 능력
- 하나의 기능을 구현한 뒤 문제(예: 버튼이 사라짐)를 발견하면 설계를 되돌리거나 바꾸는 반복 개선 능력

## 4. 얻을 수 있는 태도

- 오류 메시지를 피하지 않고 **근본 원인**을 끝까지 추적하는 태도 (예: "종가 히스토리 수집이
  실패했다" → exit code 확인 → 실제로는 장중 실행이라 파일이 안 생겼던 것이 원인이었음을
  단계적으로 좁혀가는 과정)
- "동작하는 것 같다"에서 멈추지 않고 실제 로그·결과물로 검증하는 습관
- 토큰·키 같은 비밀정보를 다룰 때의 책임감 있는 태도 (커밋 전 항상 확인하는 습관)
- 반복 작업을 자동화로 해결하려는 문제 해결 지향적 사고
- 완벽한 설계를 먼저 고민하기보다 **작동하는 것부터 만들고 점진적으로 개선**하는 반복적 개발 태도
- 협업 도구(Git)를 통해 변경 이력을 남기고 추적 가능하게 만드는 습관

## 5. 13주차 학습 내용

**1주 — 개발 환경 & Git/GitHub 기초**
- 학습 내용: Python·VS Code 설치, GitHub 계정 생성, 저장소 개념(clone/commit/push)의 의미
- 관련 파일/실습: 저장소 fork 또는 clone, 첫 커밋 실습

**2주 — 파이썬 데이터 처리 기초 I: pandas**
- 학습 내용: Series/DataFrame 개념, `pd.read_csv()`로 표 데이터 읽기, 열 선택·`dtype` 지정(종목코드 앞자리 0 보존 등), 행 순회
- 관련 파일/실습: 프로젝트와 무관한 간단 CSV로 연습 후 `read_watchlist()` 코드 읽어보기

**3주 — 파이썬 데이터 처리 기초 II: matplotlib**
- 학습 내용: `fig, ax = plt.subplots()`, `ax.plot()`으로 선 그래프, 축 라벨·제목, `fig.savefig()`로 이미지 저장
- 관련 파일/실습: 임의의 숫자 리스트로 그래프 그려보기 후 `build_price_chart()` 코드 읽어보기

**4주 — 외부 API 호출 기초**
- 학습 내용: `requests`로 HTTP GET 요청, **JSON 구조 이해**(키-값 쌍이 중첩된 텍스트 형식으로,
  파이썬의 딕셔너리·리스트와 거의 그대로 대응된다는 것 — `response.json()`이 이 문자열을
  실제 파이썬 딕셔너리로 바꿔준다), 네이버 금융 API로 현재가 조회
- 관련 파일/실습: `fetch_naver_current_price()` 직접 작성해보기

**5주 — 텔레그램 봇 만들기 & 비밀정보 관리**
- 학습 내용: `@BotFather`로 봇 생성·토큰 발급, `getUpdates`로 CHAT_ID 확인, `python-dotenv`·`.env`/`.gitignore`로 비밀키 보호
- 관련 파일/실습: `telebot.py` 실행, `.env` 작성 및 커밋 전 확인 습관 실습

**6주 — 데이터 입력과 메시지 전송**
- 학습 내용: 2주차 pandas 지식을 실전 적용 — `watchlist.csv`를 읽어 여러 종목을 순회하며 텔레그램 `sendMessage` 연동
- 관련 파일/실습: `read_watchlist()` + `send_telegram_message()` 조합

**7주 — 코드 구조화 & 상태 저장 설계**
- 학습 내용: 공용 함수 모듈(`stock_utils.py`) 분리 이유, `holidays`로 거래일 판별, "왜 과거 종가를 매번 재조회하지 않는가"와 JSON으로 최근 N일만 유지하는 로직
- 관련 파일/실습: `is_trading_day()`, `load_price_history()`, `update_price_history()` 구현

**8주 — 시각화와 이미지 전송**
- 학습 내용: 3주차 matplotlib 지식을 실전 적용 — 7주차에 만든 `price_history.json`의 실제 과거 종가로 종목별 그래프 생성, `io.BytesIO`로 메모리에 저장, `sendPhoto` 연동
- 관련 파일/실습: `build_price_chart()` 완성 및 전송 테스트
- 심화(선택): 과거 종가 그래프가 끝난 뒤, "오늘 하루의 실시간 흐름도 보고 싶다"는 요구를 어떻게
  풀지 다뤄본다 — 네이버 API의 당일 분봉 엔드포인트는 표준 JSON이 아니라 EUC-KR/깨진 문자가
  섞여 있어 `response.json()`이 그대로 안 먹힌다는 걸 직접 겪고, `re.findall()`로 필요한 데이터
  행만 방어적으로 추출하는 `fetch_naver_intraday_minutes()`를 완성한다. 이어서
  `build_price_chart()`가 과거 종가(점 15개)와 오늘 분봉(수백 개 점을 잇는 선)을 한 그래프에
  같이 그리도록 확장한다 — 점이 너무 많을 때 x축 눈금을 어떻게 솎아내는지도 함께 다룬다.

**9주 — Git을 상태 저장소로 쓰기 & Actions 기초**
- 학습 내용: GitHub Actions 개념, workflow YAML 문법(`on`, `jobs`, `steps`), cron 표기법과 시간대(UTC/KST)
- 관련 파일/실습: `notify.yml` 직접 작성해보기

**10주 — 자동화 배포 & 디버깅**
- 학습 내용: Secrets 등록, 스케줄 vs `workflow_dispatch`, 실패한 워크플로 로그 읽고 원인 추적
- 관련 파일/실습: 실제 워크플로 수동 실행 → 실패 로그 분석 → 수정

**11주 — 텔레그램 수동 트리거 & 다중 job 워크플로**
- 학습 내용: 9·10주차에서 익힌 GitHub Actions 지식을 확장 — 대부분의 폴링은 트리거가 없어 그냥
  끝난다는 점에서 착안해, `check`(가벼운 확인) job과 `notify`(무거운 알림 전송) job으로 나누고
  `needs`/`outputs`/`if`로 연결하는 다중 job 워크플로를 설계한다. 텔레그램의 리플라이 키보드
  버튼과 고정 메뉴 명령어(`setMyCommands`)로 사용자 입력을 받는 방법, `getUpdates`의 `offset`으로
  중복 처리를 막는 방법도 함께 다룬다.
- 관련 파일/실습: `check_manual_trigger.py`, `setup_telegram_button.py`,
  `.github/workflows/check_manual_trigger.yml` 작성
- 실전 디버깅 사례: 리플라이 키보드 버튼이 원인 불명으로 사라지는 문제를 겪고 인라인 버튼으로
  바꿨다가, "메시지를 지우면 버튼도 같이 사라진다"는 새로운 문제를 발견해 다시 리플라이
  키보드로 되돌리고 고정 메뉴 명령어를 보험으로 추가한 실제 과정을 그대로 따라가 본다
  (`ROADMAP.md` "기능 4" 후속 절 참고) — "한 번에 완벽한 설계"가 아니라 문제를 만날 때마다
  설계를 고쳐나가는 과정을 그대로 체험하는 것이 목적이다.

**12주 — 관계형 DB 기초 & Turso 설계**
- 학습 내용: SQL 기본 문법, JSON 구조를 테이블 스키마로 변환하는 사고 과정, Turso 계정/DB 생성
- 관련 파일/실습: `price_history` 테이블 스키마 설계 (`CREATE TABLE`)

**13주 — Turso 마이그레이션 & 최종 점검**
- 학습 내용: `libsql-client`로 DB 연동, `load_price_history`/`update_price_history`를 SQL 쿼리로
  교체, 워크플로에서 git 커밋 스텝 제거, 전체 파이프라인 종단간 테스트 및 발표
  - `update_price_history()`에 쓰인 두 SQL 패턴을 구체적으로 다룬다: (1) 같은 (종목, 날짜)
    조합이 이미 있으면 덮어쓰고 없으면 새로 넣는 `INSERT ... ON CONFLICT (code, date) DO
    UPDATE SET close = excluded.close` — 매번 "있는지 먼저 확인 후 분기"하지 않고 한 문장으로
    처리하는 upsert. (2) 종목별로 최근 `N`개(`NUM_HISTORY_DAYS`)보다 오래된 행만 지우는
    `DELETE ... WHERE code = ? AND date NOT IN (SELECT date FROM price_history WHERE code = ?
    ORDER BY date DESC LIMIT ?)` — 안쪽 `SELECT`로 "남겨야 할 최신 N개의 날짜"를 먼저 뽑고,
    바깥쪽 `DELETE`가 그 목록에 없는 나머지를 지우는 서브쿼리 활용.
- 관련 파일/실습: `stock_utils.py` DB 버전 완성, 최종 데모
- 심화(선택): `dashboard.py`(Streamlit)를 함께 열어, `stock_utils.py`의 `load_price_history()`를
  DB 버전으로 바꾸는 순간 텔레그램 알림과 대시보드 양쪽에 동시에 반영되는 것을 직접 확인해본다 —
  "공용 함수 모듈을 왜 분리했는가"(7주차)의 효과가 저장 방식이 바뀌는 순간에도 그대로 유지된다는
  것을 보여주는 실습이다. 이때 Streamlit 고유의 실행 모델도 함께 짚는다: 지금까지 만든
  스크립트는 위에서 아래로 한 번 실행되고 끝이었지만, Streamlit 앱은 페이지를 새로고침하거나
  `st.button("🔄 새로고침")`을 누르는 등 화면과 상호작용할 때마다 `dashboard.py` 전체가
  맨 위(import문)부터 다시 실행된다 — 즉 종목 리스트를 읽고 네이버 API를 조회하는 코드가
  "한 번만 실행"이 아니라 "열 때마다·누를 때마다 매번 새로 실행"된다는 점이 핵심이다.

**설계 의도**: 2~3주에 pandas·matplotlib **문법 자체**를 프로젝트와 분리해 먼저 익히고,
6주·8주에 그 지식을 실제 프로젝트 코드에 적용하는 2단계 구성으로 바꿨다 — 처음 API/텔레그램
코드를 볼 때 `pd.read_csv`나 `ax.plot` 같은 낯선 문법 때문에 막히지 않도록 하기 위함이다.
이를 위해 원래 있던 "텔레그램 봇 만들기"와 "비밀정보 관리"(5주)를 한 주로 묶어 전체 주차
수는 12주로 유지했다.

7주(코드 구조화 & 상태 저장 설계)와 8주(시각화와 이미지 전송)는 원래 개발 순서(그래프 →
상태 저장)를 그대로 옮겼을 때 "8주차에 배울 `price_history.json`을 7주차 그래프가 먼저
필요로 하는" 선후관계 역전이 있어 순서를 맞바꿨다 — `build_price_chart()`가 과거 종가
리스트를 입력으로 받아야 하므로, 그 데이터를 어디서 가져오는지(상태 저장 설계)를 먼저
배워야 그래프 실습이 실제 데이터로 의미 있게 완성된다.

8~10주는 "왜 이렇게 설계했는가/자동화가 왜 필요한가"를 다루며, 12~13주에 DB 연동이라는
상대적으로 추상적인 주제를 배치해 파일 기반 저장의 한계를 몸소 겪은 뒤 DB의 필요성을
체감하도록 했다.

**11주(텔레그램 수동 트리거 & 다중 job 워크플로) 신설 배경**: 원래 12주 계획에는 없던 주차다.
실제 프로젝트를 구현하는 과정에서 "자동 알림 시각이 아닐 때도 원할 때 바로 확인하고 싶다"는
요구가 나왔고, 이를 풀려면 9·10주차에서 배운 기본적인 워크플로 문법(`on`, `jobs`, `steps`,
Secrets)만으로는 부족해서 job을 나누고 연결하는 더 심화된 GitHub Actions 지식이 필요했다.
그래서 9·10주(Actions 기초·디버깅)와 12주(DB, 더 추상적인 주제) 사이, 즉 기초를 다진 직후이자
DB로 넘어가기 전에 배치했다. 이 주차는 실제로 겪은 시행착오(리플라이 키보드 → 인라인 버튼 →
다시 리플라이 키보드 + 명령어)를 그대로 담고 있어, "얻을 수 있는 태도" 4항(완벽한 설계보다
점진적 개선)을 가장 구체적으로 보여주는 주차이기도 하다.
