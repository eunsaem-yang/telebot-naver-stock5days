#!/usr/bin/env bash
# GitHub Actions 스케줄이 지연/스킵됐을 때 수동으로 워크플로를 실행하고
# 완료될 때까지 기다린 뒤 결과 로그(✅/❌ 등)를 바로 보여주는 스크립트.
#
# 강사용 편의 스크립트다 — GitHub CLI(`gh`)가 설치돼 있고 `gh auth login`이 끝나 있어야
# 동작하므로, 학생 실습에 필수는 아니다. 설치 없이 같은 일을 하려면 GitHub 저장소의
# Actions 탭에서 워크플로를 골라 "Run workflow"를 누르면 된다
# (README.md의 "스케줄 실행이 안 됐을 때" 절 참고).
#
# 사용법:
#   ./run_workflow.sh notify          # 관심종목 현재가 알림 (notify.yml)
#   ./run_workflow.sh collect_close   # 종가 히스토리 수집 (collect_close.yml)
set -euo pipefail

case "${1:-}" in
  notify)
    workflow="notify.yml"
    ;;
  collect_close)
    workflow="collect_close.yml"
    ;;
  *)
    echo "사용법: $0 {notify|collect_close}" >&2
    exit 1
    ;;
esac

echo "🚀 ${workflow} 수동 실행 트리거 중..."
# gh 2.96+은 트리거 직후 방금 만든 run의 URL을 출력해준다. 거기서 run id를 바로 뽑는다.
trigger_output=$(gh workflow run "$workflow")
echo "$trigger_output"
run_id=$(echo "$trigger_output" | grep -oE '/runs/[0-9]+' | grep -oE '[0-9]+' | head -1)

if [[ -z "$run_id" ]]; then
  echo "🔍 URL에서 run id를 못 찾아 목록에서 재조회합니다..."
  sleep 3
  run_id=$(gh run list --workflow="$workflow" --limit=1 --json databaseId -q '.[0].databaseId' 2>/dev/null || echo "")
fi

if [[ -z "$run_id" ]]; then
  echo "❌ 새 실행을 찾지 못했습니다. GitHub Actions 탭에서 직접 확인하세요." >&2
  exit 1
fi

echo "🔍 run ${run_id} 실행 완료 대기 중..."
if gh run watch "$run_id" --exit-status; then
  echo "🎉 실행 성공"
else
  echo "❌ 실행 실패"
fi

echo "📋 스크립트 로그 요약:"
gh run view "$run_id" --log | grep -E "✅|❌|⚠️|🚀|🎉" || echo "(마커 로그 없음)"
