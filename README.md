# Playwright + Pytest Skeleton

- Install deps: `pip install -r requirements.txt`
- Install browsers once: `python -m playwright install chromium`
- Run tests: `pytest`
- Configure local settings in `.env`
- Debug with an existing Chrome profile:
  - Close all Chrome windows first.
  - Set `USE_CHROME_PROFILE=1` in `.env`
  - Set `CHROME_USER_DATA_DIR=%LOCALAPPDATA%\Google\Chrome\User Data` in `.env`
  - Optionally set `CHROME_PROFILE_DIR=Default` or `Profile 1` in `.env`
  - Run `pytest`
