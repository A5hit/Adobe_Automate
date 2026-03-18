import re

from playwright.sync_api import expect

from pages.base_page import BasePage


class LoginPage(BasePage):
    """Adobe authentication page interactions."""

    def open(self) -> None:
        self.page.goto("https://www.adobe.com/express/login")

    # def expect_login_page_visible(self) -> None:
    #     expect(self.page).to_have_url(
    #         re.compile(r"https://auth\.services\.adobe\.com/.*"),
    #         timeout=15_000,
    #     )
    #     expect(self.page.locator('input[type="email"]')).to_be_visible(timeout=10_000)

    def click_students_teachers_tab(self) -> None:
        tab = self.page.get_by_role("tab", name="Students / Teachers")
        expect(tab).to_be_visible(timeout=10_000)
        tab.click(timeout=10_000)

    def enter_email(self, email: str) -> None:
        email_field = self.page.get_by_role("textbox").first
        expect(email_field).to_be_visible(timeout=10_000)
        email_field.fill(email, timeout=10_000)

    def click_continue(self, delay_ms: float = 500) -> None:
        continue_button = self.page.locator("button[data-id='submit-button']:visible")
        expect(continue_button).to_be_visible(timeout=10_000)
        continue_button.click(timeout=10_000, delay=delay_ms)

    def wait_for_identity_provider_redirect(self) -> str:
        self.page.wait_for_url(
            re.compile(r"https://(login\.microsoftonline\.com|accounts\.google\.com)/.*"),
            timeout=15_000,
        )

        current_url = self.page.url
        if current_url.startswith("https://login.microsoftonline.com/"):
            return "microsoft"
        if current_url.startswith("https://accounts.google.com/"):
            return "google"

        raise AssertionError(f"Unexpected identity provider redirect: {current_url}")

    def microsoft_login_page(self, email: str, password: str) -> None:
        expect(self.page).to_have_url(
            re.compile(r"https://login\.microsoftonline\.com/.*"),
            timeout=15_000,
        )
        email_field = self.page.get_by_placeholder("Email, phone, or Skype")
        expect(email_field).to_be_visible(timeout=10_000)
        email_field.fill(email, timeout=10_000)
        submit_button = self.page.locator("input[type='submit']")
        expect(submit_button).to_be_visible(timeout=10_000)
        submit_button.click(timeout=10_000, delay=500)

        # Wait for password field to appear, which indicates we've moved to the next step of the login flow

        password_field = self.page.get_by_placeholder("Password")
        expect(password_field).to_be_visible(timeout=10_000)
        password_field.fill(password, timeout=10_000)
        password_submit_button = self.page.locator("input[type='submit']")
        expect(password_submit_button).to_be_visible(timeout=10_000)
        password_submit_button.click(timeout=10_000, delay=500)
        stay_signed_in_text = self.page.get_by_text("Stay signed in?", exact=True)
        expect(stay_signed_in_text).to_be_visible(timeout=10_000)
        stay_signed_in_submit_button = self.page.locator("input[type='submit']")
        expect(stay_signed_in_submit_button).to_be_visible(timeout=10_000)
        stay_signed_in_submit_button.click(timeout=10_000, delay=500)


    def google_login_page(self, email: str, password: str) -> None:
        expect(self.page).to_have_url(
            re.compile(r"https://accounts\.google\.com/.*"),
            timeout=15_000,
        )
        # Google login flow can vary based on factors like account settings and previous login sessions, so we need to handle multiple possible prompts. We'll start by entering the email, then proceed step-by-step, waiting for each expected element to appear before interacting with it.
        email_field = self.page.get_by_role("textbox", name="Email or phone")
        expect(email_field).to_be_visible(timeout=10_000)
        email_field.fill(email, timeout=10_000)
        next_button = self.page.get_by_role("button", name="Next")
        expect(next_button).to_be_visible(timeout=10_000)
        next_button.click(timeout=10_000, delay=500)

        # Wait for password field to appear, which indicates we've moved to the next step of the login flow
        password_field = self.page.get_by_role("textbox", name="Enter your password")
        expect(password_field).to_be_visible(timeout=15_000)
        password_field.fill(password, timeout=10_000)
        password_next_button = self.page.get_by_role("button", name="Next")
        expect(password_next_button).to_be_visible(timeout=10_000)
        password_next_button.click(timeout=10_000, delay=500)

        # Handle "Google wants to know you’re a real person" prompt if it appears
        i_understand = self.page.locator("#confirm")
        expect(i_understand).to_be_visible(timeout=15_000)
        i_understand.click(timeout=10_000, delay=500)

        # Handle "Stay signed in?" prompt if it appears
        continue_button = self.page.get_by_text("Continue", exact=True)
        expect(continue_button).to_be_visible(timeout=15_000)
        continue_button.click(timeout=10_000, delay=500)
        
