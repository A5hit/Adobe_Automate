import csv
import os
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import expect, sync_playwright

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import PW_DEFAULT_TIMEOUT_MS, PW_EXPECT_TIMEOUT_MS, PW_NAVIGATION_TIMEOUT_MS

expect.set_options(timeout=PW_EXPECT_TIMEOUT_MS)

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


class CsvRowCollector:
    """Collect CSV rows from worker-local artifact files."""

    def __init__(self, csv_path: Path, fieldnames: list[str]) -> None:
        self.csv_path = csv_path
        self.fieldnames = fieldnames
        self._file = None
        self._writer = None

    def _ensure_open(self) -> None:
        if self._file is not None and self._writer is not None:
            return

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.csv_path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
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


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def _is_xdist_controller(config: pytest.Config) -> bool:
    if _is_xdist_worker(config):
        return False

    numprocesses = getattr(getattr(config, "option", None), "numprocesses", None)
    return bool(numprocesses)


def _get_worker_id(config: pytest.Config) -> str:
    if _is_xdist_worker(config):
        return str(config.workerinput["workerid"])
    return "master"


def _worker_artifact_path(base_path: Path, worker_id: str) -> Path:
    return base_path.with_name(f"{base_path.stem}.{worker_id}{base_path.suffix}")


def _load_consumed_emails(ledger_path: Path) -> set[str]:
    consumed_emails: set[str] = set()
    if not ledger_path.is_file():
        return consumed_emails

    with ledger_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            email = _normalize_email(row.get("email", ""))
            if email:
                consumed_emails.add(email)
    return consumed_emails


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


def _get_consumed_fragment_writer(config: pytest.Config) -> CsvRowCollector | None:
    return getattr(config, "_consumed_fragment_writer", None)


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


def _set_account_selection_state(
    config: pytest.Config,
    *,
    accounts: list[dict[str, str]],
    source: str,
    total_accounts: int,
    consumed_skipped: int,
    duplicate_skipped: int,
    ledger_path: Path,
) -> list[dict[str, str]]:
    selected_accounts = _with_account_ids(accounts)
    config._selected_accounts = selected_accounts
    config._account_selection_summary = {
        "source": source,
        "total_accounts": total_accounts,
        "runnable_accounts": len(selected_accounts),
        "consumed_skipped": consumed_skipped,
        "duplicate_skipped": duplicate_skipped,
        "ledger_path": str(ledger_path),
    }
    return selected_accounts


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
    accounts: list[dict[str, str]],
    *,
    consumed_emails: set[str],
) -> tuple[list[dict[str, str]], int, int]:
    fresh_accounts: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    consumed_skipped = 0
    duplicate_skipped = 0

    for account in accounts:
        normalized_email = _normalize_email(account["email"])
        if normalized_email in seen_emails:
            duplicate_skipped += 1
            continue

        seen_emails.add(normalized_email)
        if normalized_email in consumed_emails:
            consumed_skipped += 1
            continue

        fresh_accounts.append(account)

    return fresh_accounts, consumed_skipped, duplicate_skipped


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
    cached_accounts = getattr(config, "_selected_accounts", None)
    if cached_accounts is not None:
        return cached_accounts

    ledger_path = getattr(config, "_final_consumed_accounts_path", _resolve_consumed_accounts_csv(config))
    consumed_emails = _load_consumed_emails(ledger_path)
    csv_path = _resolve_accounts_csv(config)
    if csv_path is not None:
        accounts = _load_accounts_from_csv(csv_path)
        fresh_accounts, consumed_skipped, duplicate_skipped = _filter_fresh_accounts(
            accounts,
            consumed_emails=consumed_emails,
        )
        return _set_account_selection_state(
            config,
            accounts=fresh_accounts,
            source=str(csv_path),
            total_accounts=len(accounts),
            consumed_skipped=consumed_skipped,
            duplicate_skipped=duplicate_skipped,
            ledger_path=ledger_path,
        )

    email = os.getenv("ADOBE_EMAIL", "").strip()
    password = os.getenv("ADOBE_PASSWORD", "").strip()
    if email and password:
        accounts = [{"email": email, "password": password, "id": email}]
        fresh_accounts, consumed_skipped, duplicate_skipped = _filter_fresh_accounts(
            accounts,
            consumed_emails=consumed_emails,
        )
        return _set_account_selection_state(
            config,
            accounts=fresh_accounts,
            source="environment variables",
            total_accounts=len(accounts),
            consumed_skipped=consumed_skipped,
            duplicate_skipped=duplicate_skipped,
            ledger_path=ledger_path,
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


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node) -> None:
    config = node.config
    accounts = _load_accounts(config)
    worker_id = str(node.workerinput.get("workerid", node.gateway.id))
    worker_ids = getattr(config, "_xdist_worker_ids", set())
    worker_ids.add(worker_id)
    config._xdist_worker_ids = worker_ids
    node.workerinput["selected_accounts"] = accounts
    node.workerinput["account_selection_summary"] = getattr(config, "_account_selection_summary", None)
    node.workerinput["final_results_path"] = str(config._final_results_path)
    node.workerinput["final_consumed_accounts_path"] = str(config._final_consumed_accounts_path)


