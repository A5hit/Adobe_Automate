from time import monotonic, sleep

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

from pages.base_page import BasePage
from settings import (
    PW_BRIEF_TIMEOUT_MS,
    PW_DEFAULT_TIMEOUT_MS,
    PW_LONG_TIMEOUT_MS,
    PW_QUICK_TIMEOUT_MS,
    PW_SHORT_TIMEOUT_MS, PW_NAVIGATION_TIMEOUT_MS,
)


class LandingPage(BasePage):
    """Entry page interactions for the initial onboarding flow."""

    def open(self) -> None:
        self.set_step("Open Adobe Express landing page")
        self.page.goto("https://new.express.adobe.com/")

    def ensure_authenticated(self) -> None:
        self.set_step("Verify authenticated Adobe session")
        current_url = self.page.url
        if "auth.services.adobe.com" in current_url or "adobelogn.icom" in current_url:
            raise AssertionError(
                "Adobe session is not authenticated in the current browser context. "
                "Complete the login flow before running the authenticated scenario."
            )

    def click_lets_go(self) -> None:
        self.set_step("Handle Let's go prompt")
        cta = self.page.get_by_text("Let\u2019s go", exact=True)
        try:
            # This onboarding CTA can arrive late after the authenticated shell paints on slower runs.
            cta.wait_for(state="visible", timeout=PW_NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return
        else:
            cta.click(timeout=PW_DEFAULT_TIMEOUT_MS)

    def expect_create_a_poster_visible(self) -> None:
        self.set_step("Wait for Create a poster option")
        expect(self.page.get_by_text("Create a poster", exact=True)).to_be_visible(
            timeout=PW_NAVIGATION_TIMEOUT_MS
        )

    def click_create_a_poster(self) -> None:
        self.set_step("Click Create a poster")
        card = self.page.get_by_text("Create a poster", exact=True)
        expect(card).to_be_visible(timeout=PW_SHORT_TIMEOUT_MS)
        card.click(timeout=PW_SHORT_TIMEOUT_MS)

    def dismiss_skip_tour_if_visible(self) -> None:
        self.set_step("Dismiss Skip tour prompt")
        skip_tour = self.page.get_by_text("Skip tour", exact=True)
        try:
            skip_tour.wait_for(state="visible", timeout=PW_DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return
        else:
            skip_tour.click(timeout=PW_SHORT_TIMEOUT_MS)
            self.page.wait_for_load_state("domcontentloaded")

    def click_generate_template(self) -> None:
        self.set_step("Click Generate template")
        self.dismiss_skip_tour_if_visible()
        button = self.page.get_by_text("Generate template", exact=True)
        expect(button).to_be_visible(timeout=PW_DEFAULT_TIMEOUT_MS)
        button.click(timeout=PW_DEFAULT_TIMEOUT_MS)
        self.page.wait_for_load_state("domcontentloaded")

    def enter_prompt_text(self) -> None:
        self.set_step("Enter poster prompt")
        prompt = self.page.locator("textarea.input")
        expect(prompt).to_be_visible(timeout=PW_DEFAULT_TIMEOUT_MS)
        prompt.fill(
                "Create a poster for festival."
        )

    def click_generate(self) -> None:
        self.set_step("Generate poster")
        button = self.page.get_by_text("Generate", exact=True)
        expect(button).to_be_enabled(timeout=PW_DEFAULT_TIMEOUT_MS)
        button.click(timeout=PW_DEFAULT_TIMEOUT_MS)
        self.page.wait_for_load_state("domcontentloaded")

    def expect_generated_template_visible(self) -> None:
        self.set_step("Wait for generated template")
        template = self.page.get_by_label("Generated Template").last
        alert = self.page.get_by_role("alert").first
        close_button = self.page.get_by_role("button", name="Close")
        max_retries = 2
        timeout_ms = PW_LONG_TIMEOUT_MS
        poll_interval_ms = 500

        for attempt in range(max_retries + 1):
            deadline = monotonic() + (timeout_ms / 1000)
            while monotonic() < deadline:
                if template.is_visible():
                    return

                if alert.is_visible():
                    alert_text = alert.inner_text().strip()
                    close_button.click(timeout=PW_SHORT_TIMEOUT_MS)
                    alert.wait_for(state="hidden", timeout=PW_SHORT_TIMEOUT_MS)

                    if attempt >= max_retries:
                        raise AssertionError(
                            "Adobe generation showed an alert instead of a generated template"
                            + (f": {alert_text}" if alert_text else ".")
                        )

                    self.click_generate()
                    self.set_step("Wait for generated template")
                    break

                self.page.wait_for_timeout(poll_interval_ms)
            else:
                expect(template).to_be_visible(timeout=PW_QUICK_TIMEOUT_MS)

    def click_generated_template(self) -> None:
        self.set_step("Select generated template")
        template = self.page.get_by_label("Generated Template").last
        expect(template).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        template.click(timeout=PW_DEFAULT_TIMEOUT_MS)

    def click_edit_template(self) -> None:
        self.set_step("Click Edit template")
        button = self.page.get_by_role("button", name="Edit template")
        expect(button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        with self.page.context.expect_page(timeout=PW_DEFAULT_TIMEOUT_MS) as new_page_info:
            button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        self.page = new_page_info.value
        self.page.wait_for_load_state("domcontentloaded")

    def click_editor_download_button(self) -> None:
        self.set_step("Click editor download button")
        self.page.wait_for_load_state("load")
        button = self.page.get_by_test_id("editor-download-button")
        expect(button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

    def click_dialog_download_button(self) -> None:
        self.set_step("Click download dialog button")

        download_button = self.page.locator("#dialog-download-btn").last
        success_text = self.page.get_by_text("Your download is complete.", exact=True)
        error_item = self.page.get_by_test_id("error-item").last
        all_clear_heading = self.page.get_by_role("heading", name="All clear")
        resolved_button = self.page.get_by_test_id("x-pre-export-check-resolved-button")

        expect(download_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        download_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)
        # Wait until either success appears or export errors appear
        while True:
            if success_text.is_visible():
                return

            if error_item.is_visible():
                break

            self.page.wait_for_timeout(PW_QUICK_TIMEOUT_MS)
        # Resolve export errors until "All clear" is shown, then proceed with download
        while not all_clear_heading.is_visible():
            if error_item.is_visible():
                error_item.click(timeout=PW_SHORT_TIMEOUT_MS)
                self.page.keyboard.press("Delete")
                self.set_step("Delete error item")
            self.page.wait_for_timeout(PW_QUICK_TIMEOUT_MS)

        self.set_step("wait for resolved button")
        expect(resolved_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        self.set_step("click resolved button")
        sleep(1)  # Avoid potential timing issues with button state update after error resolution
        resolved_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        expect(download_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        download_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        expect(success_text).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)












