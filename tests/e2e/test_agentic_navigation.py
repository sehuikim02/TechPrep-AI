import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

def test_agentic_navigation_to_article(page_with_telemetry):
    """
    [Agentic Navigation E2E 검증]
    1. 관리자 계정 로그인
    2. 챗봇 열기 -> '쿠버네티스 관련 기사 찾아서 보여줘' 질문 전송
    3. AI 답변에 '📍 대시보드에서 기사 위치로 이동함' 상태 뱃지 노출 확인
    4. 대시보드로 자동 스크롤 및 해당 기사 카드에 .agentic-highlight 강조 효과 부여 확인
    5. '다시 이동' 버튼 클릭 시 재실행 인터랙션 정상 작동 확인
    """
    page, telemetry = page_with_telemetry

    page.goto(BASE_URL)
    page.evaluate("() => localStorage.clear()")
    page.reload()
    page.wait_for_load_state("domcontentloaded")

    # 1. Login
    page.fill("#gate-auth-username", ADMIN_USERNAME)
    page.fill("#gate-auth-password", ADMIN_PASSWORD)
    page.click("#gate-auth-submit-btn")
    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)

    # 2. Open chat panel
    page.click("#chat-toggle-btn")
    expect(page.locator("#chat-panel")).to_be_visible()

    # 3. Ask navigation query
    chat_input = page.locator("#chat-input")
    chat_input.fill("쿠버네티스 관련 기사 찾아서 보여줘")
    chat_input.press("Enter")

    # Wait for answer and UI action badge to be rendered
    badge = page.locator(".agentic-action-badge")
    expect(badge).to_be_visible(timeout=20000)
    expect(badge).to_contain_text("대시보드에서 기사 위치로 이동함")

    # 4. Check that article card has received agentic-highlight class
    highlighted_card = page.locator(".article-card-item.agentic-highlight")
    expect(highlighted_card).to_be_visible(timeout=5000)

    # 5. Test clicking "다시 이동" (Retry Navigate) button
    retry_btn = page.locator(".btn-retry-navigate").first
    expect(retry_btn).to_be_visible()
    retry_btn.click()

    # Should re-trigger highlight on card
    expect(page.locator(".article-card-item.agentic-highlight")).to_be_visible()
