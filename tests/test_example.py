import re
from time import sleep

from playwright.sync_api import Page

from pages.landing_page import LandingPage
from pages.login_page import LoginPage


def test_login(page: Page, account: dict[str, str]) -> None:
    email = account["email"]
    password = account["password"]

    login_page = LoginPage(page)
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

    page.wait_for_url(re.compile(r"https://new\.express\.adobe\.com/.*"), timeout=60_000)
    page.get_by_text("Let\u2019s go", exact=True).wait_for(state="visible", timeout=60_000)


    landing_page = LandingPage(page)
    landing_page.open()
    landing_page.ensure_authenticated()
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
