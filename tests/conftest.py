import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for tests, override with BASE_URL env var."""
    return os.getenv("BASE_URL", "https://example.org")


@pytest.fixture(scope="session")
def _playwright():
    """Session-scoped Playwright instance shared across tests."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def base_browser_context_args(base_url):
    """Common browser-context settings used by both ephemeral and persistent modes."""
    return {"accept_downloads": True, "base_url": base_url}


@pytest.fixture(scope="session")
def download_dir() -> Path:
    """Project-local directory where downloaded files are stored."""
    path = Path(os.getenv("DOWNLOAD_DIR", "downloads")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def browser(_playwright):
    """Launch a Chromium browser once per session when not using a persistent profile."""
    if os.getenv("USE_CHROME_PROFILE", "0") == "1":
        yield None
        return

    headless = os.getenv("HEADLESS", "1") != "0"
    browser = _playwright.chromium.launch(headless=headless)
    yield browser
    browser.close()


@pytest.fixture()
def context(_playwright, browser, base_url, base_browser_context_args):
    """Create an isolated context or attach to a persistent Chrome profile for debugging."""
    if os.getenv("USE_CHROME_PROFILE", "0") == "1":
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")
        if not user_data_dir:
            pytest.fail("CHROME_USER_DATA_DIR must be set when USE_CHROME_PROFILE=1")

        profile_dir = os.getenv("CHROME_PROFILE_DIR")
        launch_args = []
        if profile_dir:
            launch_args.append(f"--profile-directory={profile_dir}")

        context = _playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            args=launch_args,
            **base_browser_context_args,
        )
        yield context
        context.close()
        return

    context = browser.new_context(**base_browser_context_args)
    yield context
    context.close()


@pytest.fixture()
def page(context):
    """Use the existing persistent page when available, otherwise create a new one."""
    existing_pages = context.pages
    page = existing_pages[0] if existing_pages else context.new_page()
    yield page

    if page in context.pages and len(context.pages) > 1:
        page.close()
