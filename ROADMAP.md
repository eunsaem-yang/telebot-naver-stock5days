# ROADMAP.md

`notify_stock_price.py`에 추가하고 싶은 기능과 구현 방법 후보를 정리한 문서다. 아직 구현 전 계획 단계.

## 현재 상태 (제약사항)

- 지금 쓰는 공공데이터포털 금융위원회 API(`GetStockSecuritiesInfoService`)는 **일별 종가(EOD) 데이터**만 제공한다.
  장중 실시간 체결가(현재가)는 이 API로 조회 불가능하다.
- `basDd` 기준 하루씩 과거로 재시도하는 기존 로직은 "가장 최근 영업일의 종가"를 안전하게 가져오는 용도로는
  이미 완성되어 있음 → 장 시작 전/마감 후 fallback에 그대로 재사용 가능.

## 기능 1: 관심종목 현재가 전송 (장중이면 실시간, 아니면 최근 종가)

### 방법 후보

| 방법 | 장점 | 단점 |
|---|---|---|
| **네이버 금융 비공식 API**<br>(`m.stock.naver.com` 등 공개 JSON 엔드포인트 scraping) | 키 발급 불필요, 무료, 응답 빠름 | 비공식이라 언제든 URL/응답 구조가 바뀔 수 있음. 약관상 회색지대 |
| 증권사 Open API<br>(한국투자증권 KIS, 이베스트 등) | 공식 지원, 안정적, 실시간 체결가 정식 제공 | 계좌 개설 + API 키 발급 필요, 인증 흐름(OAuth 토큰 등)이 복잡해 수업 난이도 초과 |
| `pykrx` 라이브러리 | 설치만 하면 바로 사용 가능 | 내부적으로 KRX 데이터를 감싼 것이라 결국 EOD 위주, 실시간 현재가는 미지원 |

