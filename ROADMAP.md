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
- [x] GitHub에 저장소 생성 후 push 완료 (`github.com/eunsaem-yang/telebot-naver-stock5days`,
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

### 재발 확인: 2026-07-22에도 동일 증상, `check_manual_trigger.yml`까지 영향

2026-07-22(수) 10:05 KST 슬롯에서도 `notify.yml`의 자동 실행이 발동하지 않았고, 같은 날 사용자가
텔레그램 버튼/`/notify` 명령어로 수동 트리거를 눌러도 응답이 없었다. 확인해보니 감지 역할인
`check_manual_trigger.yml`(평일 5분 간격 폴링)도 전날 오후 이후 단 한 번도 실행되지 않은 상태였다
— 즉 트리거를 감지할 워크플로 자체가 멈춰 있어서, 버튼을 누르든 명령어를 치든 반응이 없었던 것.
`schedule` 트리거의 신뢰성 문제가 `notify.yml` 하나만이 아니라 **폴링 방식에 의존하는 기능 4
전체**에 그대로 전이된다는 걸 재확인했다.

### 수업 진행을 위한 결정 사항: cron-job.org 대신 수동 `workflow_dispatch` 안내

위 재발을 계기로 "학생이 개발을 완료해도 결과를 확인할 수 없으면 수업 진행이 막힌다"는 문제를
논의했다. cron-job.org 이중 트리거(위 대응 방향)를 `check_manual_trigger.yml`에도 확장 적용하는
안을 검토했으나, **수업 목적으로는 채택하지 않기로 했다**:

- cron-job.org는 학생 각자가 자기 저장소마다 GitHub PAT를 발급해 제3자 서비스에 등록해야 하는데,
  이 설정 자체가 수업 시간을 잡아먹고 보안 리스크(제3자 서비스에 PAT 노출)도 매 학생마다 반복된다.
- 수업에서 실제로 필요한 건 "매일 빠짐없이 정시에 자동 발송"이 아니라 "학생이 개발을 마쳤을 때
  즉시 결과를 확인"하는 것이다. 이 요구는 이미 두 워크플로 모두에 걸려 있는 `workflow_dispatch`
  트리거로 충분히 해결된다 — 지금까지 기록상 `workflow_dispatch`로 실행한 런은 전부 성공했다
  (best-effort인 `schedule`과 달리 `workflow_dispatch`는 즉시·확실하게 실행됨).

**결정**: 수업 중 검증은 GitHub Actions 탭의 **"Run workflow" 버튼**(또는 `gh workflow run
notify.yml` / `gh workflow run check_manual_trigger.yml`)으로 안내한다. cron-job.org 이중
트리거는 "실제 프로덕션에서 매일 자동 알림이 안정적으로 와야 한다"는 요구가 별도로 생겼을 때
선택적으로 재검토하는 것으로 미룬다 (착수 안 함, 방향성만 유지).

### 후속 논의: "수동 Run workflow"와 "자동화"는 서로 다른 문제

위 결정 직후, "학생이 PC 없이도 스케줄에 의해 자동으로 데이터를 받는다"는 것 자체가 이 프로젝트의
핵심 목적이라는 점을 다시 짚었다. 정리하면 두 문제는 다르다:

- **지금 당장 결과를 확인하고 싶다 (수업 중 검증/채점)** → `workflow_dispatch`(Run workflow)로
  충분히 해결됨. 사람이 그 순간 직접 눌러야 한다는 건 자동화가 아니라 수동 확인 수단일 뿐이다.
- **PC/사람 개입 없이 매일 자동으로 온다 (원래 목적)** → 이건 여전히 `schedule` 트리거의 신뢰성
  문제에 그대로 노출돼 있고, `workflow_dispatch`로는 대체되지 않는다.

이 신뢰성 문제는 GitHub의 유료 요금제로도 해결되지 않는다 — 공식 문서에 `schedule`은 Free/Pro/
Team/Enterprise Cloud 전부 동일하게 "best-effort"라고 명시돼 있고, 원인이 컴퓨팅 자원 부족이
아니라 GitHub 중앙 스케줄 디스패처가 부하 시 이벤트 자체를 스킵하는 설계이기 때문이다. 진짜
신뢰도를 높이려면 이 디스패처를 거치지 않고 외부에서 직접 API(`workflow_dispatch`)를 호출하는
방식(cron-job.org 등)이 필요하다는 결론에 다시 도달했다. **안정성을 끌어올리는 방향으로 의견이
모였고, cron-job.org 도입 여부는 아래 모바일 실습 결과를 본 뒤 최종 결정하기로 했다.**

### 모바일에서 수동 트리거 실습 결과 (2026-07-22, 두 방법 모두 검증 완료)

cron-job.org 도입을 최종 결정하기 전에, "학생 입장에서 수동 트리거가 얼마나 번거로운지"를
안드로이드/아이폰에서 직접 실습해봤다. **방법 1, 방법 2 모두 실제로 텔레그램 메시지 수신까지
확인됨.**

#### 방법 1: GitHub 웹사이트 "Run workflow" 버튼 (브라우저만 있으면 됨)

1. 폰 브라우저에서 `github.com` 접속 → 로그인
2. 저장소(`github.com/eunsaem-yang/telebot-naver-stock5days`) 이동
3. `☰` 메뉴 → **Actions** 탭
4. 워크플로 목록에서 **"관심종목 현재가 알림"** 탭
5. 오른쪽 위 **"Run workflow"** 드롭다운 → 브랜치 `main` 확인 → 초록색 **"Run workflow"** 버튼 탭
6. 화면 당겨 새로고침 → 새 실행 항목 확인

→ **실습 결과: 성공, 텔레그램 메시지 수신 확인.** 로그인 상태만 유지되면 이후엔 몇 번의 탭만으로
끝나 수업 중 검증용으로 실용적.

#### 방법 2: `gh workflow run notify.yml` (터미널 앱 설치 필요, 최초 1회만 로그인)

**Android (Termux)**
1. Play 스토어에서 **Termux** 설치
2. `pkg update && pkg upgrade`
3. `pkg install gh`
4. `gh auth login` → `GitHub.com` → `HTTPS` → `Login with a web browser` 선택
5. 터미널에 뜨는 `! First copy your one-time code: XXXX-XXXX`를 복사 → Enter로 브라우저 열기 →
   `github.com/login/device`에서 코드 입력해 인증
6. `gh workflow run notify.yml --repo eunsaem-yang/telebot-naver-stock5days`

→ **실습 결과: 성공, 텔레그램 메시지 수신 확인.** `gh auth login`은 최초 1회만 필요하고(토큰이
Termux 앱 저장공간에 남아있는 한 유지), 이후엔 마지막 명령어 한 줄이면 됨.

**iPhone (iSH)**
1. App Store에서 **iSH**(Alpine Linux 에뮬레이터, x86 32비트라 다소 느림) 설치
2. `apk update`
3. `apk add github-cli` (iSH 아키텍처 제약으로 패키지가 없을 수 있음 — 이 경우 `curl`로 GitHub
   REST API를 직접 호출하는 방식으로 대체 가능)
4. `gh auth login` → 인증
5. `gh workflow run notify.yml --repo eunsaem-yang/telebot-naver-stock5days`

→ iPhone 쪽은 실제 실습·검증까지는 하지 않음 (Android로 검증 완료, 원리는 동일).

#### 결론

두 방법 다 모바일에서 실제로 동작하는 걸 확인했지만, 체감 난이도는 다르다: 방법 1은 브라우저
로그인만 되어 있으면 매번 몇 번의 탭으로 끝나고, 방법 2는 최초 설정(앱 설치 → 패키지 설치 →
`gh auth login`)이 무겁지만 그 이후엔 명령어 한 줄로 끝난다. 두 방법 모두 **"학생이 그 순간
직접 조작해야 한다"는 근본적 한계는 동일**하므로, cron-job.org 도입 여부 결정에는 이 실습
결과보다 위 "후속 논의"에서 정리한 신뢰성 문제 자체가 더 중요한 판단 기준이다.

### cron-job.org 이중 트리거 실제 도입 (2026-07-22, 검증 완료)

모바일 실습 이후 "안정성을 끌어올리는 방향"으로 결정하고, 검토만 해뒀던 cron-job.org 이중
트리거를 실제로 구축했다.

#### 1. Fine-grained PAT 발급

`github.com/settings/tokens?type=beta`에서 발급:
- Repository access: **Only select repositories** → 이 저장소 하나만
- Permissions → **Actions: Read and write**만 부여, 나머지는 전부 No access
- Expiration을 무기한이 아니라 기한을 두어 설정 (주기적 재발급 필요 — 아래 "남은 과제" 참고)

PAT는 Bearer 토큰 방식(`Authorization: Bearer <token>`)으로 쓰이며, 발급 화면에서 **한 번만
표시**되므로 그 자리에서 안전한 곳에 복사해둬야 한다. `.env`의 비밀값과 동일한 무게로 다뤄야
하고, 저장소 코드/커밋에는 절대 남기면 안 된다.

#### 2. cron-job.org에 Cron Job 2개 등록

로그인 후 작업 목록/수정 화면: `https://console.cron-job.org/jobs`

**공통 헤더** (`notify.yml`/`check_manual_trigger.yml` 두 작업 모두 동일, 토큰도 동일 —
저장소 단위 권한이라 워크플로별로 나눌 필요 없음):
```
Authorization: Bearer <PAT>
Accept: application/vnd.github+json
```
- cron-job.org 화면의 **"Requires HTTP authentication"**(Basic Auth 전용 별도 기능)은 켜지
  않는다 — 이건 헤더 방식과 별개 기능이라, 둘 다 채우면 `Authorization` 헤더가 충돌해 요청이
  실패할 수 있다.
- Request method: `POST`, Request body: `{"ref":"main"}`

**작업 1 (`notify.yml`)**: URL 끝을 `.../actions/workflows/notify.yml/dispatches`로, 스케줄은
KST 10:05/12:05/14:05(평일)에 맞춰 등록.

**작업 2 (`check_manual_trigger.yml`)**: URL 끝을 `check_manual_trigger.yml/dispatches`로.
스케줄은 "Every 5 minutes" 같은 **간편 프리셋으로는 시간대(09~19시)·요일(평일) 제한 옵션 자체가
비활성화/미표시**되는 걸 확인했다 — cron-job.org에서 이런 조합을 쓰려면 **Custom(사용자 지정)
모드**로 전환해야 분/시/요일을 각각 체크박스로 독립 지정할 수 있다. Minutes에 5분 단위 전부,
Hours에 9~18, Days of week에 월~금만 체크해서 해결.

#### 3. 트러블슈팅: 401 Unauthorized

첫 저장 후 테스트 시 `401 Unauthorized: the endpoint requires authentication` 응답을 받았다.
이 메시지는 "토큰이 틀렸다"가 아니라 **Authorization 헤더 자체가 요청에 안 실려갔다**는 뜻이라,
아래처럼 원인을 분리해서 확인했다.

- 토큰 자체가 유효한지 확인하기 위해, 토큰을 채팅(대화 기록)에 노출시키지 않고 **사용자의
  터미널(Termux)에서 직접 `curl`로 같은 요청**을 재현하도록 안내:
  ```
  curl -i -X POST -H "Authorization: Bearer <TOKEN>" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/{owner}/{repo}/actions/workflows/notify.yml/dispatches \
    -d '{"ref":"main"}'
  ```
- 이렇게 GitHub API 호출 경로와 cron-job.org UI 문제를 분리해서 원인을 좁혔다. 최종적으로는
  cron-job.org 쪽 헤더 저장/입력 문제였던 것으로 보이며(재입력 후 정상화), 재발 시 위 curl
  재현이 가장 빠른 진단 수단임을 기록해둔다.

#### 4. 검증: 자동 스케줄이 실제로 사람 개입 없이 도는지 확인

Test Run(수동 클릭)으로 204 응답을 받는 것과, **실제 예약 스케줄이 자동으로 도는 것**은 다른
문제라 별도로 검증했다.

- cron-job.org 대시보드의 **"Next execution"** 값(예: 13:45 KST)을 확인하고, 그 시각이 지날
  때까지 아무 것도 누르지 않고 기다린 뒤 `gh run list`로 확인 → **13:45:15(KST)에 정확히
  `workflow_dispatch` 이벤트로 자동 실행됨**을 확인. Timezone을 `Asia/Seoul`로 정확히 맞췄기
  때문에 시각이 어긋나지 않았다 (UTC로 잘못 설정했다면 시간대가 12~13시간 밀렸을 것).
- 이어서 **버튼→감지→알림 전체 파이프라인**을 실제로 검증: 13:46 KST에 텔레그램 버튼을 누름 →
  13:50:21 KST 자동 폴링 슬롯에서 `check` job이 트리거를 감지 → 같은 실행 안에서 `notify` job이
  자동으로 이어져 13:51:09 KST에 `notify_stock_price.py` 실행 완료 → 텔레그램 메시지 수신 확인.
  **사람이 GitHub 쪽에서 아무것도 누르지 않았는데도 버튼 입력이 최종 메시지로 이어지는 것까지
  end-to-end로 검증됨.**

#### 5. 도입 과정에서 새로 발견한 문제 1: private 저장소 Actions 실행 시간 한도

cron-job.org가 5분마다 **빠짐없이** 트리거하기 시작하면서, 그동안 GitHub 자체 스케줄이 대부분
스킵되는 바람에 가려져 있던 문제가 드러났다. 이 저장소가 **private**인데, GitHub Actions
무료 한도는 private 저장소 기준 **월 2,000분**이다. `check_manual_trigger.yml`의 `check`
job이 평일 09~19시(KST) 5분마다 돌면 하루 120회 × 월 22일 ≈ 2,640회 실행되고, GitHub은 실행
1건당 최소 1분으로 반올림 청구하므로 **월 2,640분**이 소요되어 무료 한도를 초과한다. 이는
프로젝트 초기부터 지켜온 "카드 등록 불필요" 제약과 정면으로 충돌한다.

**결정**: 저장소를 **public으로 전환**해 Actions 실행 시간을 무제한 무료로 만든다. 전환 전
`git log --all --full-history -- .env` 및 커밋 히스토리 전체에서 실제 토큰 패턴(`숫자:영숫자`
형태)을 검색해 유출된 비밀값이 없음을 확인했다 (`.env`는 처음부터 커밋된 적 없음, README.md에
등장하는 `TELEGRAM_BOT_TOKEN`은 변수명 설명일 뿐 실제 값 아님).

**전환 완료 (2026-07-22)**: `gh repo edit --visibility public --accept-visibility-change-consequences`로
실제 전환했다 (`gh repo view --json isPrivate` → `false` 확인). 계기는 Actions 분당 한도가 아니라
아래 "Streamlit Cloud 배포 재시도" 절에서 먼저 막혔던 문제 — private 상태로는 Streamlit Cloud
배포 자체가 막혀 있었다.

#### 6. 도입 과정에서 새로 발견한 문제 2: "최대 5분 대기"가 버튼의 사용자 경험과 어긋남

폴링 주기가 5분이면, "지금 현재가 확인" 버튼을 눌러도 **최대 5분**을 기다려야 감지된다. 이건
폴링 방식(GitHub가 능동적으로 물어보는 방식)을 쓰는 한 구조적으로 피할 수 없는 지연이다 —
텔레그램이 먼저 GitHub에 신호를 보내는 방법(webhook)을 쓰지 않는 한, 몇 분 간격으로 계속
"확인 작업"이 돌아야만 한다. 실제로 이번 대화 중 5분 대기 전체 과정을 겪어보니, **"지금"이라는
버튼명이 주는 기대와 실제 경험(최대 5분 지연)이 어긋난다**는 지적이 나왔다.

**검토한 개선안 (결정 전, 방향만 논의)**:
- **(쉬움) cron-job.org 폴링 간격을 5분 → 1분으로 단축**: 저장소를 public으로 전환하면 Actions
  실행 시간 제약이 없어지므로 비용 부담 없이 바로 적용 가능. 아키텍처 변경 없이 설정값만 변경.
  최대 대기시간이 5분 → 1분으로 줄어듦.
- **(근본적) 진짜 webhook 방식 재검토**: 기능 4에서 "새 언어(JS/TS) 학습 부담"을 이유로 기각했던
  webhook을, **Python으로 그대로 배포 가능한 무료 서버리스**(예: Vercel의 Python 런타임, Render
  무료 티어 Flask 앱)를 쓰면 그 기각 이유가 더 이상 유효하지 않을 수 있다는 점을 논의했다. 다만
  이건 시스템에 새 구성요소(상시 공개 엔드포인트, webhook 보안 검증용 secret token)가 하나 더
  늘어나는 것이라 관리 부담이 커진다.

**다음 단계로 제안한 순서**: 우선 1분 간격으로 바꿔 체감을 다시 확인하고, 그래도 부족하면 Python
기반 webhook을 검토한다. **아직 어느 쪽도 착수하지 않았고, 방향성만 기록**해둔다.

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

## 전략적 재검토 (2026-07-22): "텔레그램 유지"는 목적이 아니었다

cron-job.org 이중 트리거를 실제로 구축·검증하고, 그 다음으로 "최대 5분 대기"를 없애기 위한
webhook 방식(Python 서버리스 배포처)을 검토하던 중, 사용자가 이 프로젝트의 **진짜 목적**을
다시 명확히 했다:

> 목적은 원하는(주식 정보 같은) 실시간 빅데이터를 읽어, 원하는 시점에 원하는 방식으로
> 사용자에게 보여주는 것이다. 이 과정에 DB가 쓰여서 학생들이 데이터의 전체 흐름을 알게
> 되면 좋겠다. 이 목적에 맞는다면 지금까지의 작업을 전부 새로 써도 상관없다.

즉 **"텔레그램으로 받는다"는 특정 구현 방식이지 목적 자체가 아니었다.**

### 핵심 발견: 지금까지의 문제 전부가 "Push 방식" 선택에서 파생됨

되짚어보면, 이 대화에서 겪은 문제들 — GitHub Actions `schedule` 미발동, 폴링에 의존하는 수동
트리거의 최대 5분 지연, 그 지연을 줄이려던 cron-job.org 이중 트리거, private 저장소 Actions
분당 한도, webhook을 위한 새 서버 호스팅 필요성 — **전부 "사용자가 원할 때 텔레그램으로 메시지를
push해준다"는 전달 방식 하나를 고정해두고 그 신뢰성/지연을 개선하려다 생긴 문제들**이었다.

### 대안 방향: Push(텔레그램) → Pull(웹 대시보드)

사용자가 "확인하고 싶을 때" 웹페이지를 열어 DB에서 즉시 조회해 보여주는 방식으로 바꾸면:

- **폴링/webhook 자체가 불필요해진다** — 페이지를 여는 행위가 곧 확인 행위이므로 "트리거를
  기다리는" 구조가 사라짐.
- **수집 스케줄이 가끔 스킵돼도 치명적이지 않다** — 지금까지는 스케줄 스킵 = "그 시각 메시지가
  영영 안 옴"이었지만, 대시보드 방식이면 "약간 오래된 데이터가 보임" 정도로 완화됨.
- **데이터 흐름(수집 → 저장 → 조회 → 표시)이 코드 구조상 명확히 분리**되어, "DB로 전체 흐름을
  가르치고 싶다"는 목적에 오히려 더 잘 맞는다.

### 검토한 스택 조합 (결정 전, 방향만 기록)

| 조합 | 장점 | 단점 |
|---|---|---|
| **Turso(DB) + Streamlit(대시보드)** | 순수 Python, `pandas`/`matplotlib` 이미 다루는 커리큘럼과 잘 맞음, Streamlit Community Cloud로 카드 등록 없이 무료 배포 | Streamlit 특유의 "상호작용마다 스크립트 전체 재실행" 모델에 적응 필요 |
| **Turso(DB) + Flask/FastAPI + Jinja2 템플릿** | HTTP 라우팅·템플릿 등 "진짜 웹 개발" 기초 개념을 같이 가르칠 수 있음 | Streamlit보다 보일러플레이트가 많고, 별도 무료 호스팅(Render/PythonAnywhere 등) 필요 |
| **Turso(DB) + Gradio + Hugging Face Spaces** | Streamlit과 비슷한 간편함, HF Spaces가 git 기반 무료 배포 지원 | 원래 ML 데모용이라 "표 형태 대시보드"엔 Streamlit보다 부자연스러움 |
| **정적 페이지(GitHub Pages) + Turso HTTP API 직접 호출** | 별도 서버 호스팅이 전혀 필요 없음(GitHub Pages는 이미 쓰는 GitHub 생태계), 브라우저 JS가 Turso의 libSQL HTTP API를 직접 조회 | DB 접근 토큰이 클라이언트(브라우저)에 노출되므로 **읽기 전용으로 스코프를 제한**해야 함, 서버 사이드 로직(가공/인증)을 못 넣음 |

**다음 단계로 제안**: 아직 어느 조합도 결정하지 않았다. 사용자가 "다른 조합도 생각해보라"고
요청해 위 표를 정리해뒀고, 실제 착수는 추후 결정한다. 이 전환이 확정되면 `CLAUDE.md`의 프로젝트
목표 서술("텔레그램 봇 API로 전송")과 `CURRICULUM.md`의 관련 주차도 함께 재검토가 필요하다.

### 목적 재확인: "웹 개발 기초"가 아니라 "빅데이터 흐름 체험"이 목표

위 표를 두고 "Flask/FastAPI는 웹 개발 기초까지 가르칠 수 있다"는 장점을 제시했더니, 사용자가
목적을 한 번 더 좁혀서 명확히 했다:

> 웹 개발 기초까지 가르치고 싶다는 목표는 없다. 이 프로젝트는 "사용자요구 → 데이터의 수집 →
> 저장 → 가공 → 시각화 → 사용자 확인"으로 이어지는 빅데이터의 흐름을 하나의 연결고리로 직접
> 체험하고 학습하는 것이 목표다.

이 기준으로 위 네 후보를 다시 좁혔다.

**결론(권장): Turso(DB) + Streamlit.** 이유:

- 파이프라인의 각 단계가 **전부 Python으로, 새 프레임워크 개념 추가 없이** 이어진다 — 사용자
  요구(`watchlist.csv`) → 수집(네이버 API) → 저장(Turso INSERT) → 가공(DB에서 SELECT한 원본을
  pandas로 가공, 이동평균/등락률 등을 추가하기 좋은 지점) → 시각화(`matplotlib`, 이미 배운 것
  그대로) → 확인(Streamlit이 렌더링, 사용자가 원할 때 접속).
- **Flask/FastAPI 제외**: HTTP 라우팅·템플릿은 이 프로젝트가 원하지 않는 "웹 개발 기초" 학습을
  끌어들인다.
- **정적 페이지 + Turso HTTP API 직접 호출 제외**: 서버가 필요 없다는 장점은 있지만, 브라우저에서
  조회하려면 시각화를 **JavaScript 차트 라이브러리로 다시 짜야 해서** 이미 배운 `matplotlib`과의
  연속성이 끊긴다 — "가공→시각화" 단계가 Python에서 이탈하는 게 이 목표에는 맞지 않는다.
- **Gradio 제외**: ML 모델 데모용 도구라 표+차트 대시보드 용도로는 Streamlit보다 부자연스럽다.

**제안한 코드 구조**: 파이프라인의 각 단계를 별도 파일/함수로 명확히 분리해서(예: `collect.py` →
`db.py` → `process.py` → `dashboard.py`), 학생이 코드 구조만 보고도 "이게 수집, 이게 저장, 이게
가공, 이게 시각화" 단계를 구분할 수 있게 한다.

**상태**: 방향만 권장한 상태이고, 사용자가 최종 결정 전이다. 결정되면 위 "다음 단계" 절의
`CLAUDE.md`/`CURRICULUM.md` 재검토도 함께 진행한다.

### Streamlit 프로토타입 제작 및 Community Cloud 배포 시도 (2026-07-22)

권장안(Turso + Streamlit)을 확정하기 전에, 가볍게 체험해보기로 하고 `dashboard.py`를 만들었다.
기존 `stock_utils.py`의 `read_watchlist`/`fetch_naver_current_price`/`fetch_naver_intraday_minutes`/
`build_price_chart`를 그대로 재사용해, DB 연동 없이 "Pull 방식이 실제로 어떤 느낌인지"만 확인하는
용도다. 로컬 실행(`python -m streamlit run dashboard.py`)과 같은 Wi-Fi 내 모바일 접속(터미널의
Network URL로 접속)까지 성공적으로 검증했다.

이 과정에서 로컬 `price_history.json`이 GitHub에 이미 반영된 최신 커밋(전날 장마감 후 자동 수집분)
보다 뒤처져 있어 텔레그램(2일치 표시)과 대시보드(1일치 표시)의 표시 내용이 달랐던 것도 확인 —
`git pull`로 로컬을 최신화해서 해결했다 (단순 동기화 문제, 코드 버그 아님).

**Streamlit Community Cloud 배포 중 발견한 버그와 해결**: `share.streamlit.io`에서 "Deploy an app"
시도 중 저장소 이름(`eunsaem-yang/-telebot-naver-stock5days`)을 입력하면 "This repository does
not exist"가 계속 떴다. GitHub 쪽 저장소 접근 권한(OAuth App 승인, GitHub App 설치 등)을 여러
경로로 확인·재설정해봐도 동일했고, 브라우저 개발자 도구(F12 콘솔)로 실제 원인을 확인했다:

```
Warning: An unhandled error was caught from submitForm() RequiredError:
Required parameter repo was null or undefined when calling verifyFileExists.
```

**원인**: 저장소 이름이 **하이픈(`-`)으로 시작**해서, Streamlit Cloud 프론트엔드가 저장소 이름을
파싱하는 과정에서 `repo` 파라미터를 `null`로 만들어버리는 **Streamlit Cloud 쪽의 버그**였다. 권한
문제가 전혀 아니었다 — "Paste GitHub URL" 방식(전체 blob URL 입력)으로도 같은 증상이 재현됐다.

**해결**: `gh repo rename telebot-naver-stock5days`로 저장소 이름에서 맨 앞 하이픈을 제거했다
(`eunsaem-yang/-telebot-naver-stock5days` → `eunsaem-yang/telebot-naver-stock5days`). `gh` CLI가
로컬 git remote URL도 자동으로 새 이름으로 갱신해줬다 (`git fetch`로 정상 연결 확인). 이후 사용자가
cron-job.org에 등록해둔 두 작업(`notify.yml`/`check_manual_trigger.yml` dispatch URL)의 저장소
이름도 새 이름으로 직접 갱신했다. 이 문서(`ROADMAP.md`) 안의 옛 저장소 이름 참조 4곳도 함께
갱신했다.

### Streamlit Cloud 배포 재시도: private 저장소 접근 404 → public 전환으로 해결 (2026-07-22)

이름 변경 후 재시도했으나 새 문제가 나타났다. GitHub URL(`.../blob/main/dashboard.py`)을 입력하면
브라우저 콘솔에 다음이 떴다:

```
GET https://share.streamlit.io/api/v2/github/repository/branches?owner=eunsaem-yang&repo=telebot-naver-stock5days 404 (Not Found)
```

**원인**: 저장소가 여전히 **private**이었다 (`gh repo view --json isPrivate` → `true`). Streamlit
Cloud가 private 저장소에 접근하려면 GitHub에 설치된 Streamlit GitHub App이 해당 저장소에 대한
접근 권한을 별도로 부여받아야 하는데, 이게 없어서 브랜치 조회 자체가 저장소를 못 찾는 것처럼
404로 응답한 것 — 앞서 겪은 하이픈 파싱 버그와는 별개의, 순수 권한 문제였다.

**해결**: 위 "private 저장소 Actions 실행 시간 한도" 절에서 이미 결정만 해두고 미룬 public 전환을
이 시점에 실행했다 (`gh repo edit --visibility public --accept-visibility-change-consequences`).
Streamlit Cloud 접근 문제와 Actions 분당 한도 문제를 동시에 해결하는 선택이었다.

전환 후 재시도 → **배포 성공** ("Your app is in the oven" 빌드 시작 화면 확인). 새 저장소 이름
버그와 private 접근 권한 문제 둘 다 해소됨을 확인했다.

### 배포 후 발견한 버그: 그래프 제목 한글 깨짐 → `packages.txt` 추가, 수동 Reboot 필요 (2026-07-22)

배포된 대시보드를 실제로 열어보니 그래프 위 제목(`build_price_chart()`의 `ax.set_title(...)`)의
한글이 깨져 보였다.

**원인**: `stock_utils.py`의 `plt.rcParams["font.family"] = ["Malgun Gothic", "NanumGothic",
"AppleGothic"]`(Windows/GitHub Actions Ubuntu/macOS를 순서대로 겨냥한 목록)에 있는 폰트가 Streamlit
Cloud의 Linux 컨테이너에는 하나도 설치돼 있지 않았다. GitHub Actions에서는 `sudo apt-get install -y
fonts-nanum`으로 워크플로가 직접 설치했지만(`.github/workflows/notify.yml`,
`check_manual_trigger.yml`), Streamlit Cloud는 워크플로 스크립트를 못 건드리는 대신 저장소 루트의
**`packages.txt`** 파일을 읽어 apt 패키지를 자동 설치해준다.

**해결**: 저장소 루트에 `packages.txt`를 새로 만들고 `fonts-nanum` 한 줄을 추가, 커밋·push했다
(`1cda330`).

**추가로 겪은 문제: push 직후엔 반영되지 않음.** push 후 대시보드를 새로고침해봐도 한글이 계속
깨져 있었다. `packages.txt`/`requirements.txt`를 이미 떠 있는 앱에 나중에 추가한 경우, 일반적인
git push 감지 재배포(앱 재실행 수준)만으로는 apt 패키지 설치 단계가 다시 돌지 않는 것으로 보인다.
**Manage app → ⋮(점 3개) 메뉴 → "Reboot app"으로 수동으로 완전 재빌드를 강제한 뒤에야** 한글이
정상 표시되는 것을 확인했다. 앞으로 `packages.txt`/`requirements.txt`를 바꿀 때 자동 반영이 안
되면 이 수동 Reboot을 우선 시도하면 된다.

### 모바일 홈 화면 접근 시도: PWA 아이콘 설치 실패 → 즐겨찾기로 우회 (2026-07-22)

배포 확인 후 모바일(안드로이드, 삼성 Galaxy S24)에서 대시보드에 빠르게 접근하는 방법을 시도했다.

- Chrome "홈 화면에 추가": 아이콘은 생겼지만 이름이 항상 **"Streamlit"**로 고정되고 편집 불가.
  Streamlit Cloud가 내려주는 PWA 매니페스트의 앱 이름을 그대로 쓰기 때문으로, `dashboard.py`의
  `st.set_page_config(page_title=...)`로는 영향을 줄 수 없는 영역이다 (Community Cloud가 커스텀
  매니페스트/HTML 삽입을 허용하지 않음).
- 기존 아이콘 삭제 후 **삼성 인터넷**으로 재시도(이름 편집 필드 기대) → **"안전하지 않은 앱"** 경고로
  추가 자체가 취소됨. 이는 Play Protect가 `streamlit.app`처럼 많은 앱이 공유하는 도메인에서 생성된
  WebAPK(PWA 설치 패키지)를 낯설다고 판단해 차단하는 것으로, 코드/설정으로 해결할 수 있는 부분이
  아니다.
- **최종 해결**: 홈 화면 앱 아이콘 설치를 포기하고, 브라우저 **즐겨찾기(북마크)**로 저장하는 방식으로
  전환. 이 방식은 WebAPK를 만들지 않아 보안 경고 없이 항상 동작한다. 접근 단계가 한 단계(브라우저 →
  즐겨찾기 탭) 늘어나는 대신 안정적이라는 트레이드오프를 감수하기로 했다.

## Turso 마이그레이션 착수 (코드 구현 완료, 2026-07-22)

"Turso+Streamlit" 방향을 최종 확정한 뒤, 커리큘럼 12·13주가 이미 목표로 삼고 있던 Turso
마이그레이션에 착수했다.

### 구현 내용

- `stock_utils.py`의 `load_price_history()`/`update_price_history()`를 JSON 파일 I/O에서
  `libsql-client` 기반 SQL 쿼리로 교체. `save_price_history()`는 완전히 제거했다 — DB 쓰기는
  `update_price_history()` 호출 시점에 즉시 커밋되므로, JSON 방식처럼 "메모리에서 다 수정한 뒤
  파일 통째로 다시 쓰는" 별도의 저장 단계 자체가 필요 없어졌다 (파일 기반 저장과 DB 기반 저장의
  구조적 차이를 그대로 보여주는 지점이라 커리큘럼 13주에도 그대로 활용 가능).
