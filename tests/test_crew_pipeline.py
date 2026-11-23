import pytest
from backend.crew_pipeline import get_crewai_llm, build_devops_audit_crew, run_devops_audit_pipeline

def test_get_crewai_llm():
    llm = get_crewai_llm()
    assert llm is not None
    assert llm.model == "gemini-2.5-flash"
    assert "http_options" in llm.client_params

def test_build_devops_audit_crew_structure():
    """3단계 협업 에이전트(지표 검산, 보안·운영 분석, 리포트 작성) 구성 검증"""
    crew = build_devops_audit_crew("2026-11-23")
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3
    
    agent_roles = [a.role for a in crew.agents]
    assert "Audit Metrics Aggregator & Verifier" in agent_roles[0]
    assert "Security & DevOps Operations Analyst" in agent_roles[1]
    assert "Executive Report Writer & Synthesizer" in agent_roles[2]

    for agent in crew.agents:
        assert agent.max_iter == 2
        assert agent.max_retry_limit == 1
        assert agent.max_execution_time == 25

def test_run_devops_audit_pipeline():
    mock_data = {
        "total_usage_logs": 100,
        "total_login_logs": 20,
        "login_failed_count": 2,
        "chat_calls": 10,
        "total_tokens": 1500,
        "frontend_error_count": 0,
        "blocked_event_count": 1,
        "cleanup_event_count": 3,
        "total_articles": 700,
        "sample_login_logs": [],
        "sample_usage_logs": []
    }
    res = run_devops_audit_pipeline("2026-11-23", raw_data=mock_data)
    assert res is not None
    assert "status" in res
    assert "mode" in res
    assert "model" in res
    assert "report_content" in res
    assert "TechPrep-AI" in res["report_content"]
    assert "1. 오늘의 종합 운영 요약" in res["report_content"]
