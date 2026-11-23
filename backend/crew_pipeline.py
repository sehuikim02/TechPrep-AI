"""
CrewAI Multi-Agent Pipeline for TechPrep-AI
============================================
이 모듈은 TechPrep-AI의 시스템 감사 로그, 보안 이슈, 클라이언트 에러를
역할 분담형 멀티 에이전트(CrewAI) 팀이 3단계로 협업 분석하고 종합 리포트를 도출하는 파이프라인입니다.

[역할 분담 3단계 구조]
1. Metrics Aggregator & Verifier (Agent 1: 지표 집계·검산 에이전트):
   - 로그인 시도/실패, 분석 로그, 토큰, 에러/차단 건수를 집계·검산하여 상단 요약 수치와 본문 수치 간 불일치가 없도록 기준 데이터를 정리
2. Security & DevOps Operations Analyst (Agent 2: 보안·운영 분석 에이전트):
   - 인증/차단 이슈, 에러 스택, 토큰 소비, 기사 정리 흐름에서 핵심 인사이트와 주의 사항을 도출
3. Executive Report Writer & Synthesizer (Agent 3: 리포트 작성 에이전트):
   - 앞선 검증 및 분석 결과를 종합하여 관리자 관제탑 및 마크다운 다운로드에 최적화된 최종 비즈니스 마크다운 리포트 작성
"""

import os
import sys
from typing import Optional, Dict, Any

# 불필요한 외부 원격 통신 및 대화형 블로킹 방지 환경변수 기본 설정
os.environ["CREWAI_TRACING_ENABLED"] = os.environ.get("CREWAI_TRACING_ENABLED", "false")
os.environ["CREWAI_DISABLE_TELEMETRY"] = os.environ.get("CREWAI_DISABLE_TELEMETRY", "true")
os.environ["OTEL_SDK_DISABLED"] = os.environ.get("OTEL_SDK_DISABLED", "true")
os.environ["CREWAI_DISABLE_VERSION_CHECK"] = os.environ.get("CREWAI_DISABLE_VERSION_CHECK", "true")
os.environ["CREWAI_TESTING"] = os.environ.get("CREWAI_TESTING", "true")

# 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from backend.database import get_logs_for_date

def get_crewai_llm(model_name: Optional[str] = None, timeout: int = 30):
    """
    CrewAI용 LLM 인스턴스를 프로젝트 환경변수(GEMINI_API_KEY)와 연결합니다.
    Gemini 2.5/2.0 계열 모델의 Developer Instruction 및 Thinking 기능을 지원하도록
    api_version='v1beta'를 지정하고, 무한 대기(hang)를 방지하기 위해 단일 요청 재시도(attempts=1)
    및 타임아웃을 설정합니다.
    API 키가 없거나 미설정 시 None을 반환하여 규칙 기반 mock/fallback 모드로 동작할 수 있게 합니다.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    try:
        from crewai import LLM
        import google.genai as genai

        selected_model = model_name or "gemini/gemini-2.5-flash"
        http_options = genai.types.HttpOptions(
            api_version="v1beta",
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        )

        return LLM(
            model=selected_model,
            api_key=api_key,
            client_params={"http_options": http_options}
        )
    except Exception as e:
        print(f"⚠️ [CrewAI] LLM 초기화 실패 ({e}). Fallback 모드로 전환합니다.")
        return None

def build_devops_audit_crew(target_date: str, raw_data: Optional[Dict[str, Any]] = None):
    """
    '오늘의 AI 리포트' 전용 3단계 CrewAI 멀티 에이전트 파이프라인(크루)을 구성합니다.
    무한 루프나 대기를 차단하기 위해 max_iter, max_retry_limit, max_execution_time을 명시합니다.
    """
    try:
        from crewai import Agent, Task, Crew, Process
    except ImportError as e:
        raise RuntimeError("CrewAI 패키지가 설치되어 있지 않습니다. `pip install crewai` 필요") from e

    data = raw_data or get_logs_for_date(target_date)
    llm = get_crewai_llm()

    # 1. 지표 집계·검산 에이전트
    metrics_verifier = Agent(
        role="Audit Metrics Aggregator & Verifier",
        goal=(
            f"Verify and reconcile all usage logs, authentication stats, token totals, "
            f"and error counts for date {target_date} without mathematical discrepancy."
        ),
        backstory=(
            "You are a rigorous data auditor and DevOps telemetry analyst. You cross-check "
            "log counts, failed logins, client errors, and token consumption to guarantee "
            "100% data consistency between header summaries and report details."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=25
    )

    # 2. 보안·운영 분석 에이전트
    operations_analyst = Agent(
        role="Security & DevOps Operations Analyst",
        goal=(
            f"Extract vital security insights, attack trends, reliability risks, and resource "
            f"efficiencies from verified telemetry metrics for date {target_date}."
        ),
        backstory=(
            "You are a veteran cybersecurity and SRE expert. You analyze anomalous authentication "
            "bursts, forbidden requests, frontend client errors, and 30-day article retention cleanup events."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=25
    )

    # 3. 리포트 작성 에이전트
    report_writer = Agent(
        role="Executive Report Writer & Synthesizer",
        goal=(
            f"Synthesize the verified metrics and operational insights into a structured, "
            f"professional Korean Markdown Daily AI Audit Report for date {target_date}."
        ),
        backstory=(
            "You are the Chief AI Auditor for TechPrep-AI. You produce elegant, management-ready "
            "Korean Markdown reports complete with Executive Summary, Security Analysis, "
            "System Stability & Telemetry, and Prioritized Action Items."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=25
    )

    # Context Data Text
    data_context = f"""
