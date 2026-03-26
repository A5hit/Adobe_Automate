import re
from time import sleep

import pytest
from playwright.sync_api import Page

from pages.landing_page import LandingPage
from pages.login_page import LoginPage
from settings import PW_LOGIN_FINAL_URL_TIMEOUT_MS


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
    page.wait_for_url(
        re.compile(r"https://new\.express\.adobe\.com/.*"),
        timeout=PW_LOGIN_FINAL_URL_TIMEOUT_MS,
    )

    landing_page = LandingPage(page, request.node)
    landing_page.open()
    landing_page.ensure_authenticated()
    sleep(5)
    landing_page.click_lets_go()
    landing_page.expect_create_a_poster_visible()
    landing_page.click_create_a_poster()
    landing_page.click_generate_template()
    sleep(5)
    landing_page.enter_prompt_text()
    sleep(5)
    landing_page.click_generate()
    sleep(5)
    landing_page.expect_generated_template_visible()
    landing_page.click_generated_template()
    landing_page.click_edit_template()
    landing_page.click_editor_download_button()
    landing_page.click_dialog_download_button()
    sleep(5)
