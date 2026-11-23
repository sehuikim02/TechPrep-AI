import re
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

    # 6. Verify Quick Reply candidates and active class transition
    quick_reply_btns = page.locator(".quick-reply-btn")
    expect(quick_reply_btns.first).to_be_visible()
    count = quick_reply_btns.count()
    assert count >= 2, f"Expected at least 2 quick reply buttons, got {count}"

    # Initially, the 1st button should have active-candidate class
    expect(quick_reply_btns.nth(0)).to_have_class(re.compile(r"active-candidate"))

    # Click second quick reply candidate to navigate and verify active state moves to 2nd
    quick_reply_btns.nth(1).click()
    expect(quick_reply_btns.nth(1)).to_have_class(re.compile(r"active-candidate"))
    expect(quick_reply_btns.nth(0)).not_to_have_class(re.compile(r"active-candidate"))
    expect(page.locator(".article-card-item.agentic-highlight")).to_be_visible()

    # Click third quick reply candidate if present and verify active state moves to 3rd
    if count >= 3:
        quick_reply_btns.nth(2).click()
        expect(quick_reply_btns.nth(2)).to_have_class(re.compile(r"active-candidate"))
        expect(quick_reply_btns.nth(1)).not_to_have_class(re.compile(r"active-candidate"))

    # Test Chat panel docking toggle button
    dock_btn = page.locator("#btn-dock-chat")
    expect(dock_btn).to_be_visible()
    dock_btn.click()
    expect(page.locator("#chat-panel")).to_have_class(re.compile(r"left-0"))

    # Test Chat panel collapse/expand button
    collapse_btn = page.locator("#btn-collapse-chat")
    expect(collapse_btn).to_be_visible()
    collapse_btn.click()
    collapse_btn.click()

def test_agentic_navigation_pending_and_resumed_flow(page_with_telemetry):
    """
    [Agentic Navigation Pending & Follow-up E2E 검증]
    1. 사용자가 키워드 없이 '기사 보여줘' 전송 시 즉시 대시보드 이동을 보류하고 되묻는 문장 출력 확인
    2. 후속 턴에 단답형 키워드('쿠버네티스')만 전송했을 때 보류된 액션을 이어받아 기사 이동 및 하이라이트 정상 실행 확인
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

    # 3. Turn 1: Send query without keyword ("기사 보여줘")
    chat_input = page.locator("#chat-input")
    chat_input.fill("기사 보여줘")
    chat_input.press("Enter")

    # Verify clarifying question is shown and NO highlight or action badge was triggered
    clarification_msg = page.locator(".chat-bubble-model").last
    expect(clarification_msg).to_contain_text("어떤 기사(키워드나 제목, 혹은 관련 기술 주제)로 이동할까요?", timeout=15000)
    expect(page.locator(".agentic-action-badge")).to_have_count(0)
    expect(page.locator(".article-card-item.agentic-highlight")).to_have_count(0)

    # 4. Turn 2: Follow-up with keyword only ("쿠버네티스")
    chat_input.fill("쿠버네티스")
    chat_input.press("Enter")

    # Verify that the pending action was resumed and the card is now highlighted with badge
    badge = page.locator(".agentic-action-badge")
    expect(badge).to_be_visible(timeout=20000)
    expect(badge).to_contain_text("대시보드에서 기사 위치로 이동함")

    highlighted_card = page.locator(".article-card-item.agentic-highlight")
    expect(highlighted_card).to_be_visible(timeout=5000)