- 스키마: `price_history(code TEXT, date TEXT, close INTEGER, PRIMARY KEY (code, date))`.
  같은 (종목, 날짜) 조합은 `INSERT ... ON CONFLICT DO UPDATE`로 덮어쓰고, 종목별로 최근
  `NUM_HISTORY_DAYS`(15)개보다 오래된 행은 `DELETE`로 정리한다. 이 업서트/정리 로직은 로컬
  SQLite 파일(`file:` URL)로 실제 실행해 정상 동작을 확인했다 — libSQL이 SQLite와 프로토콜
  호환이라 원격 Turso 없이도 로직 검증이 가능했다.
- `collect_daily_close.py`: `load_price_history()`/`save_price_history()` 호출 자체가 필요 없어져
  제거하고, 종목별로 `update_price_history()`만 바로 호출하도록 단순화.
- `notify_stock_price.py`/`dashboard.py`: `load_price_history()` 시그니처(인자 없음, 반환 형태
  동일)가 그대로 유지되므로 호출부는 수정할 필요가 없었다 — DB 마이그레이션이 저장 계층
  안쪽으로만 국한되도록 설계한 효과.
- `price_history.json` 파일은 삭제했다 (git 히스토리로 복구 가능). 더 이상 어떤 스크립트도
  이 파일을 읽거나 쓰지 않는다.
