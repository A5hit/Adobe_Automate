import re

import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.ai_generation_page import AiGenerationPage
from pages.landing_page import LandingPage
from pages.login_page import LoginPage
from settings import PW_LOGIN_FINAL_URL_TIMEOUT_MS

ADOBE_APP_URL_RE = re.compile(r"https://(?:new\.)?express\.adobe\.com/.*")


def test_login(page: Page, account: dict[str, str], request: pytest.FixtureRequest) -> None:
    email = account["email"]
    password = account["password"]

    login_page = LoginPage(page, request.node)
    login_page.open()
    login_page.click_students_teachers_tab()
    login_page.enter_email(email)
    login_page.click_continue()
    provider = login_page.wait_for_identity_provider_redirect()

    if provider == "microsoft":
        login_page.microsoft_login_page(email, password)
    elif provider == "google":
        login_page.google_login_page(email, password)
    else:
        raise AssertionError(f"Unsupported identity provider: {provider}")

    login_page.set_step("Wait for Adobe Express app after login")
    try:
        page.wait_for_url(
            ADOBE_APP_URL_RE,
            timeout=PW_LOGIN_FINAL_URL_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError:
        # Do not hard-fail here; landing_page.open() below navigates to Express explicitly.
        pass

    landing_page = LandingPage(page, request.node)
    landing_page.open()
    landing_page.ensure_authenticated()
    landing_page.click_lets_go()

    ai_generation_page = AiGenerationPage(page, request.node)
    try:
        ai_generation_page.wait_until_ready()
    except AssertionError:
        # Retry once in case onboarding controls were late on the first attempt.
        landing_page.click_lets_go()
        ai_generation_page.wait_until_ready()
    ai_generation_page.click_ai()
    ai_generation_page.fill_prompt()
    ai_generation_page.click_generate_when_ready()
    ai_generation_page.wait_for_generation_page_ready()
    ai_generation_page.download_selected_image()
