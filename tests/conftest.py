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
CONSUMED_ACCOUNT_HEADERS = ["email", "consumed_at", "source"]


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


class ConsumedAccountLedger:
    """Persistently track emails that have already been attempted once."""

    def __init__(self, ledger_path: Path, source: str) -> None:
        self.ledger_path = ledger_path
        self.source = source
        self._file = None
        self._writer = None
        self._consumed_emails: set[str] | None = None

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().casefold()

    def _ensure_loaded(self) -> None:
        if self._consumed_emails is not None:
            return

        consumed_emails: set[str] = set()
        if self.ledger_path.is_file():
            with self.ledger_path.open(newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    email = self._normalize_email(row.get("email", ""))
                    if email:
                        consumed_emails.add(email)

        self._consumed_emails = consumed_emails

    def _ensure_open(self) -> None:
        if self._file is not None and self._writer is not None:
            return

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.ledger_path.exists()
        self._file = self.ledger_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=CONSUMED_ACCOUNT_HEADERS)
        if not file_exists or self.ledger_path.stat().st_size == 0:
            self._writer.writeheader()
            self._file.flush()

    def has(self, email: str) -> bool:
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return False

        self._ensure_loaded()
        return normalized_email in self._consumed_emails

    def claim(self, email: str) -> bool:
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return False

        self._ensure_loaded()
        if normalized_email in self._consumed_emails:
            return False

        self._ensure_open()
        self._writer.writerow(
            {
                "email": email.strip(),
                "consumed_at": datetime.now(timezone.utc).isoformat(),
                "source": self.source,
            }
        )
        self._file.flush()
        self._consumed_emails.add(normalized_email)
        return True

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


def _resolve_consumed_accounts_csv(config: pytest.Config) -> Path:
    csv_path_value = os.getenv("ADOBE_CONSUMED_ACCOUNTS_CSV", "").strip()
    if csv_path_value:
        csv_path = Path(csv_path_value).expanduser()
        if not csv_path.is_absolute():
            csv_path = Path(config.rootpath) / csv_path
        return csv_path

    return Path(config.rootpath) / "reports" / "adobe_consumed_accounts.csv"


def _get_reporter(config: pytest.Config) -> CsvResultReporter:
    reporter = getattr(config, "_csv_result_reporter", None)
    if reporter is None:
        raise pytest.UsageError("CSV result reporter was not initialized.")
    return reporter


def _get_consumed_ledger(config: pytest.Config) -> ConsumedAccountLedger:
    ledger = getattr(config, "_consumed_account_ledger", None)
    if ledger is None:
        raise pytest.UsageError("Consumed account ledger was not initialized.")
    return ledger


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


def _with_account_ids(accounts: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            **account,
            "id": account.get("id") or account["email"],
        }
        for account in accounts
    ]


def _record_account_selection_summary(
    config: pytest.Config,
    *,
    source: str,
    total_accounts: int,
    runnable_accounts: int,
    consumed_skipped: int,
    duplicate_skipped: int,
    ledger_path: Path,
) -> None:
    config._account_selection_summary = {
        "source": source,
        "total_accounts": total_accounts,
        "runnable_accounts": runnable_accounts,
        "consumed_skipped": consumed_skipped,
        "duplicate_skipped": duplicate_skipped,
        "ledger_path": str(ledger_path),
    }

def _filter_fresh_accounts(
    config: pytest.Config,
    accounts: list[dict[str, str]],
    *,
    source: str,
) -> list[dict[str, str]]:
    ledger = _get_consumed_ledger(config)
    fresh_accounts: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    consumed_skipped = 0
    duplicate_skipped = 0

    for account in accounts:
        normalized_email = ConsumedAccountLedger._normalize_email(account["email"])
        if normalized_email in seen_emails:
            duplicate_skipped += 1
            continue

        seen_emails.add(normalized_email)
        if ledger.has(account["email"]):
            consumed_skipped += 1
            continue

        fresh_accounts.append(account)

    _record_account_selection_summary(
        config,
        source=source,
        total_accounts=len(accounts),
        runnable_accounts=len(fresh_accounts),
        consumed_skipped=consumed_skipped,
        duplicate_skipped=duplicate_skipped,
        ledger_path=ledger.ledger_path,
    )
    return _with_account_ids(fresh_accounts)


def _load_accounts_from_csv(csv_path: Path) -> list[dict[str, str]]:
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
                    "id": f"row{row_number - 1}-{email}",
                }
            )

    if not accounts:
        raise pytest.UsageError(f"Accounts CSV has no usable credential rows: {csv_path}")
    return accounts


def _build_skip_account_param(reason: str) -> object:
    return pytest.param(
        {
            "email": "",
            "password": "",
            "id": "no-fresh-accounts",
        },
        marks=pytest.mark.skip(reason=reason),
        id="no-fresh-accounts",
    )


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
        accounts = _load_accounts_from_csv(csv_path)
        return _filter_fresh_accounts(config, accounts, source=str(csv_path))

    email = os.getenv("ADOBE_EMAIL", "").strip()
    password = os.getenv("ADOBE_PASSWORD", "").strip()
    if email and password:
        return _filter_fresh_accounts(
            config,
            [{"email": email, "password": password, "id": email}],
            source="environment variables",
        )

    raise pytest.UsageError(
        "Provide credentials with accounts.csv, ADOBE_ACCOUNTS_CSV, or ADOBE_EMAIL/ADOBE_PASSWORD."
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "account" not in metafunc.fixturenames:
        return

    accounts = _load_accounts(metafunc.config)
    if not accounts:
        accounts = [
            _build_skip_account_param(
                "No fresh accounts are available after filtering the consumed account ledger."
            )
        ]

    account_ids = None
    if all(isinstance(account, dict) for account in accounts):
        account_ids = [account["id"] for account in accounts]

    metafunc.parametrize(
        "account",
        accounts,
        ids=account_ids,
        scope="module",
        indirect=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    config._csv_result_reporter = CsvResultReporter(_resolve_results_csv(config))
    config._consumed_account_ledger = ConsumedAccountLedger(
        _resolve_consumed_accounts_csv(config),
        source=_resolve_results_csv(config).name,
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    reporter = getattr(config, "_csv_result_reporter", None)
    if reporter is not None:
        reporter.close()
    ledger = getattr(config, "_consumed_account_ledger", None)
    if ledger is not None:
        ledger.close()


def pytest_report_header(config: pytest.Config):
    summary = getattr(config, "_account_selection_summary", None)
    if summary is None:
        return None

    return [
        f"account source: {summary['source']}",
        f"consumed account ledger: {summary['ledger_path']}",
        "account selection: "
        f"loaded={summary['total_accounts']}, "
        f"runnable={summary['runnable_accounts']}, "
        f"consumed_skipped={summary['consumed_skipped']}, "
        f"duplicate_skipped={summary['duplicate_skipped']}",
    ]


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
    channel = os.getenv("PLAYWRIGHT_CHANNEL", "").strip() or None
    with sync_playwright() as playwright:
        launch_kwargs: dict[str, object] = {
            "headless": headless,
            "args": ["--disable-http2"],
        }
        if channel is not None:
            launch_kwargs["channel"] = channel

        browser = playwright.chromium.launch(
            **launch_kwargs,
        )
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def context(browser, base_url, account, request: pytest.FixtureRequest):
    """Create a fresh browser context for each credential row."""
    email = str(account.get("email", "")).strip()
    if email:
        _get_consumed_ledger(request.config).claim(email)

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