**권장**: 네이버 금융 비공식 API로 장중 현재가를 가져오고, 장 시작 전/마감 후에는 기존 `basDd` fallback 로직으로 최근 종가를 그대로 사용.
(`.env`에 남아있는 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`는 네이버 검색/파파고 등 Open API용이라 실시간 시세와 무관 — 이 기능에는 별도 인증 없이 공개 JSON 엔드포인트를 직접 호출하는 방식이 필요함)

### 구현 스케치

1. 현재 시각이 평일 09:00~15:30(KST) 장중인지 판별하는 함수 추가.
2. 장중이면 네이버 금융 공개 엔드포인트로 종목별 현재가 조회.
3. 장중이 아니거나 조회 실패 시, 기존 `basDd` 루프로 최근 영업일 종가를 fallback으로 사용.
4. 텔레그램 메시지에 "현재가(장중)" 또는 "종가(최근 영업일 YYYY-MM-DD 기준)" 라벨을 구분해서 표시.

## 기능 2: 현재가 포함 최근 5일 종가 추이 그래프 전송

### 방법 후보

| 방법 | 장점 | 단점 |
|---|---|---|
| **`matplotlib`으로 선 그래프 생성 후 `sendPhoto`로 전송** | 기존 requests/pandas 스택과 잘 맞음, 구현 간단 | 텍스트가 아닌 이미지 생성/전송 코드 추가 필요 |
| 텍스트로 최근 5일 종가를 나열 (그래프 없이) | 구현 매우 간단 | 사용자가 "그래프"를 요청했으므로 요구사항 미충족 |

**권장**: `matplotlib`으로 그래프 생성 후 텔레그램 `sendPhoto` API로 전송.

### 구현 스케치

1. 기존 `basDd` 루프를 "하루라도 데이터를 찾으면 종료"가 아니라 "유효한 영업일 데이터를 5개 모을 때까지 계속(주말/공휴일은 skip)" 방식으로 확장.
2. 종목별로 최근 5거래일 종가 리스트 + (장중이면) 기능 1에서 구한 현재가를 마지막 점으로 추가.
3. `matplotlib`으로 종목별 선 그래프 생성, 이미지를 파일이 아니라 메모리(`io.BytesIO`)에 저장.
4. 텔레그램 `sendMessage` 대신 `sendPhoto` 엔드포인트로 멀티파트 이미지 업로드 (종목별 1장씩, 혹은 관심종목 수가 적으니 3개를 한 이미지에 subplot으로 묶어 1장으로 전송).

## 결정이 필요한 사항

- [x] 기능 1의 실시간 시세 소스: 네이버 비공식 API 사용. 학생들은 증권사 계좌가 없는 경우가 많기 때문.
- [x] 그래프는 종목별 1장씩 보낸다.
- [x] matplotlib를 사용한다.

## 알려진 이슈: 최근 5일 종가가 전부 같은 데이터로 나옴

### 증상

기능 2 구현 후 실행하면 그래프의 최근 5일 종가가 실제와 다르게 모두 동일한 값으로 나온다.

### 원인

`basDd`를 어떤 날짜로 바꿔 요청해도(`20260716`, `20250101`, `20200101` 등 직접 호출 테스트)
API가 **항상 동일한 응답**(`totalCount: 4334321`, 고정된 `basDt` 07/14~07/15 데이터)만 반환한다.
즉 `basDd` 파라미터가 서버에서 무시되고 있다.

이는 `PUBLIC_DATA_PORTAL_KEY`로 신청한 "금융위원회_주식시세정보" 서비스의 **활용신청이 아직 정식
승인되지 않아, 개발계정 상태의 고정 샘플 응답만 오고 있을 가능성이 높다** — data.go.kr에서 흔히
나타나는 증상이다 (승인 전에는 파라미터와 무관하게 동일한 샘플 데이터만 내려줌).

### 코드 수정 (완료)

`collect_recent_daily_closes()`를 다음과 같이 방어적으로 수정했다:

1. 요청한 날짜(`date_str`)가 아니라 **응답에 실제로 담긴 `basDt`**를 키로 사용해 종목별 종가를
   저장한다 (API가 요청과 다른 날짜의 데이터를 줘도 정확히 반영되도록).
2. 새 요청의 응답에 담긴 날짜 집합이 지금까지 이미 확인한 날짜 집합의 부분집합이면(=진전 없음,
   즉 API가 `basDd`를 무시하고 같은 데이터만 반복) 즉시 수집을 중단하고 원인을 안내하는 경고를
   출력한다. 예전처럼 5일 내내 같은 값을 채워 넣고 "5/5일 수집 완료"라고 속이지 않는다.
3. 목표한 5일치를 다 못 모았으면 실제로 모은 일수만큼만 그래프에 반영하고, 부족하다는 경고를 남긴다.

### 후속 확인 결과: 승인 완료 후에도 동일 증상 재현 → data.go.kr 포기, 네이버로 통합

data.go.kr 마이페이지에서 "금융위원회_주식시세정보" 서비스가 **이미 승인된 상태**임을 확인했다.
그런데도 `basDd`를 `20260716`/`20260710`/`20250101`로 바꿔가며 재호출해도 여전히
`totalCount: 4334321`, 고정된 `basDt`(07/14~07/15)만 반환됨을 재확인했다. 즉 원인은 승인 상태가
아니라 **이 엔드포인트 자체가 `basDd` 날짜 필터를 제대로 지원하지 않는 것**으로 결론 내렸다.
이 API에 계속 의존하는 대신, 기능 1에서 이미 안정적으로 동작을 검증한 **네이버 API 하나로 통합**하기로
결정했다 (아래 기능 3 참고). data.go.kr / `PUBLIC_DATA_PORTAL_KEY`는 더 이상 사용하지 않는다.

## 기능 3: 자동 스케줄링 (하루 3회 자동 알림) + 데이터 소스 통합

### 목표

사용자가 프로그램을 직접 실행하지 않아도, 한국 주식 시장이 열리는 평일 오전 10시/12시/2시에
자동으로 "최근 5일 종가 + 그 시각의 현재가" 그래프가 텔레그램으로 전송되어야 한다.

### 결정된 사항

- [x] **데이터 소스**: data.go.kr을 완전히 걷어내고 **네이버 API 하나로 통합**한다.
      네이버 `m.stock.naver.com/api/stock/{code}/basic` 응답의 `closePrice`는 장중엔 현재가,
      장마감 후 호출하면 그날의 최종 종가와 동일하므로, "현재가 조회"와 "일별 종가 기록"을
      모두 이 하나의 엔드포인트로 처리할 수 있다.
- [x] **스케줄러**: **GitHub Actions**의 scheduled workflow(cron)를 사용한다. 완전 무료이고
      카드 등록이 필요 없어 학생들이 쓰기에 가장 적합하다. (AWS Lambda는 계정/카드 등록과
      matplotlib Lambda Layer 패키징 부담이 있고, 로컬 Windows 작업 스케줄러는 PC가 켜져
      있어야만 동작하므로 제외.)

### 아키텍처

data.go.kr 없이도 "최근 5일 종가" 추이를 만들려면, 하루 세 번(10/12/2시) 실행되는 시점에는
그날 장이 아직 끝나지 않아 종가가 확정되지 않은 상태이므로, **과거 5일치 종가는 매 실행마다
다시 조회하지 않고 로컬에 캐시된 값을 읽기만 한다.** 이 캐시는 장마감 후 하루 한 번 실행되는
별도 작업이 갱신한다. GitHub Actions 실행 환경은 매번 새로 초기화되므로(상태가 없음),
캐시 파일(`price_history.json`)은 저장소(repo)에 커밋해서 다음 실행 때 다시 읽는 방식으로
"저장소를 곧 데이터베이스처럼" 사용한다 — 별도의 DB/AWS 스토리지 없이 무료로 상태를 유지하는 방법.

1. **`collect_daily_close.py`** (하루 1회, 장마감 직후 실행)
   - 관심종목별로 네이버 API에서 그날의 최종 종가를 조회
   - `price_history.json`에 `{code: [{"date": "YYYYMMDD", "close": 가격}, ...]}` 형태로
     날짜 기준 중복 제거 후 최근 5개만 남기고 저장
   - GitHub Actions 워크플로가 이 변경 사항을 저장소에 자동 커밋

2. **`notify_stock_price.py`** (하루 3회, 10시/12시/2시 실행)
   - `price_history.json`에서 이미 확정된 최근 5일 종가를 읽음 (재조회 없음)
   - 네이버 API로 그 시각의 현재가를 조회해 5일 종가 뒤에 6번째 점으로 추가
   - 기존과 동일하게 텍스트 메시지 + 종목별 그래프(`sendPhoto`)로 전송

3. **거래일 판별**: `holidays` 파이썬 패키지(`country="KR"`)로 주말/공휴일이면 아무 작업도
   하지 않고 조용히 종료 (데이터 API의 빈 응답으로 휴장일을 추측하던 기존 방식보다 안정적).

4. **GitHub Actions 워크플로 2개**
   - `.github/workflows/notify.yml`: cron `0 1,3,5 * * 1-5` (UTC 기준, KST 10/12/14시), 평일마다
     `notify_stock_price.py` 실행
   - `.github/workflows/collect_close.yml`: cron `40 6 * * 1-5` (UTC 기준, KST 15:40경 장마감 직후),
     `collect_daily_close.py` 실행 후 `price_history.json` 변경분을 저장소에 커밋

### 사용자가 직접 해야 할 것 (코드로 자동화 불가)

- [x] 이 프로젝트를 git 저장소로 초기화하고 `main` 브랜치로 첫 커밋 완료 (로컬 커밋 2개: `15a3bf8`, `68d5f17`)
- [x] GitHub에 저장소 생성 후 push 완료 (`github.com/eunsaem-yang/-telebot-naver-stock5days`,
      로컬 환경에 `gh` CLI가 없어 사용자가 웹사이트에서 직접 저장소 생성 → URL 공유 → `git push` 순으로 진행)
- [x] GitHub 저장소 Settings → Secrets에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록 완료
      (`PUBLIC_DATA_PORTAL_KEY`는 더 이상 필요 없음)
- [x] Actions 탭에서 워크플로가 스케줄대로 실행되는지 확인 → 아래 "알려진 이슈" 참고, 스케줄이
      아예 미발동하는 문제를 발견함

**우선순위 메모**: Turso DB 마이그레이션(향후 계획)보다 이 GitHub Actions 자동화 마무리가 먼저다.
저장 방식(JSON→DB) 실험은 자동화가 실제로 스케줄대로 동작하는 걸 확인한 뒤에 진행한다.

## 알려진 이슈: GitHub Actions 스케줄이 통째로 미발동함 (2026-07-21)

### 증상

`notify.yml`의 cron이 KST 10:05/12:05/14:05(평일)로 설정돼 있는데, 2026-07-21(화) 하루 동안
**세 슬롯 모두 자동(`schedule`) 실행 기록 자체가 생기지 않았다.** 단순히 몇 분 지연된 게 아니라
예정 시각에서 2시간 이상 지나도록 실행 기록이 전혀 없었다 (`gh run list --workflow=notify.yml`로
확인, `event=schedule` 실행은 전날 07-20 12:03 UTC가 마지막이고 그 뒤로는 전부 `workflow_dispatch`
수동 실행만 존재).

### 원인 조사

다음을 모두 확인했으나 저장소/워크플로 설정 쪽 문제는 없었다.

- cron 문법·시간대 계산 정확함 (`5 1,3,5 * * 1-5` UTC = KST 10:05/12:05/14:05, 평일). 오늘(화요일)도
  `1-5` 범위에 포함됨.
- 워크플로 상태 `active` (비활성화 아님), 저장소 `archived: false`, 최근 푸시 있어 60일 비활동
  자동 비활성화 대상도 아님 (`gh api repos/{owner}/{repo}` / `.../actions/workflows` 로 확인).
- Actions 권한 `enabled: true`, `allowed_actions: all`.
- GitHub 상태 페이지(githubstatus.com): Actions 컴포넌트 `operational`, 해당 일자 인시던트 없음.
- 반면 같은 날 수동 트리거(`workflow_dispatch`)는 4번 전부 성공 → 시크릿·권한·러너 할당 등 실행
  경로 자체는 정상.

### 결론

GitHub가 공식 문서에서 밝힌 대로, scheduled workflow는 "best-effort" 트리거라 **부하가 몰리면
실행 기록조차 남기지 않고 통째로 스킵될 수 있다.** 정시(0분)를 피해 5분으로 미룬 완화책은 이미
적용돼 있었는데도(9a8557a), 그 수준을 넘어서는 빈도(하루 3슬롯 전부)로 나타났다. 코드나 설정의
버그가 아니라 GitHub Actions 스케줄러 자체의 신뢰성 한계로 결론 내렸다.

### 대응 방향 (검토 중, 아직 미착수)

GitHub Actions의 `schedule` 트리거만으로는 실행을 보장할 수 없으므로, 외부 무료 크론 서비스가
정해진 시각에 GitHub REST API(`workflow_dispatch` 엔드포인트)를 직접 호출해 트리거하는 방식을
검토했다. 학생들이 카드 등록 없이 무료로 쓸 수 있어야 한다는 기존 제약([기능 3](#기능-3-자동-스케줄링-하루-3회-자동-알림--데이터-소스-통합)의 스케줄러 선정 기준과 동일)을 그대로 적용해 후보를 비교했다.

- **cron-job.org (유력 후보)**: 완전 무료, 카드 불필요, 작업 개수 제한 없음, 최소 1분 단위로 원하는
  시각(타임존 지정 가능)에 커스텀 HTTP 요청(메서드/헤더/body) 전송 가능. GitHub REST API의
  `POST /repos/{owner}/{repo}/actions/workflows/notify.yml/dispatches`를 호출해 워크플로를
  강제 트리거하는 방식. 다만 공식 FAQ에 "정시 실행을 보장하진 않는다"는 문구가 있어 100% 해결책은
  아니고, GitHub Actions 스케줄보다 신뢰도가 높은 이중 안전장치 정도로 접근해야 한다.
- **Google Apps Script time-driven trigger (기각)**: 학생들에게 익숙한 Google 계정 기반이지만,
  공식 문서에 "특정 시각(예: 9시)으로 설정해도 실제로는 그 시부터 1시간 이내 임의 시각에 실행된다"고
  명시돼 있어 하루 3번(10/12/14시)처럼 시각이 중요한 용도엔 부적합해 제외.
- **보안 주의사항**: 이 방식은 GitHub Personal Access Token을 cron-job.org(제3자 서비스)에
  등록해야 한다. `.env` 비밀값과 동일한 무게로 다뤄야 하며, classic PAT(`repo` 전체 권한)가 아니라
  **fine-grained PAT로 이 저장소 하나 + Actions 권한만** 부여하는 최소 권한 원칙을 적용해야 한다.

아직 실제 PAT 발급/cron-job.org 작업 등록은 진행하지 않았다. 방향성만 기록해두고, 착수 여부는
추후 결정한다.

### 구현 중 발견한 버그: 텔레그램 전송이 조용히 실패함

로컬 테스트 중 `notify_stock_price.py`가 텔레그램 텍스트 메시지 전송에 실패하는 문제가 있었다.

원인은 `stock_utils.py`가 모듈 임포트 시점에 바로
`TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")`을 실행하는데, 호출하는 스크립트
(`notify_stock_price.py`)에서는 `from stock_utils import ...`가 `load_dotenv()`보다 먼저
실행되고 있었다. 즉 `.env`가 로드되기 전에 토큰을 읽어서 `None`으로 고정된 것이다.

`stock_utils.py` 안에서 자신의 모듈이 임포트되는 즉시 `load_dotenv()`를 호출하도록 고쳐서,
호출하는 쪽의 import 순서와 무관하게 항상 올바르게 동작하도록 수정했다.

## 기능 4 (구현 완료): 텔레그램 버튼으로 수동 트리거

### 배경

위 "GitHub Actions 스케줄이 통째로 미발동함" 이슈에 대한 보완책을 논의하다가, "수동으로라도 원할 때
바로 알림을 받을 수 있으면 좋겠다"는 방향으로 이어졌다. 여러 구현 방식을 놓고 비교했다.

### 검토한 방법과 기각 이유

- **텔레그램 특정 메시지 → 수동 트리거**: 기본 아이디어. 텔레그램 `getUpdates`로 명령 메시지를
  감지해서 트리거하는 방식.
- **별도 모바일 앱 제작 (기각)**: 앱의 버튼이 하는 일은 결국 HTTPS 요청 하나뿐인데, 텔레그램이 이미
  커스텀 키보드/인라인 버튼을 무료로 제공하므로 새 앱을 만들 이유가 없다. 앱 배포 부담도 크고,
  GitHub PAT를 앱 안에 넣으면 디컴파일로 유출될 위험도 있다.
- **Webhook 방식 (기각, 이번 단계에서는)**: 텔레그램 webhook을 Cloudflare Workers 같은 서버리스
  플랫폼으로 받아 즉시(지연 거의 없이) GitHub `workflow_dispatch`를 호출하는 방식. 무료로 가능하지만
  Python + GitHub Actions로만 구성된 현재 커리큘럼 밖의 새 플랫폼(보통 JS/TS)과 배포 흐름을 추가로
  배워야 해서 수업 범위를 벗어난다고 판단. ROADMAP 기능 3에서 같은 이유로 AWS Lambda를 제외했던
  것과 같은 맥락.
- **폴링 방식 (채택)**: 몇 분 간격으로 도는 GitHub Actions 워크플로가 텔레그램 `getUpdates`를 확인해
  특정 명령 메시지(버튼 눌렀을 때 오는 메시지)가 있으면 그 안에서 바로 알림 스크립트를 실행.
  새 인프라·새 언어 없이 기존 스택(Python + GitHub Actions) 안에서 해결되는 게 최대 장점. 다만
  이 폴링 워크플로 자체도 "GitHub Actions 스케줄이 통째로 미발동함" 이슈의 영향을 그대로 받으므로
  실행이 몇 분 이상 지연되거나 드물게 스킵될 수 있다는 한계는 남는다. 수동 트리거는 "지금 당장 급함"이
  아니라 "자동 알림 시간이 아닐 때 확인용"이라는 용도상 감수 가능하다고 판단.

### 결정 사항

- [x] **기존 자동 스케줄(`notify.yml`의 `schedule` 트리거)은 그대로 유지**한다. 이 기능은 그 위에
      추가되는 별도 경로다.
- [x] 구현 방식은 **폴링**으로 결정 (webhook/별도 앱 방식은 기각).

### 구현 내용 (2026-07-21 완료)

- `notify_stock_price.py`의 알림 로직을 `send_price_notification()` 함수로 분리해, 자동 스케줄과
  수동 트리거 양쪽에서 동일한 로직을 재사용하도록 했다. `python notify_stock_price.py`로 직접
  실행했을 때의 동작(하루 3회 자동 스케줄용)은 이전과 동일하다.
- `stock_utils.py`에 `MANUAL_TRIGGER_TEXT`(버튼 라벨 겸 트리거 판별 문자열),
  `MANUAL_TRIGGER_KEYBOARD`(텔레그램 커스텀 키보드), `fetch_telegram_updates()`(`getUpdates`
  래퍼), `send_telegram_message()`의 `reply_markup` 파라미터를 추가했다.
- `setup_telegram_button.py`: 로컬에서 1회만 실행해 채팅창에 버튼을 노출하는 설정 스크립트.
- `check_manual_trigger.py`: **감지만** 하는 폴링 스크립트. `getUpdates`로 새 메시지를 확인하고,
  트리거 여부와 무관하게 조회한 업데이트는 즉시 `offset`을 넘겨 텔레그램 서버 쪽에서 확인 처리한다
  (로컬에 별도 offset 파일을 저장하지 않아도 중복 처리를 막을 수 있음). 실제 알림 전송은 이 스크립트가
  아니라 `notify_stock_price.py`가 맡는다.
- `.github/workflows/check_manual_trigger.yml`: 평일 KST 09:00~18:59, 5분 간격(정시 혼잡을 피해
  2분 오프셋)으로 동작하는 새 워크플로. **`check`/`notify` 두 job으로 분리**했다 — 폴링은 대부분
  트리거 없이 끝나므로 `check` job은 `requests`/`python-dotenv`만 설치하고, 버튼이 실제로 감지된
  경우에만(`needs.check.outputs.triggered == 'true'`) `notify` job이 `requirements.txt` 전체
  (pandas/matplotlib/holidays)와 나눔고딕 폰트를 설치해 `notify_stock_price.py`를 실행한다. 겹쳐
  실행되는 런 사이의 레이스 컨디션을 막기 위해 `concurrency` 그룹도 추가했다. 기존
  `notify.yml`/`collect_close.yml`과는 독립적으로 동작한다.
- 로컬 테스트로 버튼 노출 → 버튼 클릭 → 폴링 스크립트가 트리거를 감지하는 것까지 확인했다
  (job 분리 전 구조로, `send_price_notification()`을 직접 호출해 텍스트+그래프 3종목 전송까지
  전체 흐름을 검증함).

### 알려진 트레이드오프 (의도적으로 남겨둠)

- **offset 확인 처리가 알림 전송 성공보다 먼저 일어난다.** `check` job이 버튼 메시지를 확인 처리한
  뒤에 `notify` job이 실행되므로, `notify` job이 실패(네트워크 오류, matplotlib 오류 등)해도 버튼
  입력은 이미 소비된 상태라 재시도되지 않는다. 두 job을 다시 하나로 묶으면 고칠 수 있지만, 그러면
  위에서 적용한 "트리거 없을 때 무거운 의존성을 건너뛰는" 효율화와 충돌한다. 실패 빈도가 낮고
  결과도 "버튼을 한 번 더 누르면 됨" 수준이라 감수하기로 했다.
- **이 폴링 워크플로 자체도 결국 `schedule` 트리거라 "GitHub Actions 스케줄이 통째로 미발동함"
  이슈의 영향을 그대로 받는다.** 즉 이 기능은 그 문제를 우회하는 완전한 해결책이 아니라, 발동
  확률을 높이는 보완책에 가깝다. 근본적으로 해결하려면 위에서 검토한 cron-job.org 같은 외부
  트리거가 필요하다 (아직 미착수).

### 후속: 버튼이 사라지는 문제 → 인라인 버튼 시도 → 다시 되돌림 + `/notify` 명령어 추가 (2026-07-21)

실제로 써보니 리플라이 키보드(입력창을 대체하는 커스텀 키보드) 버튼이 특별한 이유 없이 안 보이는
증상을 겪었다. 원인은 명확히 못 찾았고(디버그 메시지로는 정상 동작 확인됨, 클라이언트 렌더링
문제로 추정), 재현이 간헐적이었다.

**1차 대응: 인라인 버튼(클라이언트 무관하게 메시지에 고정으로 붙는 버튼)으로 전환.**
`MANUAL_TRIGGER_KEYBOARD`를 `inline_keyboard`로, 감지 로직을 `callback_query` 이벤트 판별로
바꾸고 `answerCallbackQuery`로 확인 응답까지 구현해 실제 동작을 검증했다. 학생 입장에서도
"하나의 Update가 여러 종류의 이벤트를 담을 수 있다"는 걸 배우는 좋은 소재라고 판단했었다.

**그런데 사용자가 새로운 맹점을 지적함**: 인라인 버튼은 특정 메시지에 딸려 있어서, 그 메시지를
사용자가 지우면 버튼도 같이 사라진다 — 리플라이 키보드는 채팅 자체에 남아있어 이 문제가 없었다.

**최종 결정: 리플라이 키보드로 되돌리고, 텔레그램의 고정 메뉴 명령어(`setMyCommands`)를 보험으로
추가.** `MANUAL_TRIGGER_KEYBOARD`는 다시 리플라이 키보드로 되돌렸고(`answer_telegram_callback`
등 인라인 전용 코드는 제거), `MANUAL_TRIGGER_COMMAND = "/notify"`를 새로 추가했다. `/notify`는
채팅 입력창 옆 고정 메뉴에 봇 자체 설정으로 등록되는 것이라(`register_telegram_commands()`,
`setMyCommands` API) **어떤 메시지도 지운 것과 무관하게 항상 남아있다.** `check_manual_trigger.py`의
`_is_trigger_message()`는 버튼 텍스트(`MANUAL_TRIGGER_TEXT`)와 명령어 텍스트
(`MANUAL_TRIGGER_COMMAND`) 둘 다 일반 텍스트 메시지로 오므로 동일한 로직으로 판별한다 — 결과적으로
콜백 이벤트보다 오히려 더 단순해졌다. `setup_telegram_button.py`가 버튼 노출과 명령어 등록을
한 번에 처리한다. 리플라이 키보드 버튼 클릭 경로와 `/notify` 명령어 경로 둘 다 로컬에서 실제
클릭·선택 → 감지 → 알림 전송까지 확인했다.

## 기능 5 (구현 완료): 오늘 시세 변화 그래프 + Turso 마이그레이션 대상 재검토

### 니즈

"오늘의 시세 변화를 그래프로 보고 싶다." 지금 그래프는 과거 15일 종가 뒤에 현재가 딱 한 점만
붙이는 방식이라, 오늘 하루 동안 가격이 어떻게 움직였는지는 보이지 않는다.

### 처음 접근과 문제점

처음엔 "자동 트리거(하루 3회) + 수동 트리거(기능 4)가 발생할 때마다 그 결과를 기록해서, 과거
15일 + 오늘의 기록된 점들을 모아 그래프를 그린다"는 방식으로 접근했다. 하지만 이 방식은:
- 하루에 최대 5~6번(자동 3 + 수동 N) git commit·push가 필요해져 `notify.yml`에도 커밋 권한이
  생기고, 두 워크플로가 동시에 커밋하다 충돌할 가능성까지 대비해야 함
- 그래프에 찍히는 점이 하루 3~6개뿐이라 실제 시세 흐름을 보여주기엔 너무 성김

### 발견: 네이버 API에 날짜범위 조회가 되는 엔드포인트가 있었음

`api.finance.naver.com/siseJson.naver` 엔드포인트를 실제 curl로 테스트해 확인했다:

```
https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime={YYYYMMDD}&endTime={YYYYMMDD}&timeframe=minute   # 분 단위 시세 (당일 09:00~조회 시점까지, 수백 개 포인트)
https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime={YYYYMMDD}&endTime={YYYYMMDD}&timeframe=day       # 일별 OHLC, 날짜 범위 지정 가능 (주말/공휴일 자동 제외, 오늘도 포함)
```

응답이 EUC-KR/mojibake가 섞인 유사-JSON이라 `json.loads`로 바로 파싱은 안 되고, 데이터 행만
정규식으로 추출해야 한다 (헤더 행의 한글 라벨은 깨지지만 데이터 행은 ASCII라 영향 없음). 이
`timeframe=day`가 `data.go.kr`과 달리 **날짜 필터가 실제로 동작**한다는 것도 확인했다.

### 설계 갈등: 이 발견을 어디까지 활용할 것인가

이 발견을 살려 "과거 15일도, 오늘 분봉도 전부 매번 라이브 조회"로 가면 `price_history.json`과
`collect_daily_close.py`, `collect_close.yml`을 통째로 없앨 수 있어 보였다 — 상태 저장·git
커밋·스케줄 미발동 리스크가 전부 사라지는 매력적인 방향이었다.

그런데 `CURRICULUM.md`를 다시 보니 **7·8·11·12주차가 전부 `price_history.json`을 중심 소재로
짜여 있었다** (7주: JSON으로 최근 N일 유지하는 로직 학습 / 8주: 그 JSON으로 그래프 생성 / 11주:
JSON 구조를 SQL 스키마로 변환 / 12주: 실제 Turso 마이그레이션). `price_history.json`을 없애면
이 4개 주차를 다시 설계해야 하는 문제가 생겼다.

이 시점에 사용자의 진짜 니즈를 다시 확인했다: **"수집된 데이터를 DB에 넣고 읽어다 쓰는 방법을
보여주고 싶었다"** — 즉 DB 단원의 핵심은 "수집(collection)"이라는 행위 자체를 가르치는 것이었다.
"파일 내용을 DB로 옮기는 것"(예: `watchlist.csv` → Turso 테이블)은 정적 데이터 이전일 뿐이라
이 "수집" 경험과는 결이 다르다는 것도 사용자가 직접 짚었다.

### 결론 (구현 전, 방향만 확정)

두 데이터의 성격이 다르다는 데서 답이 나왔다:
- **과거 15일 종가**: 매일 쌓이는(=수집되는) 데이터. `collect_daily_close.py` /
  `price_history.json`(→ 향후 Turso 마이그레이션 대상) 구조를 **그대로 유지**한다. 커리큘럼
  7·8·11·12주는 손대지 않는다.
- **오늘의 분봉**: 애초에 "수집해서 쌓아둘" 이유가 없는, 조회 즉시 쓰고 버리는 데이터. 위에서
  확인한 `timeframe=minute` 라이브 API로만 가져와 그래프의 "오늘" 구간에 이어붙인다. 저장도,
  git 커밋도, 워크플로 변경도 필요 없다.
- **"왜 매번 라이브로 다 안 가져오고 굳이 저장하는가"에 대한 수업 명분**: 이 프로젝트가 이미 겪은
  `data.go.kr`의 날짜 필터 버그, GitHub Actions 스케줄 미발동 이슈처럼 **무료 비공식 API는
  언제든 바뀌거나 막힐 수 있다는 것** — 그래서 우리만의 데이터를 직접 쌓아두는 것이 실무에서도
  흔한 이유임을 그대로 예시로 쓸 수 있다.

### 구현 내용 (2026-07-21 완료)

- `stock_utils.py`에 `fetch_naver_intraday_minutes(code, date_str=None)` 추가. 응답이 EUC-KR/
  비표준 JSON이 섞여 있어 `json.loads` 대신 데이터 행만 정규식(`re.findall`)으로 추출한다.
  실패하거나 아직 장 시작 전이면 빈 리스트를 반환 (그래프는 이 경우 기존처럼 현재가 한 점만
  표시하도록 자연스럽게 폴백된다).
- `build_price_chart()`에 `intraday_minutes` 파라미터를 추가해 과거 종가(점+값 라벨)와 오늘
  분봉(수백 개 점을 잇는 얇은 선, 마지막 점만 빨간색으로 강조)을 한 그래프에 이어 그린다. 분봉
  점 하나하나에 값 라벨을 붙이면 수백 개가 겹치므로, x축 눈금은 과거 일자는 전부 + 오늘 구간은
  정시(HH:00)만 골라 표시하도록 처리했다.
- `notify_stock_price.py`가 그래프를 그리기 전에 `fetch_naver_intraday_minutes()`를 호출해
  전달한다 — `send_price_notification()`을 통해 자동 스케줄(`notify.yml`)과 수동 트리거
  (기능 4의 `check`/`notify` job) 양쪽에 자동으로 적용된다.
- 로컬 테스트로 실제 텔레그램 전송까지 확인했다 — 어제 종가 → 오늘 09:00~조회 시점까지의
  분봉이 매끈한 선으로 이어지고, 현재가가 빨간 점으로 강조되는 것을 확인함.
- `price_history.json`/`collect_daily_close.py`/`collect_close.yml`은 계획대로 손대지 않았다
  (커리큘럼 7·8·11·12주 그대로 유지).

## DB 적용 전 최종 점검: 코드 정리 + 배포 직전에 발견한 버그 (2026-07-21)

기능 4·5까지 구현을 마친 뒤, DB(Turso) 연동 전 마지막 상태로서 코드 전체를 재사용성/단순화/
효율성/설계 깊이 네 관점으로 점검했다.

### 발견한 버그 (수정 완료): `check` job이 실제로는 항상 실패했을 것

`stock_utils.py`가 모듈 최상단에서 `import pandas as pd` / `import matplotlib`를 무조건
실행하고 있었는데, `check_manual_trigger.yml`의 가벼운 `check` job은 `pip install requests
python-dotenv`만 설치한다. `check_manual_trigger.py`가 `from stock_utils import ...`를 하는
순간 이 무거운 import들도 함께 실행되므로, **실제로 push했다면 `check` job이 매번
`ModuleNotFoundError`로 실패했을 것**이다 — 로컬 테스트에서는 개발 환경에 pandas/matplotlib이
이미 깔려있어서 증상이 드러나지 않았다.

`pandas`는 `read_watchlist()` 안으로, `matplotlib` 관련 import·설정은 `build_price_chart()`
안으로 옮겨 필요한 함수 내부에서만 로드하도록 고쳤다. `holidays`는 가벼운 패키지라 최상단에
남기고, 대신 `check_manual_trigger.yml`의 `check` job 설치 목록에 추가했다(`requests
python-dotenv holidays`). **가벼운 의존성만 설치된 격리 가상환경을 새로 만들어 실제로
`check_manual_trigger.py`가 pandas/matplotlib 없이 정상 동작하는 것까지 검증했다.**

### 정리한 것

- `notify_stock_price.py`/`stock_utils.py` 모듈 docstring이 기능 4·5 추가 전 상태로 남아있던
  것을 최신화.
- 그래프 제목(`title_prefix`)과 텔레그램 캡션에 거의 동일한 3분기 라벨 로직이 중복돼 있던 것을
  `describe_price_trend()` 공용 함수로 통합 (제목과 캡션이 이제 완전히 같은 문구를 쓴다).
- 휴장일에 버튼을 눌러도 무거운 `notify` job이 켜지던 것을 막기 위해, `check_manual_trigger.py`가
  `is_trading_day()`까지 확인하고 나서 트리거 여부를 보고하도록 변경.
- `fetch_naver_intraday_minutes()`가 "장 시작 전이라 데이터 없음"과 "API 응답 형식이 바뀜"을
  구분 못 하던 것을, 타임스탬프가 있는데도 파싱이 안 되면 경고 로그를 남기도록 보강.

### 검토했지만 적용하지 않은 것

- 종목별 현재가/분봉 API 호출을 스레드로 병렬화하는 안 — 종목 3개짜리 교육용 봇에 스레딩까지
  넣는 건 과하다고 판단.
- offset 확인 처리 시점을 job 출력값으로 넘겨 더 정교하게 만드는 안 — 이미 "기능 4" 절에
  의도적인 트레이드오프로 기록해 둔 사안이라 재검토하지 않았다.

## 수업 커리큘럼 설계 결정: pandas/matplotlib을 초기 주차에 배치

- [x] 학생들이 API 연동·자동화 코드를 보기 전에 `pandas`/`matplotlib` **문법 자체**를 먼저
      익히도록, 12주 커리큘럼의 2~3주차에 프로젝트와 무관한 독립 예제로 pandas/matplotlib
      기초를 배치하고, 6주·8주차에 그 지식을 `read_watchlist()`/`build_price_chart()` 같은
      실제 프로젝트 코드에 적용하는 2단계 구성으로 재구성했다. `pd.read_csv`나 `ax.plot`처럼
      낯선 문법 때문에 API/텔레그램 코드를 처음 볼 때부터 막히지 않게 하려는 목적.
      전체 주차 수(12주)를 유지하기 위해 성격이 비슷한 주차끼리(텔레그램 봇 만들기+비밀정보
      관리) 묶었다.
- [x] 원래 "시각화(그래프)"를 "상태 저장 설계"보다 먼저 배치했으나, `build_price_chart()`가
      과거 종가 리스트를 입력으로 받아야 하는데 그 데이터의 출처(`price_history.json`,
      `load_price_history()`)를 아직 안 배운 시점이라는 선후관계 역전을 발견해 두 주차
      순서를 맞바꿨다 (7주: 코드 구조화 & 상태 저장 설계 → 8주: 시각화와 이미지 전송).
      자세한 주차별 내용은 `CURRICULUM.md` 참고.