- `.github/workflows/collect_close.yml`에서 "`price_history.json` 변경분을 저장소에 직접
  커밋·푸시"하던 스텝과 `permissions: contents: write`를 제거했다 — Turso DB 자체가 영속
  저장소이므로 GitHub Actions가 저장소에 다시 쓸 이유가 없어졌다. `notify.yml`과
  `check_manual_trigger.yml`의 `notify` job에는 `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` env를
  추가했다 (둘 다 `load_price_history()`를 거치는 `notify_stock_price.py`를 실행하므로).
- 의도적으로 하지 않은 것: `price_history.json`에 남아있던 기존 데이터를 Turso로 옮기는 백필
  스크립트는 작성하지 않았다. "기능 5" 절에서 이미 사용자가 짚었던 것과 같은 이유다 —
  "파일 내용을 DB로 옮기는 것"은 정적 데이터 이전일 뿐이고, DB 단원의 핵심은 "수집(collection)"
  자체를 가르치는 것이므로, `collect_daily_close.py`가 매일 실행되며 자연스럽게 히스토리가
  다시 쌓이도록 두었다.

### 사용자가 직접 해야 할 것 (코드로 자동화 불가)

Turso 계정 생성과 DB 발급은 브라우저 로그인(`turso auth login`/`signup`)이 필요해 에이전트가
대신할 수 없다 — 과거 텔레그램 봇 토큰, GitHub 저장소 생성과 동일한 종류의 "사용자만 할 수
있는" 단계다.

- [x] `turso auth signup`(최초 가입) → `turso db create telebot-stock` → `turso db show
      telebot-stock --url` / `turso db tokens create telebot-stock`로 `TURSO_DATABASE_URL`/
      `TURSO_AUTH_TOKEN` 발급 (`README.md` "4. 내 Turso DB 만들기" 절 참고, 과정에서 겪은
      문제는 아래 "알려진 이슈" 참고)
- [x] 로컬 `.env`에 두 값 등록, `collect_daily_close.py` 실제 실행으로 Turso DB 저장·조회까지
      검증 완료 (2026-07-22)
- [x] 사용자가 CLI 인증(계정 토큰 노출 우려로 로그아웃했던 세션)부터 직접 다시 로그인하고,
      기존 DB를 `turso db destroy`로 지운 뒤 같은 이름(`telebot-stock`)으로 재생성 → URL/토큰
      재발급 → `.env` 갱신까지 전 과정을 사용자가 직접 수행, `collect_daily_close.py`로 재검증
      완료 (2026-07-22). 이번엔 토큰을 대화창에 붙여넣지 않고 본인 터미널에서만 다뤘다.
- [x] GitHub 저장소 Settings → Secrets에 두 값 등록 (`notify.yml`/`collect_close.yml`/
      `check_manual_trigger.yml`이 사용). 등록 첫 시도에서 `collect_close.yml`이 실패했는데,
      원인은 Secrets가 아니라 **로컬에서 완료한 코드 변경 전체가 그때까지 GitHub에 push되지
      않아** 저장소에는 여전히 옛날 워크플로(git commit/push 방식)가 남아있었기 때문이었다 —
      실패 로그에 `git push` 충돌 메시지가 찍혀 바로 알아챌 수 있었다. `git add`(관련 파일만
      선별, `.env`/무관한 미완성 파일 제외) → `commit` → `push` 후 `collect_close.yml`을
      `workflow_dispatch`로 재실행해 **Success** 확인 완료 (2026-07-22).
- [ ] Streamlit Community Cloud 앱 Settings → Secrets에 두 값 등록 (`dashboard.py`가 사용)

**현재 상태**: 로컬 실행과 GitHub Actions는 Turso DB 연동까지 완전히 검증됐다
(`collect_close.yml` 수동 실행 Success). Streamlit Cloud만 아직 Secrets 등록 전이라, 배포된
대시보드는 DB 연결 실패로 종가 히스토리 관련 기능만 조용히 비어 있는 상태로 동작한다(코드가
예외를 잡아 로그만 남기고 계속 진행하도록 방어적으로 작성돼 있어, 현재가 조회 자체는 정상
동작한다).

### 알려진 이슈: 계정 가입 브라우저 콜백 타임아웃 → `--headless`로 우회 (2026-07-22)

`turso auth signup` 실행 시 브라우저는 열리지만 "Waiting for authentication..."에서
`Error: authentication timed out, try again`로 실패했다. CLI가 로컬호스트로 열어둔 콜백
포트로 브라우저가 응답을 못 돌려준 것으로 보인다(방화벽/보안 소프트웨어가 원인일 가능성).
`turso auth signup --headless`로 재시도하면 로컬호스트 콜백 대신 웹페이지에 발급된 액세스
토큰을 `turso config set token "..."`으로 직접 붙여넣는 방식이라 이 문제를 우회할 수 있었다.

**주의**: 이 방식으로 발급되는 토큰은 Turso 계정 전체를 관리할 수 있는 토큰이다. 이 과정에서
사용자가 토큰 값을 대화창에 그대로 붙여넣는 일이 있었는데, 대화 기록에서 사후에 지울 수는
없으므로(에이전트에 그런 기능이 없음) **터미널에서 직접 `turso config set token`을 실행하는
쪽을 원칙으로 하고, 부득이 노출됐다면 GitHub Settings → Applications에서 해당 OAuth 연동을
Revoke하는 것으로 대응**했다. DB 단위로 발급하는 `TURSO_AUTH_TOKEN`(`turso db tokens create`)은
이 계정 토큰과 스코프가 분리돼 있어 영향받지 않는다.

> **후속 사건**: 같은 종류의 노출이 2026-07-31에 다시 일어났다(이번에는 붙여넣기가 아니라
> **편집기 선택 영역이 자동 전달**된 경로). 경위·조치·검증은 맨 아래 "토큰 노출 → Turso 토큰
> 교체" 절에 기록해 두었다.

### 알려진 이슈: `libsql://`(WebSocket) 연결이 일부 환경에서 무한 대기 (2026-07-22)

로컬 검증 중 `load_price_history()`/`update_price_history()` 호출이 에러도 없이 응답 없이
멈추는 증상을 발견했다. `TURSO_DATABASE_URL`(`turso db show --url`이 주는 `libsql://` 스킴)이
`libsql_client`에서 WebSocket(`wss://`) 연결로 해석되는데, 이 WebSocket 핸드셰이크가 실행
환경(방화벽/네트워크 정책)에 따라 타임아웃 없이 그냥 멈춰버리는 것으로 확인됐다. 반면 같은
호스트에 `curl https://...`로는 즉시 정상 응답(200)이 왔다.

**해결**: `stock_utils.py`의 `_get_turso_client()`가 접속 직전에 URL을 `libsql://` → `https://`로
치환하도록 수정했다. `libsql-client` 문서상 `http`/`https` 스킴은 `transaction()` API를 못 쓰는
대신 WebSocket 핸드셰이크 자체가 없는데, 이 프로젝트는 각 SQL 문을 독립적으로 실행하고
`transaction()`을 쓰지 않으므로 기능 손실 없이 적용 가능했다. 학교 네트워크처럼 WebSocket을
막는 방화벽 환경에서 학생들이 겪을 수 있는 문제이기도 해서, `.env`에는 그대로 `turso db show`가
주는 `libsql://` 형식을 넣게 하고 변환은 코드가 알아서 하도록 했다(사용자가 스킴을 신경 쓸
필요 없음).

## 알려진 이슈: Streamlit Community Cloud에서 네이버 API 전체가 ConnectTimeout (2026-07-22)

### 증상

Turso Secrets(`TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`)까지 Streamlit Cloud에 정상 등록했는데도
배포된 대시보드에 모든 종목이 "현재가 조회 실패"로 떴다. 로딩 스피너는 정상적으로 멈췄고
Turso 관련 에러는 아니었다.

### 진단 과정

`Manage app` 로그 패널에는 배포(의존성 설치) 로그만 보이고 스크립트 실행 중 `print()` 출력은
전혀 잡히지 않아(Streamlit Cloud 특유의 출력 버퍼링/로그 뷰 한계로 추정), 로그만으로는 원인을
알 수 없었다. `dashboard.py`에 `st.expander`로 감싼 임시 진단 코드를 넣어 화면에 직접
상태 코드/예외를 띄우는 방식으로 우회했다:

```python
with st.expander("🔍 진단 정보 (임시)"):
    ...
    _r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    st.write("상태 코드:", _r.status_code)
```

결과: `m.stock.naver.com`, `api.finance.naver.com` **두 네이버 도메인 모두** 10초
`ConnectTimeout`(TCP 연결 자체가 응답 없음, HTTP 레벨 403 같은 명시적 거부가 아님)으로
실패했다. 특정 엔드포인트 하나의 문제가 아니라 **Streamlit Community Cloud 인프라에서
네이버 도메인 전체로 나가는 연결 자체가 막혀 있는 것**으로 결론 내렸다(네이버 쪽에서 이
클라우드 IP 대역을 차단하고 있을 가능성이 높다 — 같은 코드가 로컬과 GitHub Actions
(Azure 러너)에서는 정상 동작하는 것과 대조적이다).