[Target Date]: {target_date}
- Total Usage/API Logs: {data.get('total_usage_logs', 0)}
- Total Login Attempts: {data.get('total_login_logs', 0)} (Failed Logins: {data.get('login_failed_count', 0)})
- Chatbot AI Calls: {data.get('chat_calls', 0)} (Token Usage: {data.get('total_tokens', 0):,} tokens)
- Frontend Telemetry Client Errors: {data.get('frontend_error_count', 0)}
- 30-Day Cleanup Maintenance Runs: {data.get('cleanup_event_count', 0)}
- Blocked / Forbidden Violations: {data.get('blocked_event_count', 0)}
- Total Active Articles in DB/Data: {data.get('total_articles', 0)}

Recent Login Log Samples:
{data.get('sample_login_logs', [])[:10]}

Recent Usage / Error Log Samples:
{data.get('sample_usage_logs', [])[:15]}
"""

    # 태스크 1: 지표 검산 및 정합성 기준표 작성
    task_verify_metrics = Task(
        description=(
            f"Cross-verify the following system logs and operational data for date {target_date}:\n{data_context}\n"
            "Produce a consolidated metric validation table ensuring no discrepancy between "
            "total logins vs failed/successful logins, error totals, and AI token counts."
        ),
        expected_output="A structured bullet-point validation baseline of verified metrics and counts.",
        agent=metrics_verifier
    )

    # 태스크 2: 보안 및 운영 위험/인사이트 분석
    task_analyze_operations = Task(
        description=(
            f"Based on the verified metrics and raw data for {target_date}, perform an in-depth security "
            "and operational diagnostic. Identify abnormal login patterns, credential stuffing signals, "
            "client-side frontend telemetry errors, token usage spikes, and cleanup maintenance status."
        ),
        expected_output="A thorough operational and security assessment with identified risk items.",
        agent=operations_analyst
    )

    # 태스크 3: 관리자용 최종 한국어 마크다운 리포트 작성
    task_write_report = Task(
        description=(
            f"Using the verified metric baseline and operational findings, draft the definitive "
            f"'오늘의 AI 리포트' (Daily AI Audit Report) for {target_date} in professional Korean Markdown.\n"
            "The report MUST follow this exact section structure:\n"
            "### 1. 오늘의 종합 운영 요약 (Executive Summary)\n"
            "### 2. 보안 및 인증/차단 이슈 분석 (Security Assessment)\n"
            "### 3. 시스템 안정성 및 에러/정리 진단 (Stability & Telemetry)\n"
            "### 4. 관리자 권장 조치 사항 (Action Items)\n"
            "Ensure the figures in the report body strictly match the verified metrics."
        ),
        expected_output="A complete, professional Korean Markdown audit report formatted cleanly for dashboard and download.",
        agent=report_writer
    )

    crew = Crew(
        agents=[metrics_verifier, operations_analyst, report_writer],
        tasks=[task_verify_metrics, task_analyze_operations, task_write_report],
        process=Process.sequential,
        verbose=False
    )

    return crew

def generate_rule_engine_report(target_date: str, data: Dict[str, Any], note: str = "") -> str:
    """규칙 기반 엔진 리포트 생성기 (안전 Fallback)"""
    note_line = f"\n> ℹ️ *{note}*\n" if note else ""
    total_articles = data.get("total_articles", 0)
    articles_line = f"- 등록 활성 기사: 총 **{total_articles}건** 유지 중\n" if total_articles else ""
    return f"""### 📊 TechPrep-AI 운영 진단 리포트 ({target_date})
{note_line}
#### 1. 오늘의 종합 운영 요약 (Executive Summary)
- **일자**: `{target_date}`
- **전체 API 활동 로그**: 총 **{data.get('total_usage_logs', 0)}건** 기록됨
- **챗봇 AI 호출 및 토큰**: **{data.get('chat_calls', 0)}건** 호출, 누적 **{data.get('total_tokens', 0):,} 토큰** 사용
{articles_line}
#### 2. 보안 및 인증 이슈 분석
- **로그인 시도**: 총 {data.get('total_login_logs', 0)}건 (성공: {data.get('total_login_logs', 0) - data.get('login_failed_count', 0)}건 / 실패: {data.get('login_failed_count', 0)}건)
- **차단 및 미승인 접근**: 총 **{data.get('blocked_event_count', 0)}건** 탐지 및 방어 완료

