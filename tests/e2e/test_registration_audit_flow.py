import pytest
import time
import uuid
from playwright.sync_api import expect
from tests.e2e.conftest import BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

def test_registration_password_policy_and_admin_audit_log(page_with_telemetry):
    """
    [회원가입 & 감사 로그 연동 시나리오]
    1. 비로그인 전용 화면에서 회원가입 탭으로 전환
    2. 약한 비밀번호(정책 불충족) 입력 시 거부 검증
    3. 보안 정책을 만족하는 신규 계정 생성 및 자동 로그인/대시보드 진입 검증
    4. 신규 계정 로그아웃 후 관리자(admin) 계정으로 로그인
    5. 관리자 대시보드 모달 열기 -> 감사 로그(로그인 시도 로그) 확인
    6. 사용자 필터 또는 목록에서 방금 생성된 사용자 로그인 시도(SUCCESS) 기록 검증
    """
    page, telemetry = page_with_telemetry

    unique_id = uuid.uuid4().hex[:6]
    test_user = f"user_{unique_id}"
    weak_pwd = "password"            # Missing number and symbol
    strong_pwd = "Password123!@"     # Satisfies length >= 8, eng, num, symbol

    # 1. Visit unauthenticated page
    page.goto(BASE_URL)
    page.evaluate("() => localStorage.clear()")
    page.reload()
    page.wait_for_load_state("domcontentloaded")

    # Switch to register tab
    page.click("#gate-tab-register")
    expect(page.locator("#gate-auth-pwd-policy-box")).to_be_visible()

    # 2. Test weak password rejection
    page.fill("#gate-auth-username", test_user)
    page.fill("#gate-auth-password", weak_pwd)
    page.click("#gate-auth-submit-btn")

    # Expect error alert
    expect(page.locator("#gate-auth-error-alert")).to_be_visible()
    expect(page.locator("#gate-auth-error-text")).to_contain_text("비밀번호")

    # 3. Enter strong password and register
    page.fill("#gate-auth-password", strong_pwd)
    page.click("#gate-auth-submit-btn")

    # Successful registration leads to auto dashboard entrance
    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)
    expect(page.locator("#nav-username")).to_have_text(test_user)
    expect(page.locator("#nav-user-badge")).to_have_text("승인대기")

    # 4. Logout new user and login as Admin
    page.click("button[onclick='handleLogout()']")
    expect(page.locator("#guest-gate-banner")).to_be_visible(timeout=5000)

    # Login as Admin
    page.click("#gate-tab-login")
    page.fill("#gate-auth-username", ADMIN_USERNAME)
    page.fill("#gate-auth-password", ADMIN_PASSWORD)
    page.click("#gate-auth-submit-btn")

    expect(page.locator("#top-main-header")).to_be_visible(timeout=10000)
    expect(page.locator("#btn-admin-dash")).to_be_visible()

    # 5. Open Admin Dashboard Modal
    page.click("#btn-admin-dash")
    expect(page.locator("#admin-modal")).to_be_visible()

    # Ensure Login Logs tab is active
    page.click("#tab-btn-login")
    expect(page.locator("#adm-login-logs-view")).to_be_visible()

    # 6. Check login logs table contains test_user
    # Wait for logs to load into table
    expect(page.locator("#adm-login-logs-body")).to_contain_text(test_user, timeout=10000)
    expect(page.locator("#adm-login-logs-body")).to_contain_text("성공")
