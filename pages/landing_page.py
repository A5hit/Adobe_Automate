from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

from pages.base_page import BasePage


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
            cta.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError:
            return
        else:
            cta.click(timeout=5_000)

    def expect_create_a_poster_visible(self) -> None:
        self.dismiss_skip_tour_if_visible()
        self.set_step("Wait for Create a poster option")
        expect(self.page.get_by_text("Create a poster", exact=True)).to_be_visible(timeout=5_000)

    def click_create_a_poster(self) -> None:
        self.set_step("Click Create a poster")
        card = self.page.get_by_text("Create a poster", exact=True)
        expect(card).to_be_visible(timeout=5_000)
        card.click(timeout=5_000)


    def dismiss_skip_tour_if_visible(self) -> None:
        self.set_step("Dismiss Skip tour prompt")
        skip_tour = self.page.get_by_text("Skip tour", exact=True)
        try:
            skip_tour.wait_for(state="visible", timeout=3_000)
        except PlaywrightTimeoutError:
            return
        else:
            skip_tour.click(timeout=5_000)
            self.page.wait_for_load_state("domcontentloaded")

    def click_generate_template(self) -> None:
        self.set_step("Click Generate template")
        button = self.page.get_by_text("Generate template", exact=True)
        expect(button).to_be_visible(timeout=10_000)
        button.click(timeout=10_000)
        self.page.wait_for_load_state("domcontentloaded")

    def enter_prompt_text(self) -> None:
        self.set_step("Enter poster prompt")
        prompt = self.page.locator("textarea.input")
        expect(prompt).to_be_visible(timeout=10_000)
        prompt.fill("Create a modern poster for a weekend coffee festival.")

    def click_generate(self) -> None:
        self.set_step("Generate poster")
        button = self.page.get_by_text("Generate", exact=True)
        expect(button).to_be_enabled(timeout=10_000)
        button.click(timeout=10_000)
        self.page.wait_for_load_state("domcontentloaded")

    def expect_generated_template_visible(self) -> None:
        self.set_step("Wait for generated template")
        expect(self.page.get_by_label("Generated Template").last).to_be_visible(timeout=30_000)

    def click_generated_template(self) -> None:
        self.set_step("Select generated template")
        template = self.page.get_by_label("Generated Template").last
        expect(template).to_be_visible(timeout=30_000)
        template.click(timeout=10_000)

    def click_edit_template(self) -> None:
        self.set_step("Click Edit template")
        button = self.page.get_by_role("button", name="Edit template")
        expect(button).to_be_visible(timeout=30_000)
        with self.page.context.expect_page(timeout=10_000) as new_page_info:
            button.click(timeout=10_000)

        self.page = new_page_info.value
        self.page.wait_for_load_state("domcontentloaded")

    def click_editor_download_button(self) -> None:
        self.set_step("Click editor download button")
        self.page.wait_for_load_state("load")
        button = self.page.get_by_test_id("editor-download-button")
        expect(button).to_be_visible(timeout=30_000)
        button.click(timeout=10_000)

    def click_dialog_download_button(self) -> None:
        self.set_step("Click download dialog button")
        button = self.page.locator("#dialog-download-btn").last
        expect(button).to_be_visible(timeout=30_000)

        # with self.page.expect_download(timeout=30_000) as download_info:
        #     button.click(timeout=10_000)
        #
        # download = download_info.value
        # target_path = download_dir / Path(download.suggested_filename).name
        # target_path.parent.mkdir(parents=True, exist_ok=True)
        # download.save_as(str(target_path))
