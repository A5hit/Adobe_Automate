from playwright.sync_api import Page


class BasePage:
    """Thin wrapper around a Playwright page."""

    def __init__(self, page: Page) -> None:
        self.page = page
