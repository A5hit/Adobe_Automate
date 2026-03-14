from playwright.sync_api import Page

from pages.landing_page import LandingPage


def test_open_site_and_click_primary_cta(page: Page) -> None:
    landing_page = LandingPage(page)
    landing_page.open()
    landing_page.ensure_authenticated()
    # landing_page.click_lets_go()
    landing_page.expect_create_a_poster_visible()
    landing_page.click_create_a_poster()
    landing_page.click_generate_template()
    landing_page.enter_prompt_text()
    landing_page.click_generate()
    landing_page.expect_generated_template_visible()
    landing_page.click_generated_template()
    landing_page.click_edit_template()
    landing_page.click_editor_download_button()
    landing_page.click_dialog_download_button()
