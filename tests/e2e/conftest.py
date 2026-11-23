import os
import json
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

E2E_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = E2E_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Base URL: local dev server or deployment URL
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")

class TelemetryCollector:
    """Collects console errors, page errors, and HTTP 4xx/5xx responses."""
    def __init__(self):
        self.console_errors = []
        self.page_errors = []
        self.http_failures = []
        self.all_console = []

    def attach(self, page):
        def on_console(msg):
            entry = f"[{msg.type.upper()}] {msg.text}"
            self.all_console.append(entry)
            if msg.type == "error":
                self.console_errors.append(msg.text)

        def on_page_error(exc):
            self.page_errors.append(str(exc))

        def on_response(res):
            if res.status >= 400:
                self.http_failures.append({
                    "url": res.url,
                    "status": res.status,
                    "status_text": res.status_text,
                })

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("response", on_response)

    def dump(self):
        return {
            "console_errors": self.console_errors,
            "page_errors": self.page_errors,
            "http_failures": self.http_failures,
            "console_log_tail": self.all_console[-20:]
        }

@pytest.fixture(scope="session")
def browser_instance():
    # Ensure LD_LIBRARY_PATH includes conda lib if needed
    lib_path = "/home/aws01/miniconda3/envs/antigravity/lib"
    current_ld = os.environ.get("LD_LIBRARY_PATH", "")
    if lib_path not in current_ld:
        os.environ["LD_LIBRARY_PATH"] = f"{lib_path}:{current_ld}".strip(":")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        yield browser
        browser.close()

@pytest.fixture
def page_with_telemetry(browser_instance, request):
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    telemetry = TelemetryCollector()
    telemetry.attach(page)

    yield page, telemetry

    # Post-test failure hook
    test_failed = False
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        test_failed = True
    elif hasattr(request.node, "rep_setup") and request.node.rep_setup.failed:
        test_failed = True

    if test_failed:
        test_name = request.node.name
        screenshot_path = ARTIFACTS_DIR / f"{test_name}_failure.png"
        dom_dump_path = ARTIFACTS_DIR / f"{test_name}_dom.html"
        log_path = ARTIFACTS_DIR / f"{test_name}_telemetry.json"

        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception as e:
            print(f"Failed to save screenshot: {e}")

        try:
            dom_dump_path.write_text(page.content(), encoding="utf-8")
        except Exception as e:
            print(f"Failed to save DOM dump: {e}")

        try:
            log_data = telemetry.dump()
            log_data["test_name"] = test_name
            log_data["url"] = page.url
            log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"Failed to save telemetry: {e}")

    context.close()

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
