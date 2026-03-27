from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from playwright.sync_api import Download, Locator, TimeoutError as PlaywrightTimeoutError, expect

from pages.base_page import BasePage
from settings import PW_DEFAULT_TIMEOUT_MS, PW_LONG_TIMEOUT_MS, PW_NAVIGATION_TIMEOUT_MS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMON_DOWNLOAD_DIR = PROJECT_ROOT / "downloads"
DEFAULT_AI_PROMPT = "Create an image of festival."


class AiGenerationPage(BasePage):
    """AI image generation and download flow after the landing CTA."""

    def wait_until_ready(self) -> None:
        self.set_step("Wait for AI entry on landing page")
        self.page.wait_for_load_state("domcontentloaded")
        # The landing shell can paint before the create cards hydrate, so gate on the AI entry itself.
        expect(self._ai_entry()).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)

    def click_ai(self) -> None:
        self.set_step("Click AI option")
        self.wait_until_ready()
        ai_option = self._ai_entry()
        # expect(ai_option).to_be_visible(timeout=PW_NAVIGATION_TIMEOUT_MS)
        ai_option.click(timeout=PW_DEFAULT_TIMEOUT_MS)
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=PW_LONG_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        # Clicking the AI label can refocus the card, but the prompt field is the reliable readiness signal.
        self._wait_for_prompt_input()

    def fill_prompt(self) -> None:
        self.set_step("Fill AI prompt")
        prompt = self._wait_for_prompt_input()
        prompt.fill(DEFAULT_AI_PROMPT)

    def click_generate_when_ready(self) -> None:
        self.set_step("Click Generate")
        generate_button = self._generate_click_button()
        # Prompt validation can lag behind the textbox fill on slower machines, so wait for enablement.
        expect(generate_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        expect(generate_button).to_be_enabled(timeout=PW_LONG_TIMEOUT_MS)
        generate_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

    def wait_for_generation_page_ready(self) -> None:
        self.set_step("Wait for AI generation page to finish loading")
        self.page.wait_for_load_state("domcontentloaded",timeout=PW_NAVIGATION_TIMEOUT_MS)
        try:
            self.page.wait_for_load_state("networkidle", timeout=PW_NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass

        generate_button = self._generate_button()
        # The shell can settle before the generated asset actions appear, so gate on Download as well.
        download_button = self._primary_download_button()
        expect(generate_button).to_be_visible(timeout=PW_NAVIGATION_TIMEOUT_MS)
        expect(download_button).to_be_visible(timeout=PW_NAVIGATION_TIMEOUT_MS)

    def download_selected_image(self) -> Path:
        self.set_step("Open AI download dialog")
        download_button = self._primary_download_button()
        expect(download_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        download_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        self.set_step("Choose selected image download")
        selected_image = self.page.get_by_text("Selected image", exact=True)
        # Download dialog options can appear after the button click animation completes on slower sessions.
        expect(selected_image).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        selected_image.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        final_download_button = self.page.get_by_text("Download", exact=True).last
        expect(final_download_button).to_be_visible(timeout=PW_LONG_TIMEOUT_MS)
        expect(final_download_button).to_be_enabled(timeout=PW_LONG_TIMEOUT_MS)

        with self.page.expect_download(timeout=PW_LONG_TIMEOUT_MS) as download_info:
            final_download_button.click(timeout=PW_DEFAULT_TIMEOUT_MS)

        download = download_info.value
        return self._save_download(download)

    def _save_download(self, download: Download) -> Path:
        self.set_step("Save AI download to common directory")
        COMMON_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

        suggested_name = download.suggested_filename or "generated-image"
        target_path = COMMON_DOWNLOAD_DIR / self._build_download_name(suggested_name)
        download.save_as(str(target_path))
        return target_path

    @staticmethod
    def _build_download_name(suggested_name: str) -> str:
        suggested_path = Path(suggested_name)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        stem = suggested_path.stem or "generated-image"
        suffix = suggested_path.suffix
        return f"{stem}_{timestamp}{suffix}"

    def _generate_button(self) -> Locator:
        return self.page.get_by_role("button", name="Generate")

    def _generate_click_button(self) -> Locator:
        return self.page.get_by_text("Generate", exact=True)

    def _ai_entry(self) -> Locator:
        return self.page.get_by_text("AI", exact=True)

    def _primary_download_button(self) -> Locator:
        return self.page.get_by_role("button", name="Download").first

    def _wait_for_prompt_input(self) -> Locator:
        deadline = monotonic() + (PW_LONG_TIMEOUT_MS / 1000)
        candidates = [
            self.page.get_by_role("textbox", name="Try places, people, or moods"),
            self.page.get_by_placeholder("Try places, people, or moods"),
            self.page.locator("textarea.input").first,
            self.page.locator("textarea").first,
            self.page.locator("[contenteditable='true'][role='textbox']").first,
            self.page.locator("[contenteditable='true']").first,
        ]

        while monotonic() < deadline:
            for candidate in candidates:
                if candidate.count() and candidate.is_visible():
                    return candidate
            self.page.wait_for_timeout(500)

        raise AssertionError(
            "No visible AI prompt input found after clicking AI. "
            f"Current URL: {self.page.url}"
        )
