import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import BASE_URL

@pytest.mark.skip(reason="Manual simulation of failure to demonstrate AI failure diagnosis report")
def test_simulated_failure_for_ai_diagnosis(page_with_telemetry):
    """
    고의로 실패를 발생시켜 Telemetry(DOM, 스크린샷, 콘솔/네트워크 로그) 수집 및
    AI 실패 분석 리포트 생성을 시연하기 위한 시뮬레이션 테스트
    """
    page, telemetry = page_with_telemetry
    page.goto(BASE_URL)
    # 고의로 존재하지 않는 셀렉터 매칭 시도
    expect(page.locator("#non-existent-critical-element")).to_be_visible(timeout=1500)
