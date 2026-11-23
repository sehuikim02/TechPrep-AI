import pytest
import os
import time
from playwright.sync_api import expect
from tests.e2e.conftest import BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

def test_unauthenticated_first_visit_and_login_logout(page_with_telemetry):
    """
    [인증 & 깜빡임 방지 시나리오]
    1. 미인증 첫 접속 시 상단 헤더(#top-main-header) 미노출 및 전용 로그인 화면(#guest-gate-banner) 단독 노출 확인
    2. 관리자 계정 로그인 진행
    3. 로그인 완료 후 상단 헤더 노출, 대시보드(#main-content-area) 및 사용자 정보 노출 확인
    4. 새로고침 시에도 인증 상태 및 대시보드 유지 확인
    5. 로그아웃 클릭 시 다시 전용 로그인 화면(#guest-gate-banner) 단독 노출 및 헤더 숨김 복귀 확인
    """
    page, telemetry = page_with_telemetry

    # 1. First visit (unauthenticated)
    page.goto(BASE_URL)
    page.evaluate("() => localStorage.clear()")
    page.reload()
    page.wait_for_load_state("domcontentloaded")

    # Header must be hidden, guest-gate-banner must be visible
    expect(page.locator("#top-main-header")).to_be_hidden()
    expect(page.locator("#guest-gate-banner")).to_be_visible()
    expect(page.locator("#main-content-area")).to_be_hidden()

    # 2. Login via dedicated gate form
    page.fill("#gate-auth-username", ADMIN_USERNAME)
    page.fill("#gate-auth-password", ADMIN_PASSWORD)
    page.click("#gate-auth-submit-btn")

    # 3. Verify logged in state
    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)
    expect(page.locator("#main-content-area")).to_be_visible()
    expect(page.locator("#guest-gate-banner")).to_be_hidden()
    expect(page.locator("#nav-username")).to_have_text(ADMIN_USERNAME)

    # 4. Refresh page and verify dashboard persistence
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)
    expect(page.locator("#main-content-area")).to_be_visible()
    expect(page.locator("#guest-gate-banner")).to_be_hidden()
    expect(page.locator("#nav-username")).to_have_text(ADMIN_USERNAME)

    # 5. Logout
    page.click("button[onclick='handleLogout()']")

    # Verify return to unauthenticated gate
    expect(page.locator("#top-main-header")).to_be_hidden(timeout=5000)
    expect(page.locator("#guest-gate-banner")).to_be_visible()
    expect(page.locator("#main-content-area")).to_be_hidden()