진단에 썼던 임시 코드는 원인 확인 후 제거했다(`dashboard.py`는 마이그레이션 완료 상태로
복원).

### 대응 방향 (검토 중, 아직 미착수)

코드로 해결할 수 있는 문제가 아니라 호스팅 인프라 자체의 네트워크 제약이라, 몇 가지 방향이
있다:

- **Turso 히스토리만으로 성능 저하 없이 보여주기**: 현재가 조회 실패 시 그 종목 전체를
  건너뛰는(`continue`) 대신, Turso에 이미 저장된 과거 종가만으로라도 그래프를 보여주도록
  `dashboard.py`를 수정. 완전한 기능은 아니지만 최소한 "빈 화면"은 피할 수 있다.
- **다른 무료 호스팅으로 이전**: Render, Fly.io, Hugging Face Spaces 등 다른 IP 대역을 쓰는
  플랫폼에서는 네이버 접근이 막히지 않을 수도 있다 — 다만 시도해보기 전까지는 확실치 않고,
  각 플랫폼의 무료 티어 제약(카드 등록 여부, 슬립 정책 등)도 다시 비교해야 한다.
  `ROADMAP.md`의 "전략적 재검토" 절에서 이미 Flask/FastAPI·Gradio를 검토했던 것과 같은 종류의
  트레이드오프 분석이 필요하다.
- **그대로 두고 알려진 한계로 문서화**: 텔레그램 push 경로(GitHub Actions, Azure 인프라)는
  이 문제와 무관하게 정상 동작하므로, 급하지 않다면 대시보드 쪽 한계로 남겨두고 우선순위를
  낮출 수도 있다.

아직 방향을 정하지 않았다.

**다음 확인 계획**: 진단을 저녁 시간(장 마감 후)에 진행했는데, 네이버 API는 장중/장마감과
무관하게 항상 응답하도록 설계돼 있고(`marketStatus`/`closePrice`로 상태만 다르게 줌) 같은
시각 로컬·GitHub Actions에서는 정상 응답했으며 실패 형태도 "빈 응답"이 아니라 TCP
`ConnectTimeout`이라 시간대 때문일 가능성은 낮다고 판단했다. 그래도 확실히 하기 위해,
**평일 장중(오전 9~15:30 KST)에 대시보드를 다시 열어 동일 증상이 재현되는지 한 번 더
확인한 뒤** 위 세 방향(히스토리만 표시/다른 호스팅 이전/한계로 문서화) 중 하나를 정하기로
했다.

### 하루 뒤 재현 확인 및 "히스토리만 표시" 대응 구현 (2026-07-23)

**재현 확인**: 다음 날 저녁(2026-07-23 21시경)에도 대시보드를 열어 동일 증상이 재현됐다.
처음엔 첫 종목(005930) 로딩 중 화면에 제목과 새로고침 버튼만 보이고 계속 도는 것처럼
보였는데, 확인해보니 `fetch_naver_current_price()`의 `timeout=10` 때문에 종목마다 최대
10초씩 순차로 걸리는 것이었을 뿐 — 실제로는 세 종목 모두 결국 "현재가 조회 실패"로
끝났다. 평일 장중 재확인 전이라 시간대 요인을 완전히 배제하진 못했지만, **이틀 연속(저녁
시간대) 재현**되어 일시적 문제라기보다 지속되는 인프라 제약에 가깝다고 판단, 장중 재확인을
더 기다리지 않고 대응책 중 하나를 바로 적용하기로 했다.

**적용한 대응**: 위 세 방향 중 **"Turso 히스토리만으로 표시"**를 구현했다 (다른 호스팅 이전은
조사·재배포 부담이 커서 보류, 한계로 문서화만 하는 것보다는 실질적 개선이 낫다고 판단).

- `stock_utils.py`: `build_price_chart()`의 `current_price`를 필수에서 **선택 인자(기본값
  `None`)로 변경**. `current_price`가 없고 분봉도 없으면 "오늘" 지점을 아예 추가하지 않고
  과거 종가만으로 선을 그리며, 마지막 지점 빨간 강조 표시도 그때는 생략한다.
  `describe_price_trend()`에 `has_current: bool = True` 인자를 추가해, 현재가가 없을 때는
  "최근 N일 종가 + 현재가 추이" 대신 **"최근 N일 종가 (현재가 조회 실패)"**로 문구를 구분했다.
  두 함수 모두 인자를 추가하는 방식이라 `notify_stock_price.py`의 기존 호출부(항상 현재가
  있음)는 그대로 동작한다.
- `dashboard.py`: `fetch_naver_current_price()`가 `None`을 반환하면 곧바로 건너뛰지 않고,
  Turso `history`에 해당 종목의 과거 종가가 있는지 먼저 확인한다. 있으면
  `st.warning("...현재가 조회 실패 — 저장된 과거 종가만 표시합니다")` 안내 후
  `build_price_chart(code, code, daily_closes)`로 히스토리만 그려 보여준다 (종목명은
  `watchlist.csv`에 없고 네이버 API 응답에서만 오므로, 조회 실패 시엔 종목코드로 대체).
  과거 종가마저 없으면 기존처럼 경고만 남기고 건너뛴다. 이 fallback 경로에서는
  `fetch_naver_intraday_minutes()`를 호출하지 않는다 — 같은 네이버 도메인이 막혀있다면
  어차피 실패할 호출을 추가해 종목당 대기 시간만 늘리기 때문.
- 로컬에서 `build_price_chart(code, code, daily_closes)` (current_price 생략)를 직접 호출해
  정상적으로 PNG가 생성되고, `describe_price_trend(..., has_current=False)`가 의도한 문구를
  반환하는 것까지 확인했다 (네이버 API가 막히지 않는 로컬 환경이라 실제 실패 상황 자체는
  재현할 수 없어 함수 단위로만 검증).

**아직 안 한 것**: 코드는 로컬 검증까지만 마쳤고, 커밋·푸시 후 Streamlit Cloud 재배포까지
확인하는 건 다음 단계다. 배포 후 실제로 "현재가 조회 실패 — 저장된 과거 종가만 표시합니다"
경고와 함께 히스토리 그래프가 뜨는지 브라우저로 최종 확인이 필요하다.

### 배포 후 재확인: Reboot으로 네이버 API 연결이 다시 정상화됨 → IP 대역 차단 가능성

커밋(`2ab538d`)을 푸시한 뒤 대시보드를 열었으나 처음엔 이전과 동일하게(첫 종목 이후 계속
도는 것처럼 보임) 증상이 재현됐다. Manage app → **Reboot app**으로 수동 재빌드를 한 뒤
다시 열어보니, 이번엔 **현재가 조회는 물론 오늘 분봉 추이까지 전부 정상적으로 나왔다** —
새로 추가한 "히스토리만 표시" 폴백이 아니라 원래의 정상 경로(현재가 + 분봉)로 작동했다.

**의미**: 재부팅만으로 네이버 API 연결이 다시 살아났다는 건, 이 문제가 "네이버가 Streamlit
Cloud 도메인/사업자 전체를 영구 차단"한 게 아니라 **Streamlit Cloud가 그때그때 할당하는
컨테이너의 특정 egress IP(대역)만 네이버 쪽에서 막고 있었을 가능성**을 시사한다. 앱을
재부팅하면 새 컨테이너(=새 IP)를 받게 되므로, 하필 막힌 IP를 물고 있던 상태에서 재부팅으로
막히지 않은 IP로 바뀌며 우연히 풀린 것으로 추정된다. 완전히 검증된 원인은 아니지만(네이버가
어떤 IP를 어떻게 차단하는지 우리가 직접 볼 수는 없음), 지금까지의 관찰(이틀 연속 재현 →
재부팅으로 즉시 해소)과 가장 잘 들어맞는 설명이다.

**실질적 의미**: 이 문제가 다시 나타나면 "다른 호스팅으로 이전" 같은 큰 작업을 하기 전에,
**우선 Manage app → Reboot app부터 시도**하는 게 가장 빠르고 저렴한 1차 대응이다. 그리고
오늘 구현한 "히스토리만 표시" 폴백은 재부팅으로도 안 풀리는 경우를 위한 안전망으로 계속
남겨둔다 — 실제 차단 상태에서 폴백이 화면에 뜨는 것 자체는 아직 브라우저로 직접 보지 못했고
(재부팅 후 바로 정상화돼 확인할 기회가 없었음), 로컬 함수 단위 검증에는 이미 통과했다.

### 폴백 UI 실제 확인 + 부가 개선 두 가지 (2026-07-23)

Streamlit Cloud가 다시 정상화되면서 실제 차단 상태의 폴백 화면을 볼 기회가 사라졌기 때문에,
로컬에서 `fetch_naver_current_price()`를 종목 하나(005930)만 실패하도록 몽키패치한 임시
스크립트(리포 밖 스크래치패드에 위치, `dashboard.py`는 건드리지 않음)로 `streamlit run`을
띄워 폴백 UI를 직접 눈으로 확인했다. 이 과정에서 두 가지를 더 개선했다.

**1. 네이버 API 타임아웃 10초 → 3초로 단축**: 실패 시 종목마다 최대 10초씩 순차로 걸리던 것을
줄였다. 정상 응답은 보통 1초 안팎이라 성공 케이스엔 영향이 거의 없고, 겪은 실패 유형이
`ConnectTimeout`(응답 지연이 아니라 연결 자체가 안 됨)이라 짧은 타임아웃으로도 안전하다고
판단했다. `fetch_naver_current_price()`/`fetch_naver_intraday_minutes()` 두 곳만 변경했고,
텔레그램 관련 요청(`timeout=15`)은 그대로 두었다.

**2. 폴백 화면에서 종목명이 코드로만 나오는 문제 수정**: 실제로 폴백을 띄워보니 종목명 없이
코드만 보였다 — `watchlist.csv`에는 애초에 `code`만 있고 종목명은 네이버 API 응답에만 있어서,
그 조회가 실패하면 이름을 알 방법이 없었다. `watchlist.csv`에 `name` 컬럼을 추가하고
(005930=삼성전자, 000660=SK하이닉스, 402340=SK스퀘어, 네이버 API로 직접 재확인한 값),
`stock_utils.py`에 `read_watchlist_names()`를 새로 추가해 `{code: name}` 매핑을 반환하도록
했다. 기존 `read_watchlist()`는 인터페이스를 그대로 유지해(코드 리스트만 반환)
`notify_stock_price.py`/`collect_daily_close.py` 등 다른 호출부는 영향받지 않는다.
`dashboard.py`는 이 매핑을 루프 시작 전 한 번만 읽어 폴백 분기에서 `code` 대신 이름을 쓴다.

**검증**: 로컬 몽키패치 테스트로 005930이 "삼성전자(005930): 현재가 조회 실패 — 저장된
과거 종가만 표시합니다" 경고와 함께 이름까지 정상적으로 나오는 것을 직접 확인했다. 단,
Python 모듈 캐싱 때문에 `streamlit run` 프로세스를 껐다 다시 켜야 새 `stock_utils.py`
내용이 반영된다는 걸 겪었다 — 스트림릿의 자동 리로드는 스크립트를 재실행할 뿐 이미
`sys.modules`에 캐시된 모듈까지 다시 읽어오지는 않기 때문(테스트 진입점이 프로젝트 폴더
바깥에 있어서 더 두드러졌을 수 있음). 프로덕션 배포(Streamlit Cloud)는 매 배포마다 완전히
새 프로세스로 뜨므로 이 캐싱 문제는 해당 없다.

### 재부팅 이후 재발 없음 확인 + 장애 대응 절차 문서화 (2026-07-24)

**관찰**: 2026-07-23 Reboot app으로 복구된 이후, 2026-07-24 저녁 20:05 KST에 대시보드를 다시
확인해도 정상 동작(현재가 조회 성공) 중이었다 — 재부팅 후 최소 하루 가까이 재발이 없었다.
다만 그 사이 구간을 계속 지켜본 건 아니라서(Streamlit Cloud 쪽 접속 로그를 볼 수 없음),
"한 번도 안 끊겼다"가 아니라 "이 두 시점에서는 정상이었다"는 관찰이다. 그래도 "네이버가
영구 차단한 게 아니라 특정 egress IP 대역만 일시적으로 막혔다가 재부팅으로 새 IP를 받으며
풀린다"는 기존 가설과는 들어맞는다.

**대시보드가 안 될 때 대응 절차** (재발 시 바로 시도할 1차 대응):

1. `https://share.streamlit.io/` 접속 후 로그인(GitHub 계정 연동).
2. 앱 목록에서 이 프로젝트(대시보드) 항목을 찾아 클릭하거나, 배포된 대시보드 페이지
   자체를 열어둔 상태에서 화면 오른쪽 아래의 **"Manage app"** 버튼을 클릭한다(앱 소유자로
   로그인돼 있어야 보인다).
3. 오른쪽 아래에 뜨는 관리 패널 하단의 **⋮ (점 3개, 메뉴)** 버튼 클릭 → **"Reboot app"**
   선택.
4. 재부팅에는 1분 내외가 걸린다 — 완료되면 대시보드 페이지를 새로고침해 관심종목 현재가와
   오늘 분봉 그래프가 정상적으로 뜨는지 확인한다.
5. 재부팅 후에도 안 되면(=IP 문제가 아닌 다른 원인일 가능성), 코드 자체는 정상이라도 이미
   구현해둔 "히스토리만 표시" 폴백(`dashboard.py`)이 화면에 뜨는지 확인 — 완전한 빈 화면 대신
   저장된 과거 종가 그래프는 보여야 한다. 그마저 안 뜨면 Turso 쪽(`TURSO_DATABASE_URL`/
   `TURSO_AUTH_TOKEN` Secrets)이나 코드 자체의 문제일 수 있으니 별도로 조사가 필요하다.

## 학생 각자의 외부 cron 범위 확장 검토: 비용 계산 및 공지문 (2026-07-23)

### 배경

