"""
CrewAI Multi-Agent Pipeline for TechPrep-AI
============================================
이 모듈은 TechPrep-AI의 시스템 감사 로그, 보안 이슈, 클라이언트 에러를
역할 분담형 멀티 에이전트(CrewAI) 팀이 단계별로 협업 분석하고 종합 리포트를 도출하는 파이프라인입니다.

[역할 분담 구조]
1. Data & Security Analyst (Agent):
   - 원시 활동 로그, 로그인 시도, 차단/에러 이벤트를 정밀 분석하여 보안 위협 및 이상 징후 파악
2. DevOps Reliability Engineer (Agent):
   - 프론트엔드 에러 스택, 기사 자동 정리 파이프라인 상태, 토큰 사용량 및 인프라 안정성 검증
3. Chief DevOps Officer / Report Synthesizer (Agent):
   - 분석 결과들을 종합하여 실무 관리자를 위한 명확하고 실행 가능한 마크다운 최종 브리핑 생성
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
    특정 날짜의 데이터에 대한 CrewAI 멀티 에이전트 파이프라인(크루)을 구성합니다.
    무한 루프나 대기를 차단하기 위해 max_iter, max_retry_limit, max_execution_time을 명시합니다.
    """
    try:
        from crewai import Agent, Task, Crew, Process
    except ImportError as e:
        raise RuntimeError("CrewAI 패키지가 설치되어 있지 않습니다. `pip install crewai` 필요") from e

    data = raw_data or get_logs_for_date(target_date)
    llm = get_crewai_llm()

    # 1. 보안 및 데이터 분석 에이전트
    security_analyst = Agent(
        role="Security & Authentication Log Analyst",
        goal=f"Analyze authentication attempts and security anomalies for date {target_date}.",
        backstory=(
            "You are a seasoned cyber security expert. You scrutinize every single login failure, "
            "unauthorized/blocked request, and detect credential stuffing or brute force indicators."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=25
    )

    # 2. 인프라 및 신뢰성 엔지니어 에이전트
    reliability_engineer = Agent(
        role="Site Reliability & DevOps Quality Engineer",
        goal=f"Examine client frontend telemetry errors, token usage efficiency, and cleanup pipeline health for {target_date}.",
        backstory=(
            "You are a DevOps and SRE specialist focused on continuous service uptime, zero unhandled errors, "
            "and efficient resource utilization (token consumption and background automation)."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=2,
        max_retry_limit=1,
        max_execution_time=25
    )

    # 3. 최고 운영 책임자 (리포트 종합 에이전트)
    executive_synthesizer = Agent(
        role="Chief DevOps Officer & Executive Synthesizer",
        goal=f"Synthesize security findings and reliability metrics into an actionable, executive Markdown audit report for {target_date}.",
        backstory=(
            "You translate technical anomalies into prioritized executive action items and summary scorecards. "
            "You produce elegant, structured Korean Markdown reports for top-tier management."
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

Recent Login Log Samples:
{data.get('sample_login_logs', [])[:10]}

Recent Usage / Error Log Samples:
{data.get('sample_usage_logs', [])[:15]}
"""

    # 태스크 정의
    task_security = Task(
        description=f"Analyze the following security data and assess threat levels:\n{data_context}\n"
                    "Detail the login failure rate, repeated bad logins, and blocked attacks.",
        expected_output="A concise bullet-point security assessment with severity levels.",
        agent=security_analyst
    )

    task_reliability = Task(
        description=f"Review the frontend errors, token efficiency, and maintenance event logs:\n{data_context}\n"
                    "Assess whether system stability is compromised.",
        expected_output="A concise reliability and error diagnostic summary.",
        agent=reliability_engineer
    )

    task_synthesis = Task(
        description="Using the findings from the Security Analyst and Reliability Engineer, "
                    f"produce a comprehensive Korean Markdown audit report for date {target_date}. "
                    "The report must include: 1. Executive Summary, 2. Security Assessment, 3. Stability & Telemetry, 4. Action Items.",
        expected_output="A complete, professional Korean Markdown audit report ready for management review.",
        agent=executive_synthesizer
    )

    crew = Crew(
        agents=[security_analyst, reliability_engineer, executive_synthesizer],
        tasks=[task_security, task_reliability, task_synthesis],
        process=Process.sequential,
        verbose=False
    )

    return crew

def generate_rule_engine_report(target_date: str, data: Dict[str, Any], note: str = "") -> str:
    """규칙 기반 엔진 리포트 생성기"""
    note_line = f"\n> ℹ️ *{note}*\n" if note else ""
    return f"""# 🤖 TechPrep-AI DevOps CrewAI 감사 리포트 ({target_date})
{note_line}
### 1. 보안 분석가 진단 (Security Analyst)
- 총 로그인 시도: **{data.get('total_login_logs', 0)}건** (실패: **{data.get('login_failed_count', 0)}건**)
- 인가되지 않은 접근 차단: **{data.get('blocked_event_count', 0)}건** 탐지

### 2. 신뢰성 엔지니어 진단 (Reliability Engineer)
- 프론트엔드 텔레메트리 에러: **{data.get('frontend_error_count', 0)}건**
- 챗봇 AI 토큰 소비: **{data.get('total_tokens', 0):,} 토큰** ({data.get('chat_calls', 0)}회 호출)
- 30일 경과 기사 자동 정리: **{data.get('cleanup_event_count', 0)}건** 수행

### 3. 최고 운영 책임자 권장 조치 (Executive Action Items)
1. 로그인 실패율이 감지되면 차단된 IP 목록 및 사용자 상태를 관제탑에서 점검하십시오.
2. 클라이언트 에러 수집 로그(`FRONTEND_ERROR`)를 모니터링하여 프론트엔드 번들 안정성을 유지하십시오.
"""

def run_devops_audit_pipeline(target_date: str) -> Dict[str, Any]:
    """
    CrewAI 파이프라인을 실행하여 결과를 반환합니다.
    API 키가 없거나 외부 통신/쿼터 제한 등 예외 발생 시 신속하고 비파괴적인 fallback 리포트를 반환합니다.
    """
    data = get_logs_for_date(target_date)
    llm = get_crewai_llm()

    if not llm:
        fallback_content = generate_rule_engine_report(
            target_date, data, "CrewAI LLM 미설정으로 인해 룰 기반 멀티 에이전트 진단기가 생성한 보고서입니다."
        )
        return {
            "status": "success",
            "mode": "fallback_rule_engine",
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
    print("\n--- [Pipeline Result Mode: {}] ---".format(res.get("mode")))
    print(res["report_content"][:500] + ("..." if len(res["report_content"]) > 500 else ""))
