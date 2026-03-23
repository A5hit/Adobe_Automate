from playwright.sync_api import Page


class BasePage:
    """Thin wrapper around a Playwright page."""

    def __init__(self, page: Page, report_target: object | None = None) -> None:
        self.page = page
        self.report_target = report_target

    def set_step(self, step: str) -> None:
        if self.report_target is None:
            return
        setattr(self.report_target, "_failed_step", step)
