import os
import sys
import json
import base64
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "e2e" / "artifacts"
REPORT_FILE = ARTIFACTS_DIR / "AI_FAILURE_ANALYSIS_REPORT.md"

def get_gemini_client():
    """Initializes Google GenAI client if available."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        return None, "GEMINI_API_KEY가 설정되지 않았거나 기본값입니다."
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"Google GenAI SDK 초기화 오류: {e}"

def collect_failure_artifacts():
    """Scans ARTIFACTS_DIR for failure reports, telemetry, DOM dumps, and screenshots."""
    failures = []
    if not ARTIFACTS_DIR.exists():
        return failures

    telemetry_files = list(ARTIFACTS_DIR.glob("*_telemetry.json"))
    for tf in telemetry_files:
        test_base = tf.name.replace("_telemetry.json", "")
        screenshot_path = ARTIFACTS_DIR / f"{test_base}_failure.png"
        dom_path = ARTIFACTS_DIR / f"{test_base}_dom.html"

        telemetry_data = {}
        try:
            telemetry_data = json.loads(tf.read_text(encoding="utf-8"))
        except Exception:
            pass

        dom_summary = ""
        if dom_path.exists():
            try:
                full_dom = dom_path.read_text(encoding="utf-8")
                # Truncate DOM if too large to fit in prompt
                dom_summary = full_dom[:3000] + ("\n...[DOM Truncated]..." if len(full_dom) > 3000 else "")
            except Exception:
                pass

        failures.append({
            "test_name": test_base,
            "telemetry": telemetry_data,
            "screenshot_path": str(screenshot_path) if screenshot_path.exists() else None,
            "dom_summary": dom_summary
        })

    return failures

def generate_ai_analysis(client, failure_item):
    """Calls Gemini LLM to diagnose failure root cause and provide fix suggestions."""
    prompt = f"""
당신은 Playwright E2E 테스트 및 풀스택(FastAPI/HTML/Tailwind) 자동화 진단 전문가입니다.
아래는 E2E 테스트 실행 중 발생한 실패 데이터입니다.

### [실패 테스트 이름]
{failure_item['test_name']}

### [테스트 대상 URL]
{failure_item['telemetry'].get('url', 'N/A')}

### [수집된 콘솔 에러 (console.error / pageerror)]
{json.dumps(failure_item['telemetry'].get('console_errors', []) + failure_item['telemetry'].get('page_errors', []), ensure_ascii=False, indent=2)}

### [수집된 HTTP 실패 (4xx/5xx)]
{json.dumps(failure_item['telemetry'].get('http_failures', []), ensure_ascii=False, indent=2)}

### [콘솔 로그 Tail]
{json.dumps(failure_item['telemetry'].get('console_log_tail', []), ensure_ascii=False, indent=2)}

### [실패 시점의 DOM 스냅샷 요약]
```html
{failure_item['dom_summary']}
```

위 데이터를 종합 분석하여 다음 포맷의 한국어 마크다운 리포트를 작성해 주세요:
1. **실패 현상 및 에러 요약**: (정확히 어떤 조건/요소/응답에서 테스트가 실패했는지 간결 서술)
2. **근본 원인 분석 (Root Cause)**: (네트워크 문제, 타이밍/레이스 컨디션, 프론트엔드 DOM 셀렉터 불일치, 백엔드 인증/API 처리 오류 등 명확한 원인)
3. **수정 포인트 및 코드 제안**: (프론트엔드 또는 백엔드 또는 테스트 코드에서 즉시 수정해야 할 파일명과 해결 코드 스니펫)
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"AI 진단 생성 중 오류 발생: {e}"

def generate_rule_based_fallback(failure_item):
    """Fallback diagnostics when LLM is unavailable."""
    telemetry = failure_item['telemetry']
    c_errs = telemetry.get('console_errors', [])
    p_errs = telemetry.get('page_errors', [])
    http_fails = telemetry.get('http_failures', [])

    report = []
    report.append(f"### 🔍 {failure_item['test_name']} 진단 (로컬 규칙 기반 분석)")
    report.append(f"- **대상 URL**: `{telemetry.get('url', 'N/A')}`")
    
    if c_errs or p_errs:
        report.append(f"- **자바스크립트/콘솔 에러**: {len(c_errs) + len(p_errs)}건 감지됨")
        for err in (c_errs + p_errs)[:5]:
            report.append(f"  - `{err}`")

    if http_fails:
        report.append(f"- **HTTP 4xx/5xx 실패**: {len(http_fails)}건 감지됨")
        for h in http_fails[:5]:
            report.append(f"  - `[{h.get('status')}] {h.get('url')}`")

    report.append("\n**추천 점검 포인트**:")
    report.append("1. 백엔드 서버(FastAPI)가 정상 실행 중인지 확인 (`curl http://127.0.0.1:8000/api/server/status`)")
    report.append("2. DOM 셀렉터나 타이밍 이슈인지 확인 (`artifacts/` 폴더 내 실패 스크린샷 및 DOM 파일 확인)")
    report.append("3. 인증 토큰 만료 또는 CORS 차단 여부 확인")
    return "\n".join(report)

def main():
    print("=" * 60)
    print("🛠️ TechPrep-AI 실패 진단 및 AI 분석 리포트 생성기")
    print("=" * 60)

    failures = collect_failure_artifacts()
    if not failures:
        print("✅ 축하합니다! 실패한 테스트 아티팩트가 없습니다. 모든 테스트가 통과했거나 아직 실행되지 않았습니다.")
        REPORT_FILE.write_text("# 🎉 E2E 테스트 성공 리포트\n\n발견된 실패 아티팩트가 없습니다. 모든 E2E 테스트가 성공적으로 통과했습니다.\n", encoding="utf-8")
        print(f"📄 리포트 저장 완료: {REPORT_FILE}")
        return

    print(f"⚠️ 총 {len(failures)}건의 실패 아티팩트가 감지되었습니다. 분석을 시작합니다...")
    client, client_err = get_gemini_client()
    if client:
        print("🤖 Gemini API 클라이언트 연결 성공. 고도화된 AI 원인 분석을 진행합니다.")
    else:
        print(f"ℹ️ {client_err} -> 로컬 휴리스틱 분석 모드로 전환합니다.")

    markdown_sections = [
        "# 🚨 Playwright E2E 테스트 실패 진단 및 AI 분석 리포트",
        f"> **분석 대상 수**: {len(failures)}건  ",
        f"> **아티팩트 경로**: `{ARTIFACTS_DIR}`\n",
        "---"
    ]

    for item in failures:
        print(f"📊 [{item['test_name']}] 분석 중...")
        if client:
            analysis = generate_ai_analysis(client, item)
            markdown_sections.append(f"## 📌 테스트: `{item['test_name']}`")
            if item.get("screenshot_path"):
                markdown_sections.append(f"![실패 스크린샷]({item['screenshot_path']})\n")
            markdown_sections.append(analysis)
        else:
            fallback = generate_rule_based_fallback(item)
            markdown_sections.append(fallback)
        markdown_sections.append("\n---\n")

    full_report = "\n".join(markdown_sections)
    REPORT_FILE.write_text(full_report, encoding="utf-8")
    print("=" * 60)
    print(f"✅ AI 실패 분석 리포트 생성이 완료되었습니다: {REPORT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