2026-07-23 텔레그램 메시지 두 건(00:24, 19:06)이 예정보다 크게 지연 도착한 원인을 역추적하다가,
`check_manual_trigger.yml`을 호출하는 외부 cron(학생 각자 cron-job.org 등에 등록, 위 "cron-job.org
이중 트리거 실제 도입" 절 참고)이 **09:00~18:59 KST 구간에만** 걸려 있어서, 그 이후(저녁 9시 이후)
누른 버튼이 GitHub 네이티브 `schedule`의 지연 실행(수 시간 뒤)에야 겨우 잡혔다는 것을 확인했다.
개선안으로 외부 cron 커버리지를 **09:30~23:55, 5분 간격**까지 넓히는 안을 검토했다.

### 비용 계산: public 유지 vs private 전환

리포가 **public**이면 GitHub Actions 사용 시간이 무제한 무료라 아래 계산은 전부 해당 없음. 문제는
학생이 자기 저장소를 **private**로 두는 경우다 (GitHub Free 플랜: private 저장소 월 2,000분 무료,
Linux 러너 초과분 $0.008/분, job 1회 실행은 실제 소요와 무관하게 최소 1분 단위로 반올림 과금).

09:30~23:55(14시간 25분) 구간, 평일만(월 21.74일 평균), 기존 `notify.yml`(하루 3회)+
`collect_close.yml`(하루 1회) 고정분(월 87분) 포함 시:

| 간격 | 하루 호출 횟수 | 월 총 과금 분 | 무료 2,000분 대비 | 초과 요금(월) |
|---|---|---|---|---|
| 5분 | 174회 | 3,870분 | −1,870분 | **약 $15** |
| 10분 | 87회 | 1,978분 | +22분(위험) | $0 |
| 15분 | 58회 | 1,348분 | +652분 | $0 |
| 20분 | 44회 | 957분 | +1,043분 | $0 |
| 30분 | 29회 | 631분 | +1,369분 | $0 |

**결론**: public 유지가 비용을 원천적으로 없애는 가장 간단한 방법. `.env`의 실제 비밀값은 GitHub
Secrets에 별도 저장되고 리포에 커밋되지 않으므로 public이어도 토큰 노출 위험은 없다. 그래도 굳이
private을 써야 하는 학생은 10분(여유 22분으로 위험)보다 **15분 간격을 권장** — 무료 한도 안에서
가장 짧은 안전한 주기이며, 최악의 경우에도 버튼을 누른 뒤 15분 이내엔 응답이 온다(기존 "몇 시간
지연"에 비해 충분히 개선됨).

### 학생 공지문 초안 (미발송, 문구 다듬기 필요)

> **[알림] 텔레그램 봇 저장소를 private으로 바꾸는 학생만 확인하세요**
>
> 저장소를 그대로 **public**으로 두면 GitHub Actions 실행 시간이 무제한 무료입니다. 코드 내용이
> 공개되는 것 외에 다른 불이익은 없고(`.env`의 토큰 등 비밀값은 GitHub Secrets에 별도 저장되어
> 리포에 커밋되지 않으므로 노출되지 않습니다), 별도 조치 없이 지금처럼 쓰시면 됩니다.
>
> 만약 저장소를 **private**로 바꾸신다면, "지금 현재가 확인" 버튼을 저녁 9시 이후에도 빠르게
> 받아보기 위해 cron-job.org 등록 범위를 09:00~18:59에서 더 넓히는 걸 고려하실 텐데, 이때 **5분
> 간격은 월 약 $15의 GitHub Actions 초과 요금이 발생**할 수 있습니다(무료 한도 월 2,000분 기준).
> private으로 바꾸실 분은 **15분 간격을 권장**합니다 — 무료 한도 안에서 유지되면서도, 최악의 경우
> 버튼을 누르고 최대 15분 안에는 응답을 받을 수 있습니다.
>
> 선택은 각자 자율입니다: (1) public 유지 + 5분 간격 그대로, (2) private 전환 + 15분 이상 간격
> 중 편한 쪽으로 설정하세요.

**상태**: 계산과 초안만 기록. 실제 공지 발송 여부·최종 문구는 사용자가 결정한다.

### 사용자 본인 저장소 반영 및 트러블슈팅 (완료, 2026-07-23)

사용자 본인 저장소는 이미 **public**이라 비용 계산과 무관하게 바로 5분 간격으로 넓혀도 된다.
`check_manual_trigger.yml` 작업의 시간 범위를 09:00~18:59 → **09:30~23:55**로 넓혔다.

- 변경 위치: cron-job.org 콘솔 `https://console.cron-job.org/jobs` → `check_manual_trigger.yml`
  작업 열기 → Schedule → Custom 탭 → Hours `9-23`, Minutes 5분 단위 전체 체크.
- 참고용 API 요청 URL(작업 설정의 "URL" 필드에 이미 입력되어 있음, 브라우저로 직접 접속하는
  용도 아님): `https://api.github.com/repos/eunsaem-yang/telebot-naver-stock5days/actions/workflows/check_manual_trigger.yml/dispatches`

#### 적용 직후 실행 중단 → 오진(PAT 만료) → 실제 원인은 `notify.yml` 작업의 401

변경 직후 GitHub 실행 이력을 확인하니 `check_manual_trigger.yml`이 18:50 KST 이후 2시간 넘게
전혀 실행되지 않았다. 처음엔 "Fine-grained PAT 발급" 절에 이미 남겨둔 만료 리스크를 의심해
GitHub 토큰 페이지(`github.com/settings/tokens?type=beta`)를 확인했으나, **PAT는 2026-10-20까지
유효**하고 최근 사용 이력도 있어 만료가 아니었다 — 오진이었다.

cron-job.org의 작업별 History를 직접 열어보니 실제 상황은 달랐다:
- `check_manual_trigger.yml` 작업: `Successful 204 No Content` — 정상.
- `notify.yml`(하루 3회) 작업: `Failed (HTTP error) 401 Unauthorized` — 이쪽만 실패 중이었다.

같은 PAT를 공유하는데 한쪽만 401이 나는 걸로 봐서 토큰 문제가 아니라 **`notify.yml` 작업에
등록된 Authorization 헤더 자체가 요청에 안 실려가고 있는 상태**로 판단했다 (지난 "트러블슈팅:
401 Unauthorized" 절과 동일한 유형). 실제로 `notify.yml` GitHub 실행 이력에는 오늘자
`workflow_dispatch` 기록이 하나도 없었고, 유일한 알림(19:05)은 cron-job.org가 아니라 GitHub
네이티브 `schedule`이 몇 시간 지연되어 보낸 것이었다 — 즉 이중화 안전장치가 조용히 죽어있던 상태.

**해결**: `notify.yml` 작업의 Authorization 헤더 값을 지우고 `check_manual_trigger.yml` 작업의
값을 그대로 복사해 다시 붙여넣은 뒤 Test run → 그 즉시 GitHub에 `workflow_dispatch` 실행이
생성되고 success로 완료됨을 확인. **재입력 후 비교해보니 헤더 값 자체는 원래와 동일했다** — 즉
값이 틀렸던 게 아니라, cron-job.org UI가 저장된 헤더를 실제 요청에 실어 보내지 않는 상태였다가
재저장으로 다시 정상화된 것으로 보인다. 지난번(7/22) 401도 같은 패턴이었던 것과 일치 —
**cron-job.org 쪽의 재발성 UI 버그**로 결론.

**검증 완료**: `check_manual_trigger.yml`은 21:00 이후에도 5분 간격으로 정상 실행 중임을 GitHub
이력으로 확인. `notify.yml`도 Test run으로 트리거한 실행이 성공으로 완료되고 텔레그램 메시지
수신까지 확인됐다.

**교훈**: 앞으로 cron-job.org 작업이 401로 실패하면, 헤더 값이 맞는지 눈으로 비교하는 것보다
**일단 같은 값을 재입력·재저장해보는 것이 더 빠른 해결책**일 수 있다. PAT 만료 여부는
GitHub 토큰 페이지에서 바로 확인 가능하니 이걸 먼저 배제하고 넘어가면 된다.

## 다음에 이어서 논의할 것 (2026-07-23 기준, 아직 미해결)

빅데이터 파이프라인(사용자요구→수집→저장→가공→시각화→확인) 자체는 구조적으로 완성되어 오늘
각 단계를 직접 검증했지만, 의식적으로 남겨둔 미해결 항목이 세 가지 있다.

1. **`collect_daily_close.py`(장마감 후 종가 수집)에는 cron-job.org 이중 트리거가 없다.**
   오늘 `notify.yml`/`check_manual_trigger.yml` 두 워크플로는 외부 cron 이중화를 점검·수리했지만
   (위 "cron-job.org 이중 트리거 실제 도입", "사용자 본인 저장소 반영 및 트러블슈팅" 절 참고),
   `collect_close.yml`은 여전히 GitHub 네이티브 `schedule`에만 의존한다 — 스킵되면 그날 종가가
   조용히 안 쌓인다. **→ 2026-07-24에 해결, 아래 "collect_close.yml에 cron-job.org 이중 트리거
   추가" 절 참고.**
2. **`load_price_history()`의 Turso 연결에 타임아웃이 없다.** 네이버 API처럼 Turso 접속이
   막히면 최대 5분(aiohttp 기본값)까지 대시보드가 멈출 수 있는데, `concurrent.futures` 스레드
   기반 해결책은 "커리큘럼이 가르치는 개념 수준을 초과한다"는 이유로 구현하지 않기로 했다
   (위 "폴백 UI 실제 확인 + 부가 개선 두 가지" 절 관련 논의 참고). **→ 2026-07-24에 재검토,
   알려진 한계로 최종 확정. 아래 "Turso 타임아웃 해결 방안 재검토" 절 참고.**
3. **Streamlit Cloud ↔ 네이버 API 차단의 근본 원인이 확정되지 않았다.** Manage app → Reboot
   app으로 우연히 풀렸고, Streamlit Cloud 컨테이너의 특정 egress IP 대역이 차단됐을 가능성만
   추정했을 뿐이다 (위 "배포 후 재확인: Reboot으로 네이버 API 연결이 다시 정상화됨" 절 참고).
   재발 가능성은 남아있고, 오늘 추가한 "히스토리만 표시" 폴백이 안전망 역할을 한다.

**다음 대화에서**: 남은 두 가지(2, 3)를 그대로 고칠지("완전히 해결"), 아니면 계속 "알려진
한계"로 문서화만 하고 우선순위를 낮출지 사용자와 다시 논의해서 결정한다.

## collect_close.yml에 cron-job.org 이중 트리거 추가 (2026-07-24, 완료)

위 미해결 1번을 해결했다. `notify.yml`/`check_manual_trigger.yml`과 동일한 패턴으로 세 번째
cron-job.org 작업을 등록했다.

#### 등록 스텝바이스텝

1. `https://console.cron-job.org/jobs` 로그인 → **CREATE CRONJOB**.
2. **Common 탭**: Title에 `collect_close.yml` 같은 구분용 이름, URL에
   `https://api.github.com/repos/eunsaem-yang/telebot-naver-stock5days/actions/workflows/collect_close.yml/dispatches`,
   Request method는 `POST`.
3. **Advanced 탭(Headers)**: 기존 `notify.yml`/`check_manual_trigger.yml` 작업에 등록된
   것과 **같은 PAT**를 그대로 재사용(저장소 단위 권한이라 작업별로 나눌 필요 없음, 새로
   타이핑하기보다 기존 작업 헤더를 복사해 붙여넣는 편이 오타 위험이 적음).
   ```
   Authorization: Bearer <PAT>
   Accept: application/vnd.github+json
   ```
   "Requires HTTP authentication"(Basic Auth 전용 별도 옵션)은 켜지 않는다 — 켜면
   `Authorization` 헤더와 충돌해 401이 난다.
4. **Request Body**: `{"ref":"main"}`
5. **Schedule 탭**: 프리셋이 아니라 **Custom 모드**로 전환(평일만+특정 시각 조합은
   프리셋에서 옵션 자체가 비활성화됨). Minutes `45` / Hours `15` / Days of week 월~금
   체크, Timezone은 반드시 `Asia/Seoul`(UTC로 두면 12~13시간 밀림) — `collect_close.yml`의
   GitHub 네이티브 스케줄(`45 6 * * 1-5` UTC = KST 15:45 평일)과 동일한 시각으로 맞춤.
6. **SAVE** 후 **Test Run**으로 `204 No Content` 확인 → `gh run list --workflow=collect_close.yml`
   (또는 GitHub Actions 웹 페이지)로 방금 `workflow_dispatch` 실행이 성공했는지 확인. 401이
   나면 토큰이 틀린 게 아니라 cron-job.org UI가 저장된 헤더를 요청에 안 실어 보내는 재발성
   버그일 가능성이 높으므로, 헤더 값을 지우고 동일하게 재입력·재저장해본다.

검토했던 대안(노선 채택 안 함): `notify.yml` 작업에 장마감 이후 시각을 하나 더 추가하는 방식.
`notify.yml`은 `notify_stock_price.py`(텔레그램 전송만, DB 저장 없음)를 실행하고
`collect_close.yml`은 `collect_daily_close.py`(DB 저장만, 텔레그램 전송 없음)를 실행하므로
서로 다른 스크립트다 — 시간만 추가하면 원치 않는 4번째 텔레그램 알림만 늘어날 뿐 종가 히스토리는
여전히 안 쌓인다. 두 스크립트의 책임을 분리한 기존 설계를 유지하기 위해 3번째 작업을 별도로
등록하는 쪽을 택했다.

검증: 등록 직후 Test Run → cron-job.org 쪽 `204 No Content` 확인. 로컬에 `gh` CLI가 없어
Homebrew로 설치(`brew install gh`) 후 `gh run list --workflow=collect_close.yml`로 확인한
결과, `workflow_dispatch`(방금 Test Run)와 `schedule`(GitHub 네이티브) 두 이벤트 모두 성공(✓)
확인됨 — 401 없이 인증 통과.

**남은 확인**: Test Run(수동) 성공과 "평일 15:45 KST에 아무 개입 없이 자동으로 도는지"는 별개
문제였던 전례가 있다(위 "cron-job.org 이중 트리거 실제 도입" 절 참고). 다음 평일 15:45 KST
이후 `gh run list --workflow=collect_close.yml`로 자동 `workflow_dispatch` 실행이 찍히는지
한 번 더 확인하면 완전히 마무리된다.

## Turso 타임아웃 해결 방안 재검토 (2026-07-24, 알려진 한계로 최종 확정)

위 미해결 2번을 다시 논의했다. 코드는 변경하지 않고, `libsql_client` 소스까지 확인해 원인과
대안을 짚어본 뒤 기존 결정을 유지하기로 했다.

### 확인한 사실

- `stock_utils.py`의 `_get_turso_client()`가 호출하는 `libsql_client.create_client_sync()`는
  공개 API로 타임아웃을 넘길 방법이 없다. HTTPS 접속 시 라이브러리 내부에서
  `aiohttp.ClientSession(headers=...)`를 타임아웃 인자 없이 생성하므로, 응답이 없으면
  aiohttp 기본값인 **300초(5분)**를 그대로 기다린다.
- 흥미로운 점: `create_client_sync()`가 반환하는 `ClientSync`는 이미 내부적으로 **백그라운드
  스레드 + asyncio 이벤트 루프**로 동기 인터페이스를 흉내내는 구조다. 즉 "스레드 개념을
  넘어선다"고 판단했던 복잡성이 사실 라이브러리 내부엔 이미 숨어 있고, 지금도 학생들은 그
  내부를 몰라도 이 함수를 문제없이 쓰고 있다.

### 검토한 대안 두 가지 (둘 다 채택 안 함)

1. **`concurrent.futures.ThreadPoolExecutor`로 감싸기**: `load_price_history()`의 기존 본문을
   내부 함수로 옮기고, `ThreadPoolExecutor(max_workers=1).submit(...)` +
   `future.result(timeout=10)`로 감싸 10초 안에 안 끝나면 빈 딕셔너리를 반환. 로직은 그대로고
   래퍼만 ~10줄 추가되지만, `ThreadPoolExecutor`/`submit`/`future.result(timeout=...)`라는
   새 개념이 코드에 등장한다.
2. **`aiohttp.ClientSession.__init__`을 몽키패치**: `_get_turso_client()` 안에서 세션 생성
   전에 `__init__`을 감싸 `timeout=aiohttp.ClientTimeout(total=10)`을 기본값으로 끼워 넣는
   방식. 스레드 개념은 전혀 안 나오지만, "다른 라이브러리의 클래스 동작을 실행 중에
   바꿔치기한다"는 더 낯선 기법이 들어가고, `libsql_client`가 내부적으로 계속 aiohttp를
   쓴다는 비공개 구현 세부사항에 의존해 라이브러리 버전이 바뀌면 조용히 무력화될 수 있다.

### 결론

두 방식 모두 대화 중 예시 코드로만 확인하고 실제 반영은 하지 않기로 했다. 결정적인 이유는
**이 문제가 아직 한 번도 실제로 발생한 적이 없다는 것** — 네이버 API 차단(위 관련 절들)은
이틀 연속 실제로 겪었지만, Turso 접속 지연/무응답은 관측된 적이 없는 이론적 위험이다. 일어난
적 없는 문제를 막으려고 학생 예제 코드에 새 개념(스레드든 몽키패치든)을 넣는 것은 커리큘럼
설계 원칙과 맞지 않는다고 판단해 **알려진 한계로 최종 확정**한다.

## 아키텍처 리스크로 명시: 네이버 비공식 API가 완전히 막히면 전체가 정지 (2026-07-24)

위 "Streamlit Cloud ↔ 네이버 API 전체가 ConnectTimeout" 절의 대응책(Reboot app, 히스토리만
표시 폴백)은 모두 **"Streamlit Cloud 컨테이너의 특정 egress IP만 부분적으로 막히는"** 시나리오
전용이다. 대화 중 "네이버가 아예 차단 규칙을 바꾸거나 엔드포인트 자체를 없애버리면 어떻게
되는가"라는 질문이 나와, 그 경우의 영향 범위를 별도로 짚어 리스크로 남겨둔다.

### 왜 부분 차단과 다른가

지금 겪은 문제는 IP 대역 단위라서 로컬 실행·GitHub Actions(Azure 러너)는 영향이 없고
Streamlit Cloud만 흔들렸다. 하지만 네이버 쪽에서 **엔드포인트 자체(`m.stock.naver.com/api/
stock/{code}/basic`)를 없애거나 응답 형식을 바꾸면**, 이건 IP 문제가 아니므로 실행 환경과
무관하게 전부 동시에 실패한다. Reboot app으로 새 IP를 받는 식의 완화책은 이 시나리오에는
전혀 적용되지 않는다.

### 영향 범위가 넓은 이유: 단일 함수에 세 경로가 모두 의존

`stock_utils.py`의 `fetch_naver_current_price()` 하나를 아래 세 곳이 전부 공유한다
(CLAUDE.md에 적힌 "시세 데이터는 네이버 API 하나로 통합"의 이면):

- `notify_stock_price.py` — 텔레그램 알림(현재가 + 오늘 분봉)
- `collect_daily_close.py` — 그날 종가를 Turso DB `price_history`에 저장
- `dashboard.py` — 대시보드 현재가 표시

즉 이 API 하나가 완전히 죽으면 **push(텔레그램)·pull(대시보드) 두 경로 모두, 새로 데이터를
가져오는 기능 전체가 동시에 정지**한다. 데이터 소스를 네이버 하나로 통합한 결정(단순함을
얻은 대가)이 그대로 단일 장애점(SPOF)이 된 것이다.

### 그나마 남는 것과 안 남는 것

- **남는 것**: 이미 Turso DB에 쌓인 과거 종가 히스토리는 그대로 유지된다. 대시보드의
  "히스토리만 표시" 폴백은 계속 옛 그래프 정도는 보여줄 수 있다 — 다만 그 시점 이후로는
  새 데이터가 전혀 안 쌓여 그래프가 멈춘 채로 굳는다.
- **안 남는 것**: 텔레그램 쪽엔 이런 폴백이 없다. 다만 "조회 실패" 메시지라도 계속 오는 건
  아니다 — `notify_stock_price.py`는 전 종목 조회에 실패하면 `if not current_prices:` 분기에서
  stdout에 로그만 남기고 그대로 `return`하므로, 텔레그램으로는 **아무것도 보내지 않는 완전 무음**
  상태가 된다. 사용자 입장에서는 "오늘 알림이 안 왔네" 정도로만 인지되고 이미 익숙한 스케줄
  스킵과 구분도 안 되므로, 장애를 알아채기가 오히려 더 어렵다.
  `collect_daily_close.py`도 같은 이유로 그날부터 히스토리 적재가 완전히 끊긴다.

### 결론

이건 코드로 미리 막을 수 있는 버그가 아니라, **비공식 API를 데이터 소스로 채택한 순간부터
감수하기로 한 근본적인 아키텍처 리스크**다(문서·SLA·문의 채널이 없는 API라 네이버가 언제
바꾸거나 막아도 대응할 방법이 없음). 지금 시점에는 별도 대응책을 마련하지 않고 리스크로만
기록해둔다 — 실제로 이 시나리오가 발생하면 대체 데이터 소스(공공데이터포털 등, 위 "알려진
이슈: 최근 5일 종가가 전부 같은 데이터로 나옴" 절 참고)를 처음부터 다시 검토해야 한다.

## 수업 중 네이버 API 차단 대응 아이디어: 샘플 응답 재생 모드 (2026-07-24, 아이디어만 기록·미착수)

위 SPOF 리스크와는 별개로, "13주 수업 진행 중 특정 회차에 네이버 API가 막히면 그날 수업
자체가 막히는가"라는 질문에서 나온 아이디어. 아직 구현하지 않았고 방향만 남겨둔다.

### 문제

`CURRICULUM.md` 기준 1~3주(개발환경·pandas·matplotlib 문법)는 네이버 API와 무관하지만,
**4주차(API 호출 실습)부터 13주차까지는 전부 API가 실제로 응답한다는 전제 위에 실습이
설계돼 있다.** 학기 중 4주차 이후 아무 시점에나 네이버가 막히면 그날 실습이 그대로 막힌다.

### 검토한 대응 방향: 공공데이터포털로 대체 프로젝트를 만들어두는 방식 (기각)

공공데이터포털 API는 EOD(일별 종가)만 제공해 실시간가를 애초에 대체할 수 없다 — 4·6·8주
(실시간/현재가/분봉 관련 주차)를 못 살린다. `basDd` 필터 무시 문제(위 "알려진 이슈: 최근
5일 종가가 전부 같은 데이터로 나옴" 절)가 지금도 유효한지 재검증도 안 된 상태다. 별도
프로젝트를 통째로 유지보수해야 하는 부담도 커서, 아직 일어나지 않은 리스크에 비해 비용이
과하다고 판단해 기각했다(위 "Turso 타임아웃 해결 방안 재검토" 절에서 내린 판단과 같은 논리).

### 대신 떠올린 아이디어: 샘플 응답 재생 모드

1. API가 정상일 때 `fetch_naver_current_price()`/`fetch_naver_intraday_minutes()`의 실제
   응답을 관심종목별로 JSON 파일 몇 개로 캡처해둔다.
2. 두 함수에 `USE_SAMPLE_DATA` 같은 환경변수 토글을 추가해, 켜져 있으면 실제 HTTP 요청
   대신 저장해둔 샘플 JSON을 그대로 파싱해 반환한다.
3. 수업 당일 네이버가 막히면 토글만 켜고 그대로 진행 — 학생들은 여전히 진짜 JSON 구조·진짜
   그래프를 보고 배우고, 4주차 이후 커리큘럼이 밀리지 않는다.

**공공데이터포털 대체안보다 나은 점**: 그날 실습을 못 하는 상황만 메꾸는 것이라 작업량이
훨씬 작고(응답 캡처 + 함수 두 곳에 분기 하나), 4·6·8주가 요구하는 실시간성도 "재생"이라
문제되지 않는다. 오히려 이 자체가 "비공식 API 의존성 리스크"를 보여주는 살아있는 사례가
되어 `CURRICULUM.md`의 "얻을 수 있는 태도"(완벽한 설계보다 점진적 개선)와도 결이 맞는다.

**한계**: 그날 수업 진행용 임시방편일 뿐, 실제 서비스(텔레그램 push/대시보드)가 막혔을 때의
해법은 아니다 — 그건 위 SPOF 리스크 절에 남긴 내용 그대로 유효하다.

**다음에 이어서**: 실제 구현(샘플 캡처 + 토글 추가) 여부와 시점은 아직 결정 안 함.

## 그래프·텔레그램·대시보드 표시 방식 대개편 (2026-07-27~28)

한 세션 안에서 그래프 가독성 문제(과거 종가 조밀함)를 고치다가, 텔레그램 서식과 대시보드 UI
전반, 그리고 실제 데이터 정합성 버그까지 이어졌다. HANDOFF.md에 심각도·우선순위별로 상세
정리했고, 여기서는 로그 컨벤션에 맞춰 요약만 남긴다.

### 계기: 과거 종가 구간이 오늘 분봉 대비 너무 조밀함

`build_price_chart()`가 x좌표를 점 개수 그대로(`range(len(prices))`)매기다 보니, 분봉이
하루 수백 개인 데 반해 과거 종가는 15일 이하라 그래프 왼쪽 끝에 조밀하게 몰려 보였다.

### 수정 1: x축을 절반씩 강제 분할

과거 종가(0.0~0.5)와 오늘 분봉(0.5~1.0)을 점 개수 비율과 무관하게 절반씩 배치하도록
`_evenly_spaced()` 헬퍼를 추가(`stock_utils.py`). 그림 안 제목은 텔레그램 캡션·대시보드가
이미 같은 문구를 보여줘 중복이라 판단해 제거했고, 가격 라벨은 9pt→13pt로 키웠다.

### 수정 2: 텔레그램 서식 재구성

텍스트 메시지는 종목별 상세를 반복하던 걸 헤더+대표 종목 추이 설명 1회로 줄이고, 종목별
상세(이름 굵게·가격·등락)는 사진 캡션으로 옮겼다(`send_telegram_photo()`에
`parse_mode="HTML"` 추가). 등락 표시를 위해 `format_rate_badge()`를 새로 만들어 텍스트
메시지·캡션이 공유하게 했다("254,000원 🔺 +1.2%" 형태). 하락 세모 이모지는 처음 🔻(빨강
고정)를 썼다가, 한국 증시 관례(하락=파랑/초록 계열)와 안 맞아 몇 차례 후보(🔽, ▼)를 거쳐
▼(꽉 찬 검정 역삼각형, 색상 없음)로 정착했다.

### 수정 3: 대시보드 UI 개편

`st.metric()`이 라벨/값/등락을 고정된 세로 배치·크기로만 보여줘 세밀한 조정이 안 돼,
`st.markdown()` + 인라인 CSS로 직접 그리는 방식으로 교체했다. 등락 색상은 Streamlit 기본값
(상승=초록/하락=빨강)이 한국 증시 관례와 반대라 뒤집었다(상승=빨강/하락=초록). 추이 설명도
종목마다 반복하던 걸 `st.empty()` 자리표시자로 제목 아래 한 번만 표시하도록 바꿨다. 새로고침
버튼을 오른쪽 정렬하려고 `st.columns` → CSS(flexbox) 순으로 시도했으나, 둘 다 모바일
반응형 문제 또는 코드 복잡도 증가가 있어 **원래의 단순한 `st.button()`으로 되돌렸다** — 버튼
위치는 중요한 포인트가 아니라는 사용자 판단.

### 발견한 실제 버그: 장 시작 전에 실행되면 종가가 전날 값으로 오염됨

그래프 dedup 로직을 만들면서 실제 프로덕션 DB를 들여다보다가, `collect_daily_close.py`가
"장마감 후"와 "장 시작 전"을 `info["is_open"]=False`로 똑같이 취급한다는 걸 발견했다.
`collect_close.yml`이 스케줄 지연(이미 알려진 GitHub Actions 신뢰성 한계)으로 자정을 넘겨
실행되면, 그 시점의 "현재가"(=전날 종가 그대로)를 오늘 날짜로 잘못 저장한다 — 실제로
3종목 모두 07/27=07/28 종가가 완전히 동일한 것을 확인했다.

**결정(2026-07-28)**: 코드 수정 안 함. 장이 열리면 dedup 로직이 화면 표시를 즉시 정정하고,
정상 스케줄(15:45 KST) 실행 시 upsert로 DB도 자동 정정되므로 사람이 손댈 필요가 없다는 데
합의했다. 재발 가능성(스케줄이 또 지연되면 같은 현상 재현)은 남지만, 재발해도 동일하게
자동 정정된다.

> **⚠️ 이 결정은 2026-07-30에 뒤집혔다. 아래 "N1 재판단" 절 참고** — 당시에는 "고치려면
> 실행 시각 가드를 새로 만들어야 한다"는 전제였는데, 그 전제가 틀렸다는 게 나중에 드러났다.

### 정리: 죽은 코드 제거

`describe_price_trend()`의 `has_current` 매개변수가 실제로는 어느 호출부에서도 넘겨진 적
없는 죽은 코드였다(대시보드 fallback이 이미 `st.warning()`으로 같은 정보를 보여줘서 연결할
실익도 없다고 판단). 매개변수와 해당 분기를 제거하고, 남은 두 분기가 동일 문자열을 반환하던
중복도 `if intraday_minutes or daily_closes:` 한 줄로 합쳤다.

### 후속 정리: 공용 헬퍼 추출 + Turso 클라이언트 재사용 (2026-07-28)

같은 날 대화를 이어가며 위에서 "아직 남겨둔 것"으로 분류했던 항목들도 마저 처리했다.

- **개수 불일치 해결**: `describe_price_trend()`가 세는 "최근 N일"과 `build_price_chart()`가
  실제로 그리는 일수가 어긋날 수 있던 문제를, `dedupe_daily_closes(daily_closes, today_price,
  intraday_minutes)` 공용 헬퍼로 통일해 해결했다. `build_price_chart()` 내부와
  `describe_price_trend()` 호출부(텔레그램 대표 종목 헤더, 대시보드 추이 문구)가 모두 같은
  헬퍼를 거치므로 항상 같은 개수를 센다.
- **`today_price` 중복 제거**: `notify_stock_price.py`/`dashboard.py`에 각자 있던
  `가격 if (is_open or intraday) else None` 계산을 `resolve_today_price()` 헬퍼로 통일했다.
- **Turso 클라이언트 재사용**: "관심종목이 20개 규모로 늘어나면 어떻게 하는 게 좋은가"라는
  질문에 답하다가, 그 자리에서 구현까지 진행했다. `_get_turso_client()`를 `get_turso_client()`로
  공개 함수화하고, `update_price_history()`에 선택적 `client` 인자를 추가(안 넘기면 기존처럼
  스스로 만들고 닫아 하위 호환 유지). `collect_daily_close.py`는 종목 루프 밖에서 클라이언트를
  한 번만 만들어 재사용하도록 바꿔, 종목 수가 늘어나도 연결·`CREATE TABLE` 반복 비용이 늘지
  않는다. 실제 관심종목과 안 겹치는 가짜 테스트 코드로 클라이언트 공유·기존 호출 방식(client
  생략) 양쪽 다 정상 동작을 확인한 뒤 정리했다.
- **`telebot.py`의 timeout/예외처리 없음**: 1회성 로컬 스크립트라 수정하지 않기로 확정.

이로써 HANDOFF.md에 기록됐던 이번 세션의 Tier2/3 항목이 모두 정리됐다.

## 2·3차 점검: 대개편이 남긴 잔여물 정리 (2026-07-28~29)

위 대개편 직후 1차 점검을 "미해결 없음"으로 닫았는데, 이어진 2차 점검에서 같은 유형의 잔여물이
또 나왔다. 항목별 심각도·판단 근거 등 상세는 `HANDOFF.md` 참고, 여기서는 로그 컨벤션에 맞춰
요약만 남긴다.

### 점검 배경과 교훈

1차에서 제거한 `describe_price_trend()`의 `has_current`와 이번에 제거한 `build_price_chart()`의
`code`/`name`은 **완전히 같은 유형**(어느 호출부에서도 쓰이지 않는 죽은 매개변수)인데, 1차에서는
후자를 놓쳤다. `ruff`는 미사용 import·지역변수는 잡아도 **미사용 함수 인자는 기본 규칙으로 잡지
않기 때문에** 린트로도 안 걸린다. "한 곳에서 어떤 유형의 문제를 고쳤으면 같은 유형을 전수로 훑어야
한다"는 게 이번 교훈 — 자동 도구가 대신 잡아줄 거라 기대할 수 없는 종류의 잔여물이다.

### 수정한 것 11건

- **P1**: CLAUDE.md가 존재하지 않는 `telegram_bot.py`를 참조하던 것을 실제 파일명 `telebot.py`로
  정정. 문서만 보고 따라 하면 그대로 막히는 오류였다.
- **P2**: `fetch_naver_current_price()`가 가격 파싱에 실패했을 때 `price=0`인 dict를 반환하던 것을
  `None` 반환으로 바꿔 **값이 만들어지는 상류에서 차단**했다. 호출부 3곳이 이미 `None`을 "조회
  실패"로 처리하고 있어 새 분기를 만들 필요가 없었고, 0원이 텔레그램·대시보드 표시와 Turso
  히스토리까지 흘러가는 경로가 한 번에 막혔다. 덕분에 `collect_daily_close.py`에 따로 두었던
  `price <= 0` 가드는 도달 불가능해져 제거했다 — 하류 방어를 상류 차단으로 대체한 셈.
- **P3**: `build_price_chart(code, name, ...)`의 죽은 매개변수 제거(위 교훈 참고).
- **P4**: 첫 종목의 오늘 분봉을 헤더 문구용과 그래프용으로 두 번 조회하던 것을, 루프 전에
  `intraday_by_code` dict로 종목당 한 번씩만 선조회하도록 정리했다. API 호출이 줄어드는 것보다,
  조회 시각이 달라 헤더가 세는 일수와 그래프의 점 개수가 어긋날 수 있던 가능성을 없앤 게 크다.
- **P6**: `dashboard.py`가 `unsafe_allow_html=True` 블록에 종목명을 이스케이프 없이 넣고 있었다.
  텔레그램 쪽은 `html.escape()`로 감싸고 있어 **같은 값을 한쪽만 처리하는 비대칭**이었고, 학생이
  "언제 이스케이프가 필요한가"를 잘못 배울 자리라 맞췄다. 같은 블록의 종목코드는 텔레그램도
  이스케이프하지 않으므로 그대로 뒀다 — 목적이 "두 경로를 같게" 하는 것이었기 때문이다.
- **P7**: 대시보드가 상호작용마다(=스크립트 재실행마다) `watchlist.csv`를 두 번씩 읽고 로그도
  그때마다 찍던 것을, 기존 `_cached_*` 패턴대로 캐싱했다. **중요한 건 새로고침 버튼이 이 캐시도
  비우게 함께 고친 것** — `st.rerun()`은 스크립트를 다시 실행할 뿐 캐시를 비우지 않으므로,
  `.clear()`가 없으면 `watchlist.csv`를 편집하고 새로고침을 눌러도 ttl(5분) 동안 예전 목록이
  그대로 보인다. 캐싱을 넣기 전보다 나빠지는 셈이라 이게 빠지면 개선이 아니라 퇴보다.
- **P12**: `describe_price_trend()`가 `intraday_minutes or daily_closes`를 먼저 보는 바람에,
  히스토리가 없는 종목에 "최근 0일 종가 + 현재가 추이"라는 문구를 돌려주던 문제. `daily_closes`를
  먼저 확인하도록 조건 순서를 바꾸고, 없을 때 쓸 문구를 별도 분기로 추가했다.
- **P13**: 히스토리가 없는 종목이 장외 시간에 **빈 그래프**(축과 격자만 있는 PNG)로 전송되던 문제.
- **P15**: `build_price_chart()`가 한글 폰트 후보 3개를 그냥 나열해서, 실행 환경에 없는 이름마다
  matplotlib이 `findfont` 경고를 **글자 요소 하나하나에 대해** 찍어 로그가 수백 줄로 뒤덮이던 문제
  (실측: 차트 1장당 108줄, 4종목이면 400줄 이상). 처음엔 `logging`으로 경고를 끄는 방법을 검토했으나
  **원인이 아니라 증상을 덮는 것**이고 진짜 폰트 문제까지 같이 묻히므로 기각했다. 대신
  `font_manager.fontManager.ttflist`로 **지금 이 환경에 실제로 설치된 폰트만 골라서** `font.family`에
  넘기도록 바꿨다 — 없는 이름을 애초에 요청하지 않으니 경고가 생기지 않는다(실측 0줄).
  한글 폰트가 하나도 없으면 `sans-serif`로 떨어지며 그때는 경고가 그대로 뜨는데, 한글이 깨진다는
  뜻이라 일부러 감추지 않았다.
  검증 중 알게 된 사실: matplotlib은 `font.family` 목록에서 **쓸 폰트를 하나 찾으면 멈추는 게 아니라
  목록 전체를 확인**한다. 그래서 "설치돼 있는 폰트를 맨 앞으로 옮기면 되지 않나"는 접근은 통하지
  않는다(순서만 바꿔 측정했더니 108줄 그대로).
- **P16**: 네이버가 완전히 막혀 **한 종목도 못 가져와도 종료 코드 0**으로 끝나던 문제. 그래서
  GitHub Actions 실행 목록에 녹색 체크만 남고 기본 실패 알림도 오지 않아, 로그를 수동으로 열어보지
  않으면 장애를 알아챌 방법이 없었다. **무음보다 나쁜 상태** — 녹색 체크가 "정상 동작 중"이라고
  적극적으로 잘못된 신호를 준다. "아무것도 못 한 경우"만 1로 끝내고 휴장일(할 일이 없는 정상
  종료)과 부분 실패는 0을 유지하도록 구분했다. `notify_stock_price.py`는 로직이 재사용 목적의
  함수 안에 있어 함수에서 `exit()`를 부르는 대신 `bool`을 반환하고 `__main__`이 종료 코드로
  옮기게 했다 — 이 리포는 이미 `send_telegram_message()` 등이 bool을 반환하는 관례가 있다.
  P11(전 종목 실패 시 텔레그램 무음)을 논의하다 "그런데 실패하면 Actions는 어떻게 보이지?"를
  확인하며 발견했다. 원래 점검 목록에 없던 항목인데 이번 점검에서 가장 값어치 있는 수정이 됐다.
- **P17**: `notify_stock_price.py`가 텔레그램 전송에 **전부 실패해도 종료 코드 0**으로 끝나던 문제.
  전송 실패는 `❌` 로그만 남기고 마지막에 무조건 `return True`를 했기 때문에, 봇 토큰이 만료되거나
  텔레그램 API가 장애여도 Actions에는 녹색 체크만 남았다. 증상(텔레그램 침묵 + 녹색 ✓)이 네이버
  차단과 완전히 같아 원인을 구분할 수 없던 게 진짜 문제였다. `collect_daily_close.py`의 `collected`와
  같은 패턴으로 `sent` 카운터를 두고, P16과 동일한 규칙(**전부 실패=1, 일부라도 성공=0**)을 전송
  쪽에도 적용했다. "텔레그램이 안 오면 네이버가 막힌 것으로 봐도 되나?"라는 사용자 질문에 답하다
  두 원인이 같은 신호를 낸다는 걸 깨달으며 발견한 항목이다.

### P13의 설계 판단

처음엔 "그릴 게 없으면 사진 전송을 건너뛴다"를 검토했다. 하지만 근본 원인은 다른 곳에 있었다 —
`resolve_today_price()`가 현재가를 버리는 근거는 "어차피 마지막 종가와 중복이라서"인데, 그 근거는
**히스토리가 하나도 없을 때는 애초에 성립하지 않는다**. 그래서 전송을 건너뛰는 새 분기를 만드는
대신 조건을 `(is_open or intraday_minutes or not daily_closes)`로 한 개만 늘렸다. 분기 증가 없이
끝났고, 사진을 그대로 보내므로 캡션의 가격·등락 정보도 유지된다.

### `watchlist.csv`가 가변 입력이라는 전제 확인

점검 중 사용자가 관심종목을 수시로 추가·제거한다는 사실이 확인되면서, 그동안 "이론적으로만 가능한
상황"으로 분류했던 P12·P13이 **상시 발생 경로**로 재평가됐다. 핵심은 새로 추가한 종목은 다음
`collect_daily_close.py` 실행 전까지 종가 히스토리가 0건이라는 점 — 즉 "히스토리 없는 종목"은
예외 상황이 아니라 종목을 하나 추가할 때마다 반드시 거치는 정상 상태다. 같은 이유로 종목 수를
고정으로 가정한 서술(CLAUDE.md의 "지금 3종목 규모" 등)도 이번에 문서에서 걷어냈다.

### 수정하지 않기로 한 것과 그 이유

- **등락 표기 이원화**(텔레그램 `format_rate_badge()` vs 대시보드 인라인 HTML): 합치려면 색상
  인자·HTML 모드 플래그 같은 분기가 함수 안에 생겨 복잡도가 오히려 늘어난다.
- **수동 트리거 조기 ack**: `check_manual_trigger.py`가 알림을 실제로 보내기 **전에**
  `getUpdates`에 offset을 넘겨 그 트리거를 확인 처리해버린다. 그래서 뒤이은 `notify` job이
  실패하면(네이버 차단·러너 오류 등) 트리거는 이미 소비된 뒤라 **사용자는 버튼을 눌렀는데
  아무 일도 안 일어난 것으로 보이고, 실패했다는 사실조차 모른다.** 제대로 고치려면 "전송
  성공 후 ack" 구조가 필요한데, 그러려면 지금의 `check`/`notify` job 분리 구조(대부분의
  폴링을 가벼운 job으로 끝내 의존성 설치를 아끼는 설계)를 포기해야 해서 비용이 더 크다.
- **관심종목에서 뺀 종목의 DB 행 잔존**: 교체 1회당 15행이고 표시에는 전혀 영향이 없다.
- **장외 시간 헤더의 "현재가 추이" 문구**: 그래프가 현재가 점을 생략하는 건 의도된 정상 동작이라
  문구만 약간 부정확한 상태인데, 고치려면 1차에서 없앤 `has_current`류 매개변수를 되살려야 한다.
  문구 정확도를 위해 죽은 매개변수를 다시 들이는 건 손해라 판단해 부정확을 감수한다.
- **과거 종가가 1~2개일 때 그래프 왼쪽 절반이 비는 것**: 거래일이 쌓이면 자연히 해소된다.

### 검증 방식

`py_compile`로 문법 확인 + 스크래치패드 임시 스크립트로 함수 단위 확인 + **텔레그램 실전 전송**까지
했다. 특히 P13은 장전 시간대에 실제로 재전송해, 신규 종목의 PNG 크기가 6,825바이트(빈 그래프)에서
9,786바이트(점 1개)로 바뀐 것을 확인했다 — 눈으로 보는 대신 파일 크기 차이로 "실제로 뭔가 그려졌다"를
객관적으로 확인한 사례.

## N1 재판단: "수정 안 함"을 뒤집다 — 체결 시각 기준으로 날짜 결정 (2026-07-30)

위 "발견한 실제 버그: 장 시작 전에 실행되면 종가가 전날 값으로 오염됨"에서 **2026-07-28에
"코드 수정 안 함"으로 확정했던 결정을 이틀 만에 뒤집었다.** 판단이 바뀐 과정 자체가 기록할
가치가 있어 남긴다.

### 왜 그때는 안 고치기로 했나

당시의 판단 근거는 두 가지였다.
1. upsert라서 다음 정상 실행 때 자동 정정되고, 화면 표시도 dedup 로직이 가려준다.
2. **고치려면 `is_trading_day()`(날짜만 봄)·`info["is_open"]`(장중 여부만 봄) 어느 쪽도
   못 보는 "시각"을 판단하는 세 번째 가드를 새로 만들어야 한다** — 학생 예제에 분기를 하나
   더 얹는 비용이 이득보다 크다고 봤다.

2번이 결정적이었다. 그리고 **그 전제가 틀렸다는 게 나중에 드러났다.**

### 전제가 깨진 계기

"스케줄 지연은 늘 있는 문제인데 안고 가는 게 맞는가"를 논의하다가, 지연의 피해가 스크립트마다
다르다는 걸 정리했다 — `notify.yml`은 늦어도 대시보드가 있어 치명적이지 않고,
`check_manual_trigger.yml`은 체감 불편일 뿐이며, **실제로 데이터가 상하는 건 `collect_close.yml`
하나뿐**이었다. 그 하나를 들여다보다가 네이버 응답에 **`localTradedAt`** 필드가 있는 걸 발견했다.

```
"localTradedAt": "2026-07-29T16:10:20+09:00"
```

"언제 실행됐는가"가 아니라 **"이 가격이 언제 체결된 것인가"**를 API가 직접 알려주고 있었다.
가드를 새로 만들 필요 없이 **날짜를 뽑는 출처만 바꾸면 되는 문제**였다.

### 검증 (추측으로 넘어가지 않기)

날짜가 맞게 나오는 것만으로는 부족했다. 조회 시각(16:10)과 값이 거의 같아 **"체결 시각"이
아니라 "응답 생성 시각"일 가능성**이 남아 있었고, 후자라면 새벽 실행 시 무용지물이기 때문이다.
둘을 가르는 실험을 두 단계로 했다.

1. **70초 간격으로 두 번 조회** → 값이 완전히 고정(`2026-07-29T16:10:20` 두 번 동일).
   조회 시각을 따라가지 않으므로 응답 생성 시각이 아니다.
2. **자정을 넘긴 07-30 00:07에 조회** → 4종목 모두 여전히 `2026-07-29T16:10`.
   정확히 N1이 터지는 시간대에서 어제 날짜를 유지하는 것을 확인했다.

이때 판단을 한 번 더 정리했다 — **이 수정은 실패해도 지금보다 나빠지지 않는다.** 밤새 날짜가
유지되면 N1 해결이고, 자정에 넘어가더라도 현재(`datetime.now`)와 같은 동작이다. 최악이
현상 유지라는 점이 적용 결정을 쉽게 만들었다(단 필드 누락·형식 변경 대비 폴백은 필수).

### 구현

- `stock_utils.py`: `fetch_naver_current_price()` 반환 dict에 `traded_at` 추가.
- `collect_daily_close.py`: 루프 밖에서 한 번 계산하던 `today_str`을 없애고, **종목별로**
  `traded_at`에서 날짜를 뽑는다. 거래정지 등으로 마지막 체결일이 다른 종목도 각자 맞는 날짜로
  기록된다. 필드가 없거나 형식이 바뀌면 실행 시각으로 폴백하며 `⚠️` 로그를 남긴다.
- 로그: 시작 줄은 실행 시각을 찍고, 종목별 성공 줄에 **저장 날짜**를 넣었다 — 실행일과 저장일이
  다를 때 로그만 보고 바로 알 수 있어야 하기 때문이다.

### 실전 검증

마침 논의가 자정을 넘겨 진행돼, **N1이 터지는 바로 그 조건에서** 실제로 돌려볼 수 있었다.

```
🚀 종가 수집 시작... (실행 시각 2026-07-30 00:13 KST)
✅ [005930] 삼성전자 20260729 종가 208,500원 기록
✅ [000660] SK하이닉스 20260729 종가 1,401,000원 기록
✅ [005380] 현대차 20260729 종가 353,500원 기록
✅ [088980] 맥쿼리인프라 20260729 종가 9,930원 기록
```

수정 전이었다면 4종목 모두 `20260730`으로 저장돼 `07-28 01:00:53` 때와 같은 오염이 재현됐을
조건이다. upsert라 기존 값을 같은 값으로 덮어쓴 것이어서 DB에는 변화가 없었다.

### 남은 한계 (P18로 등재) → ✅ 해결 (2026-07-31, `is_trading_day()` 가드 제거)

이 수정은 "**자정 넘긴 실행이 잘못된 날짜로 저장**하는 것"은 막지만 "**자정 넘긴 실행이 통째로
스킵**되는 것"은 못 막았다. `collect_daily_close.py` 맨 위의 `is_trading_day()` 가드가
**실행일** 기준이라, 금요일 15:45 작업이 지연돼 토요일 00:xx에 실행되면 새 날짜 로직에 도달하기도
전에 "개장일 아님"으로 종료된다 — 그 경우 금요일 종가는 upsert로도 복구되지 않는 **영구 결측**이다.
실측 지연이 4~8시간이라 15:45+8h=23:45로 아슬아슬하고, 실제로 `07-27` 예정 작업이 `07-28 01:00:53`에
실행된 기록이 있다.

**해결 (2026-07-31): 그 가드를 아예 제거했다.** 등재 당시엔 *"가드에는 '주말·공휴일에 헛돌지
않게 한다'는 원래 목적이 따로 있어 단순 제거가 안 된다"* 고 적고 판단을 미뤘는데, **그 '원래
목적'은 `traded_at` 적용 이후로는 남아 있지 않았다.** 날짜를 체결 시각에서 뽑으므로 휴장일에
실행돼도 마지막 거래일 종가가 그 거래일 날짜로 upsert되어 헛돌 일이 없고, 중복도 생기지 않는다.
반대로 가드는 실행일 기준일 수밖에 없어 **지연될 때마다 데이터를 잃는 쪽으로만 작동**했다.
비용도 작다 — `collect_close.yml`의 cron이 평일(`1-5`)만이라 가드가 실제로 막던 것은 평일 공휴일
연 10~15회뿐이고, 4종목 기준 연 40~60회 추가 호출은 프로젝트 전체 호출량(약 6,000회/년)의 1%
미만이다. `is_trading_day()` 함수 자체와 `holidays` 의존성은 `notify_stock_price.py`·
`check_manual_trigger.py`가 계속 쓰므로 **그대로 남아 있다.**

판단이 바뀐 계기는 빈도 재계산이 아니라 **"관측되면 그때 고친다"는 전략이 이 버그에는 성립하지
않는다**는 것이었다. 이 저장소는 cron-job.org가 15:45에 먼저 처리해 주므로 P18이 발동해도 피해가
드러나지 않아 **여기서는 영원히 관측되지 않고**, 정작 터지는 곳은 이중 트리거가 없는 학생
저장소다. 게다가 **관측되는 순간이 곧 데이터를 잃은 순간**이라 사후 대응이 불가능하다. 관측을
기다리는 전략은 관측 후에 손쓸 수 있을 때만 유효하다.

부작용으로 공휴일 실행 시 로그에 실행일이 아니라 마지막 거래일 날짜가 찍히는데, 동작은 정확하고
헷갈릴 소지만 있어 코드 주석으로 설명해 뒀다.

### 남긴 교훈

**"수정 안 함"은 영구 결정이 아니다.** 07-28의 판단은 그 시점에 알던 정보 위에서는 옳았다 —
새 가드를 만드는 비용이 이득보다 컸다. 틀린 건 결론이 아니라 **"고치려면 가드가 필요하다"는
전제**였고, 그 전제는 API 응답을 한 번 더 들여다보자 무너졌다. 결정을 기록해 둘 때 **결론만
적지 말고 그 결론이 딛고 선 전제를 함께 적어야** 하는 이유다 — 전제가 바뀌었는지 나중에
확인할 수 있어야 결정을 다시 열어볼 수 있다.

## Turso 웹 콘솔로 세팅 가능 확인 — Windows에서 CLI 없이 (2026-07-30)

수업 커리큘럼 8주차(DB 세팅)를 설계하다가, **학생 다수가 Windows인데 Turso CLI 경로가 한 번도
검증된 적이 없다**는 것을 발견해 확인한 결과다.

### 발견한 검증 공백

`README.md`에 *"Windows: 공식 설치 스크립트가 Mac/Linux용이라, WSL을 사용하거나 Mac이 있다면
그쪽에서 진행"* 이라고 적혀 있었지만, 이건 **설치 스크립트의 성질에서 추론해 적은 것**이고 실제로
Windows에서 시도한 기록이 없었다. 위 "알려진 이슈: 계정 가입 브라우저 콜백 타임아웃" 절의
`--headless` 우회도 **OS 문제가 아니라 방화벽/콜백 문제**였고, 그때 어느 OS에서 작업했는지는
기록에 남지 않았다.

즉 강사가 Windows와 macOS를 번갈아 쓰는데도 Turso 세팅은 macOS에서만 했고, **학생 다수가 걸어야
할 길(Windows)을 아무도 걸어보지 않은 상태**였다. 35명 × 2개 분반에게 WSL 설치를 요구하는 것은
Turso 세팅보다 큰 작업이라, 8주차 전체가 무너질 수 있는 위험이었다.

### 확인 방법과 결과

Turso **웹 콘솔**(`turso.tech` 로그인 → Create Database → URL·토큰 발급)만으로 값 두 개를 얻어,
**Windows에서** 실제 연결·쿼리를 검증했다. 검증 스크립트는 `libsql-client`로 접속해
`CREATE TABLE` → `INSERT ... ON CONFLICT`(프로젝트가 쓰는 upsert와 같은 패턴) → `SELECT` →
`DROP`까지 4단계를 확인하도록 만들었고(토큰이 셸 히스토리·대화에 남지 않도록 `getpass`로 입력받고
기존 `.env`와 운영 DB는 건드리지 않음), **전부 통과**했다.

**→ CLI 없이 웹 콘솔만으로 Turso를 쓸 수 있다. Windows에서 확인됨.**

### 커리큘럼에 미치는 영향

8주차 세팅이 **①웹 콘솔 로그인 → ②Create Database → ③URL·토큰 복사 → ④`.env`에 두 줄**로 줄어든다.
CLI 설치, `turso auth signup`, 브라우저 콜백 타임아웃, `--headless` 우회, `turso config set token`,
`turso db create/show/tokens create`가 **전부 불필요**해진다. WSL도 필요 없다.

부수 이득: CLI 인증을 안 거치면 **계정 전체를 관리하는 토큰을 아예 만들지 않는다.** 학생은 DB 단위
토큰만 다루므로, 실수로 노출해도 피해 범위가 그 DB 하나로 제한된다 — 70명 규모에서 의미 있는
안전 마진이다.

### 남긴 교훈

이 공백이 생긴 이유는 **결론(`--headless`로 우회 성공)은 기록했지만 조건(어느 OS에서 했는지)을
기록하지 않았기** 때문이다. 그래서 나중에 "Windows는 검증됐나?"를 되짚을 수 없었다. N1 재판단
절에서 얻은 교훈("결론이 딛고 선 전제를 함께 적어야 한다")과 같은 종류이고, **환경도 그 전제에
포함된다**는 점이 이번에 추가됐다. 앞으로 설치·세팅 관련 기록에는 **확인한 OS를 함께 적는다.**

## 토큰 노출 → Turso 토큰 교체 (2026-07-31, 조치·검증 완료)

**경위**: 편집기에서 `.env`의 `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` 두 줄을 **선택해 둔
상태**였는데, 그 선택 영역이 AI 도구(Claude Code)에 자동으로 전달되어 실제 토큰이 대화에
들어갔다. 붙여넣거나 파일을 출력한 것이 아니라 **선택만 했는데 넘어간** 경로다. 2026-07-22의
계정 토큰 노출(위 "브라우저 콜백 타임아웃" 절 주의 문단)과 같은 종류지만, 그때는 사용자가 직접
붙여넣은 것이었다는 점이 다르다.

**조치**: 노출된 것은 DB 단위 토큰이므로 피해 범위가 그 DB 하나로 제한된다. 그래도 값 자체를
못 쓰게 만드는 것이 유일하게 확실한 대응이라 교체했다. 순서는 **①기존 토큰 전부 무효화 →
②새 토큰 발급 → ③세 곳 반영(로컬 `.env` / GitHub Secrets / Streamlit Secrets)**. Turso의
무효화는 **그 DB의 기존 토큰을 나중에 만든 것까지 한꺼번에 죽이므로** 이 순서여야 하고, ①과 ③
사이에는 아무것도 돌지 않는다. 그래서 **예정된 자동 실행이 없는 금요일 밤**에 진행했다(다음
예정 작업은 월요일 10:05). `TURSO_DATABASE_URL`은 바뀌지 않아 토큰만 교체했다.

**검증 결과**: 세 경로 모두 정상. 로컬 `python collect_daily_close.py` → `✅ … 종가 … 기록`
(upsert라 데이터 영향 없음), GitHub Actions **Run workflow** → 초록 ✓, Streamlit 대시보드 →
**그래프 왼쪽 과거 종가 표시 확인**. 세 번째가 특히 중요한데, `load_price_history()`가 예외를
잡고 `{}`를 반환하므로 **Streamlit은 DB를 못 읽어도 에러 없이 분봉만으로 그래프를 그린다** —
"에러 화면이 없다"는 검증이 되지 못하고, **왼쪽이 비었는지**로만 판별된다.

**재발 방지로 정한 것**: (1) `.env`를 연 상태에서 AI 도구를 쓰지 않는다 — 특히 **선택 영역을
남겨두지 않는다.** (2) 녹화·화면 공유 시 토큰이 보이는 구간을 아예 만들지 않는다(8주차 촬영은
임시 DB로 찍고 즉시 삭제하는 기존 방침 유지). (3) 제출·공유용 이미지는 올리기 전에 토큰이
찍히지 않았는지 확인한다. 학생용 절차는 `FAQ.md` 2절 18번, 수업 사례는 `CURRICULUM.md`
12주차에 반영했다.
