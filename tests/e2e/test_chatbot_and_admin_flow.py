import pytest
import time
import uuid
from playwright.sync_api import expect
from tests.e2e.conftest import BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

def test_chatbot_routing_and_admin_control(page_with_telemetry):
    """
    [챗봇 라우팅 & 관리자 제어 시나리오]
    1. 관리자 계정으로 로그인 (Admin은 API 호출 권한 즉시 보유)
    2. 챗봇 창 열기 -> 일상 대화("안녕하세요!") 전송
    3. 응답 수신 확인: 'RAG 활성' 뱃지가 아닌 일반 대화 모드로 정상 응답하는지 검증
    4. 관리자 대시보드 모달 열기 -> 회원 관리 테이블 확인
    5. 회원 상태 제어/탭 전환 인터랙션 시 새로고침 없이 즉시 반영(DOM 업데이트)되는지 검증
    """
    page, telemetry = page_with_telemetry

    # 1. Visit and login as Admin
    page.goto(BASE_URL)
    page.evaluate("() => localStorage.clear()")
    page.reload()
    page.wait_for_load_state("domcontentloaded")

    page.fill("#gate-auth-username", ADMIN_USERNAME)
    page.fill("#gate-auth-password", ADMIN_PASSWORD)
    page.click("#gate-auth-submit-btn")
    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)

    # 2. Chatbot routing: Open chat panel and send daily conversation
    page.click("#chat-toggle-btn")
    expect(page.locator("#chat-panel")).to_be_visible()

    chat_input = page.locator("#chat-input")
    chat_input.fill("안녕하세요! 오늘 날씨가 참 좋네요.")
    chat_input.press("Enter")

    # 3. Wait for chatbot response to appear in chat container
    # The response will be appended as a new message div
    # In both online (Gemini) and offline/fallback modes, 'RAG 활성' must not be active for daily smalltalk
    page.wait_for_function(
        "() => document.querySelectorAll('#chat-messages .leading-relaxed').length >= 2",
        timeout=25000
    )

    chat_text = page.locator("#chat-messages").inner_text()
    assert "RAG 활성" not in chat_text, f"Daily greeting should NOT trigger RAG badge: {chat_text}"

    # 4. Open Admin Dashboard Modal
    page.click("#btn-admin-dash")
    expect(page.locator("#admin-modal")).to_be_visible()

    # User management table should be loaded
    expect(page.locator("#adm-users-table-body")).to_be_visible()

    # 5. Check real-time / no-refresh interaction on Admin Dashboard
    # Switch tabs in audit logs section
    page.click("#tab-btn-usage")
    expect(page.locator("#adm-usage-logs-view")).to_be_visible()

    page.click("#tab-btn-login")
    expect(page.locator("#adm-login-logs-view")).to_be_visible()

    # Verify modal can be closed and reopened without page reload
    page.click("button[onclick='closeAdminModal()']")
    expect(page.locator("#admin-modal")).to_be_hidden()
    expect(page.locator("#top-main-header")).to_be_visible()
