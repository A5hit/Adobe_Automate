import csv
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_accounts_csv(config: pytest.Config) -> Path | None:
    csv_path_value = os.getenv("ADOBE_ACCOUNTS_CSV", "").strip()
    if csv_path_value:
        csv_path = Path(csv_path_value).expanduser()
        if not csv_path.is_absolute():
            csv_path = Path(config.rootpath) / csv_path
        if not csv_path.is_file():
            raise pytest.UsageError(f"Accounts CSV not found: {csv_path}")
        return csv_path

    default_csv = Path(config.rootpath) / "accounts.csv"
    if default_csv.is_file():
        return default_csv
    return None


def _load_accounts(config: pytest.Config) -> list[dict[str, str]]:
    csv_path = _resolve_accounts_csv(config)
    if csv_path is not None:
        with csv_path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise pytest.UsageError(f"Accounts CSV is empty: {csv_path}")

            field_map = {name.strip().lower(): name for name in reader.fieldnames}
            if "email" not in field_map or "password" not in field_map:
                raise pytest.UsageError(
                    f"Accounts CSV must contain 'email' and 'password' columns: {csv_path}"
                )

            email_field = field_map["email"]
            password_field = field_map["password"]
            accounts: list[dict[str, str]] = []
            for row_number, row in enumerate(reader, start=2):
                email = (row.get(email_field) or "").strip()
                password = (row.get(password_field) or "").strip()
                if not email and not password:
                    continue
                if not email or not password:
                    raise pytest.UsageError(
                        f"Accounts CSV row {row_number} must include both email and password."
                    )

                accounts.append(
                    {
                        "email": email,
                        "password": password,
                        "id": f"row{len(accounts) + 1}-{email}",
                    }
                )

        if not accounts:
            raise pytest.UsageError(f"Accounts CSV has no usable credential rows: {csv_path}")
        return accounts

    email = os.getenv("ADOBE_EMAIL", "").strip()
    password = os.getenv("ADOBE_PASSWORD", "").strip()
    if email and password:
        return [{"email": email, "password": password, "id": email}]

    raise pytest.UsageError(
        "Provide credentials with accounts.csv, ADOBE_ACCOUNTS_CSV, or ADOBE_EMAIL/ADOBE_PASSWORD."
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "account" not in metafunc.fixturenames:
        return

    accounts = _load_accounts(metafunc.config)
    metafunc.parametrize(
        "account",
        accounts,
        ids=[account["id"] for account in accounts],
        scope="module",
        indirect=True,
    )


@pytest.fixture(scope="module")
def account(request: pytest.FixtureRequest) -> dict[str, str]:
    """Credential row used to drive an isolated module run."""
    return request.param


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for tests, override with BASE_URL env var."""
    return os.getenv("BASE_URL", "https://example.org")


@pytest.fixture(scope="session")
def browser():
    """Launch a Chromium browser once per test session."""
    headless = os.getenv("HEADLESS", "1") != "0"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def context(browser, base_url, account):
    """Create a fresh browser context for each credential row."""
    context = browser.new_context(accept_downloads=True, base_url=base_url)
    yield context
    context.close()


@pytest.fixture()
def page(context):
    """Create a fresh page while keeping session state in the shared context."""
    page = context.new_page()
    yield page
    if page in context.pages:
        page.close()