def pytest_configure(config: pytest.Config) -> None:
    if _is_xdist_worker(config):
        config._selected_accounts = config.workerinput.get("selected_accounts", [])
        config._account_selection_summary = config.workerinput.get("account_selection_summary")
        config._final_results_path = Path(config.workerinput["final_results_path"])
        config._final_consumed_accounts_path = Path(config.workerinput["final_consumed_accounts_path"])
    else:
        config._final_results_path = _resolve_results_csv(config)
        config._final_consumed_accounts_path = _resolve_consumed_accounts_csv(config)
        _load_accounts(config)

    if _is_xdist_controller(config):
        return

    if _is_xdist_worker(config):
        worker_id = _get_worker_id(config)
        config._csv_result_reporter = CsvResultReporter(
            _worker_artifact_path(config._final_results_path, worker_id)
        )
        config._consumed_fragment_writer = CsvRowCollector(
            _worker_artifact_path(config._final_consumed_accounts_path, worker_id),
            CONSUMED_ACCOUNT_HEADERS,
        )
        return

    config._csv_result_reporter = CsvResultReporter(config._final_results_path)
    config._consumed_account_ledger = ConsumedAccountLedger(
        config._final_consumed_accounts_path,
        source=config._final_results_path.name,
    )


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        return []

    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def _merge_result_fragments(final_path: Path, fragment_paths: Iterable[Path]) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with final_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_HEADERS)
        writer.writeheader()
        for fragment_path in sorted(fragment_paths, key=lambda path: path.name):
            for row in _read_csv_rows(fragment_path):
                writer.writerow({header: row.get(header, "") for header in REPORT_HEADERS})


def _merge_consumed_fragments(final_path: Path, fragment_paths: Iterable[Path]) -> None:
    existing_emails = _load_consumed_emails(final_path)
    rows_to_append: list[dict[str, str]] = []

    for fragment_path in sorted(fragment_paths, key=lambda path: path.name):
        for row in _read_csv_rows(fragment_path):
            email = row.get("email", "").strip()
            normalized_email = _normalize_email(email)
            if not normalized_email or normalized_email in existing_emails:
                continue

            rows_to_append.append(
                {
                    "email": email,
                    "consumed_at": row.get("consumed_at", ""),
                    "source": row.get("source", ""),
                }
            )
            existing_emails.add(normalized_email)

    if not rows_to_append:
        return

    final_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = final_path.exists() and final_path.stat().st_size > 0
    with final_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CONSUMED_ACCOUNT_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows_to_append)


def _cleanup_fragment_files(fragment_paths: Iterable[Path]) -> None:
    for fragment_path in fragment_paths:
        if fragment_path.exists():
            fragment_path.unlink()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if not _is_xdist_controller(config):
        return

    worker_ids = sorted(getattr(config, "_xdist_worker_ids", set()))
    if not worker_ids:
        return

    result_fragments = [
        _worker_artifact_path(config._final_results_path, worker_id) for worker_id in worker_ids
    ]
    consumed_fragments = [
        _worker_artifact_path(config._final_consumed_accounts_path, worker_id)
        for worker_id in worker_ids
    ]
    _merge_result_fragments(config._final_results_path, result_fragments)
    _merge_consumed_fragments(config._final_consumed_accounts_path, consumed_fragments)
    _cleanup_fragment_files(result_fragments)
    _cleanup_fragment_files(consumed_fragments)


def pytest_unconfigure(config: pytest.Config) -> None:
    reporter = getattr(config, "_csv_result_reporter", None)
    if reporter is not None:
        reporter.close()
    ledger = getattr(config, "_consumed_account_ledger", None)
    if ledger is not None:
        ledger.close()
    consumed_fragment_writer = _get_consumed_fragment_writer(config)
    if consumed_fragment_writer is not None:
        consumed_fragment_writer.close()


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
        if _is_xdist_worker(request.config):
            _get_consumed_fragment_writer(request.config).write_row(
                {
                    "email": email,
                    "consumed_at": datetime.now(timezone.utc).isoformat(),
                    "source": request.config._final_results_path.name,
                }
            )
        else:
            _get_consumed_ledger(request.config).claim(email)

    context = browser.new_context(accept_downloads=True, base_url=base_url)
    context.set_default_timeout(PW_DEFAULT_TIMEOUT_MS)
    context.set_default_navigation_timeout(PW_NAVIGATION_TIMEOUT_MS)
    yield context
    context.close()


@pytest.fixture()
def page(context):
    """Create a fresh page while keeping session state in the shared context."""
    page = context.new_page()
    page.set_default_timeout(PW_DEFAULT_TIMEOUT_MS)
    page.set_default_navigation_timeout(PW_NAVIGATION_TIMEOUT_MS)
    yield page
    if page in context.pages:
        page.close()
