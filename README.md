# Playwright + Pytest Skeleton

- Install deps: `pip install -r requirements.txt`
- Install browsers once: `python -m playwright install chromium`
- Run tests: `pytest`
- Configure local settings in `.env`
- Run one account from env vars: set `ADOBE_EMAIL` and `ADOBE_PASSWORD`
- Run the full suite for many accounts from CSV: set `ADOBE_ACCOUNTS_CSV=path\\to\\accounts.csv`, or place `accounts.csv` in the project root
- CSV format: include `email,password` headers; each row runs the module in a fresh browser context
- Attempted emails are tracked in `reports\\adobe_consumed_accounts.csv` and are never scheduled again, even if the prior run failed
- Override the consumed-account ledger path with `ADOBE_CONSUMED_ACCOUNTS_CSV`
