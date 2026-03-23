import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_HEADERS = ["email", "test_status", "error", "failed_at_step", "timestamp"]


class CsvResultReporter:
    """Append one CSV row as each account-driven test item completes."""

    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        self._file = None
        self._writer = None

    def _ensure_open(self) -> None:
        if self._file is not None and self._writer is not None:
            return

        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.report_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=REPORT_HEADERS)
        self._writer.writeheader()
        self._file.flush()

    def write_row(self, row: dict[str, str]) -> None:
        self._ensure_open()
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()


def _resolve_results_csv(config: pytest.Config) -> Path:
    csv_path_value = os.getenv("ADOBE_RESULTS_CSV", "").strip()
    if csv_path_value:
        csv_path = Path(csv_path_value).expanduser()
        if not csv_path.is_absolute():
            csv_path = Path(config.rootpath) / csv_path
        return csv_path

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(config.rootpath) / "reports" / f"adobe_results_{timestamp}.csv"


def _get_reporter(config: pytest.Config) -> CsvResultReporter:
    reporter = getattr(config, "_csv_result_reporter", None)
    if reporter is None:
        raise pytest.UsageError("CSV result reporter was not initialized.")
    return reporter


def _extract_account_email(item: pytest.Item) -> str:
    callspec = getattr(item, "callspec", None)
    if callspec is None:
        return ""

    account = callspec.params.get("account")
    if isinstance(account, dict):
        return str(account.get("email", "")).strip()
    return ""


def _failure_reason(report: pytest.TestReport) -> str:
    if report.longreprtext:
        lines = [line.strip() for line in report.longreprtext.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return "Test failed without a captured error message."


def _failed_step(item: pytest.Item, status: str, fallback_stage: str = "") -> str:
    if status != "failed":
        return ""

    step = str(getattr(item, "_failed_step", "")).strip()
    if step:
        return step
    return fallback_stage or "pytest"


def _result_row(item: pytest.Item) -> dict[str, str]:
    setup_report = getattr(item, "rep_setup", None)
    call_report = getattr(item, "rep_call", None)
    teardown_report = getattr(item, "rep_teardown", None)

    if setup_report is not None and setup_report.failed:
        status = "failed"
        reason = _failure_reason(setup_report)
        fallback_stage = "pytest setup"
    elif call_report is not None and call_report.failed:
        status = "failed"
        reason = _failure_reason(call_report)
        fallback_stage = "pytest call"
    elif teardown_report is not None and teardown_report.failed:
        status = "failed"
        reason = _failure_reason(teardown_report)
        fallback_stage = "pytest teardown"
    elif setup_report is not None and setup_report.skipped:
        status = "skipped"
        reason = setup_report.longreprtext.strip() or "Test skipped."
        fallback_stage = ""
    elif call_report is not None and call_report.skipped:
        status = "skipped"
        reason = call_report.longreprtext.strip() or "Test skipped."
        fallback_stage = ""
    elif teardown_report is not None and teardown_report.skipped:
        status = "skipped"
        reason = teardown_report.longreprtext.strip() or "Test skipped."
        fallback_stage = ""
    else:
        status = "passed"
        reason = ""
        fallback_stage = ""

    return {
        "email": _extract_account_email(item),
        "test_status": status,
        "error": reason,
        "failed_at_step": _failed_step(item, status, fallback_stage),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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


def pytest_configure(config: pytest.Config) -> None:
    config._csv_result_reporter = CsvResultReporter(_resolve_results_csv(config))


def pytest_unconfigure(config: pytest.Config) -> None:
    reporter = getattr(config, "_csv_result_reporter", None)
    if reporter is not None:
        reporter.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)

    if report.when != "teardown":
        return

    email = _extract_account_email(item)
    if not email:
        return

    _get_reporter(item.config).write_row(_result_row(item))


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