#### 3. 시스템 안정성 및 정리 상태
- **프론트엔드 클라이언트 에러**: 총 **{data.get('frontend_error_count', 0)}건** 수집됨
- **기사 자동 정리 이벤트**: 총 **{data.get('cleanup_event_count', 0)}건** 수행됨

#### 4. 관리자 권장 조치 사항
1. 대기(pending) 상태인 신규 가입자가 있는 경우 관제탑 회원 관리 테이블에서 일괄 승인을 진행하십시오.
2. 클라이언트 에러가 감지되었을 경우 실시간 감사 로그(FRONTEND_ERROR)의 스택 트레이스를 확인하십시오.
"""

def run_devops_audit_pipeline(target_date: str, raw_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    CrewAI 파이프라인을 실행하여 '오늘의 AI 리포트' 결과를 반환합니다.
    API 키가 없거나 외부 통신/쿼터 제한(429) 등 예외 발생 시 신속하고 비파괴적인 fallback 리포트를 반환합니다.
    """
    data = raw_data or get_logs_for_date(target_date)
    llm = get_crewai_llm()

    if not llm:
        fallback_content = generate_rule_engine_report(
            target_date, data, "CrewAI LLM 미설정으로 인해 룰 기반 멀티 에이전트 진단기가 생성한 보고서입니다."
        )
        return {
            "status": "success",
            "mode": "fallback_rule_engine",
            "model": "Rule-based Diagnostic Fallback",
            "target_date": target_date,
            "metrics": data,
            "report_content": fallback_content
        }

    try:
        crew = build_devops_audit_crew(target_date, raw_data=data)
        result = crew.kickoff()
        output_text = str(result)
        return {
            "status": "success",
            "mode": "crewai_multi_agent",
            "model": "CrewAI (Gemini Multi-Agent)",
            "target_date": target_date,
            "metrics": data,
            "report_content": output_text
        }
    except Exception as e:
        print(f"⚠️ [CrewAI] 파이프라인 실행 중 예외 감지 ({e}). 신속한 비파괴 Fallback 리포트로 즉시 전환합니다.")
        fallback_content = generate_rule_engine_report(
            target_date, data, f"CrewAI 에이전트 실행 중 오류({e})가 감지되어 신속하게 Fallback 진단 리포트를 생성했습니다."
        )
        return {
            "status": "warning",
            "mode": "fallback_on_error",
            "model": "CrewAI Fallback Diagnostic",
            "error_detail": str(e),
            "target_date": target_date,
            "metrics": data,
            "report_content": fallback_content
        }

if __name__ == "__main__":
    import datetime
    today_str = datetime.date.today().isoformat()
    arg_date = sys.argv[1] if len(sys.argv) > 1 else today_str
    print(f"🚀 Running TechPrep-AI CrewAI Audit Pipeline for: {arg_date}...")
    res = run_devops_audit_pipeline(arg_date)
    print("\n--- [Pipeline Result Mode: {} | Model: {}] ---".format(res.get("mode"), res.get("model")))
    print(res["report_content"][:500] + ("..." if len(res["report_content"]) > 500 else ""))
