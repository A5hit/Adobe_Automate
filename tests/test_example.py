from random import random
import re

import pytest
from playwright.sync_api import Page

from pages.ai_generation_page import AiGenerationPage
from pages.landing_page import LandingPage
from pages.login_page import LoginPage
from settings import PW_LOGIN_FINAL_URL_TIMEOUT_MS
import os, time

from tests.conftest import page


worker_id = os.getenv("PYTEST_XDIST_WORKER", "gw0")
worker_num = int(worker_id.replace("gw", ""))

time.sleep(worker_num * 3)

def test_login(page: Page, account: dict[str, str], request: pytest.FixtureRequest) -> None:
    email = account["email"]
    password = account["password"]

    login_page = LoginPage(page, request.node)
    login_page.open()
    login_page.click_students_teachers_tab()
    login_page.enter_email(email)
    login_page.click_continue()
    page.wait_for_timeout(300)
    provider = login_page.wait_for_identity_provider_redirect()
    page.wait_for_timeout(300)

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
    landing_page.click_lets_go()
    page.wait_for_timeout(400)

    ai_generation_page = AiGenerationPage(page, request.node)
    ai_generation_page.wait_until_ready()
    ai_generation_page.click_ai()
    ai_generation_page.fill_prompt()
    ai_generation_page.click_generate_when_ready()
    ai_generation_page.wait_for_generation_page_ready()
    import random
    page.wait_for_timeout(random.randint(500, 1200))
    ai_generation_page.download_selected_image()
