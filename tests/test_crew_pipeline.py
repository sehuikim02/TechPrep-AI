import pytest
from backend.crew_pipeline import get_crewai_llm, build_devops_audit_crew, run_devops_audit_pipeline

def test_get_crewai_llm():
    llm = get_crewai_llm()
    assert llm is not None
    assert llm.model == "gemini-2.5-flash"
    assert "http_options" in llm.client_params

def test_build_devops_audit_crew():
    crew = build_devops_audit_crew("2026-11-23")
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3
    for agent in crew.agents:
        assert agent.max_iter == 2
        assert agent.max_retry_limit == 1
        assert agent.max_execution_time == 25

def test_run_devops_audit_pipeline():
    res = run_devops_audit_pipeline("2026-11-23")
    assert res is not None
    assert "status" in res
    assert "mode" in res
    assert "report_content" in res
    assert "# 🤖 TechPrep-AI DevOps CrewAI 감사 리포트" in res["report_content"]
