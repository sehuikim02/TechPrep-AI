#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure environment
CONDA_ENV="/home/aws01/miniconda3/envs/antigravity"
PYTHON="$CONDA_ENV/bin/python"
PYTEST="$CONDA_ENV/bin/pytest"
export LD_LIBRARY_PATH="$CONDA_ENV/lib:${LD_LIBRARY_PATH:-}"

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export BASE_URL

echo "=========================================================="
echo "🚀 TechPrep-AI Playwright E2E 테스트 실행"
echo "🌐 Target URL: $BASE_URL"
echo "=========================================================="

# Check if local server is running when testing localhost
SERVER_PID=""
if [[ "$BASE_URL" == *"127.0.0.1"* || "$BASE_URL" == *"localhost"* ]]; then
    if ! curl -s --connect-timeout 2 "$BASE_URL" > /dev/null 2>&1; then
        echo "⚡ 로컬 통합 테스트 서버 구동 중 (FastAPI + Frontend static)..."
        $PYTHON "$PROJECT_ROOT/backend/serve_all.py" &
        SERVER_PID=$!
        sleep 2
        echo "✅ 로컬 서버 가동 완료 (PID: $SERVER_PID)"
    fi
fi

cleanup() {
    if [ -n "$SERVER_PID" ]; then
        echo "🛑 로컬 테스트 서버 종료 (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Clean old failure artifacts
rm -rf "$PROJECT_ROOT/tests/e2e/artifacts"/* 2>/dev/null || true

# Run pytest
TEST_EXIT_CODE=0
echo "🧪 Pytest E2E 테스트 시작..."
$PYTEST tests/e2e/ -v --tb=short || TEST_EXIT_CODE=$?

echo ""
echo "=========================================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "🎉 모든 E2E 테스트가 성공적으로 통과했습니다!"
else
    echo "⚠️ 일부 E2E 테스트 실패 (Exit code: $TEST_EXIT_CODE)."
    echo "🤖 AI 실패 원인 분석 스크립트를 실행합니다..."
fi

# Run AI failure analyzer
$PYTHON tests/e2e/analyze_failures.py

exit $TEST_EXIT_CODE
