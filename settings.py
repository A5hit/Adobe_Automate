import os


def _read_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}.") from exc

    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}.")
    return value


PW_DEFAULT_TIMEOUT_MS = _read_int_env("PW_DEFAULT_TIMEOUT_MS", 10_000)
PW_EXPECT_TIMEOUT_MS = _read_int_env("PW_EXPECT_TIMEOUT_MS", 10_000)
PW_SHORT_TIMEOUT_MS = _read_int_env("PW_SHORT_TIMEOUT_MS", 5_000)
PW_BRIEF_TIMEOUT_MS = _read_int_env("PW_BRIEF_TIMEOUT_MS", 3_000)
PW_QUICK_TIMEOUT_MS = _read_int_env("PW_QUICK_TIMEOUT_MS", 1_000)
PW_AUTH_TIMEOUT_MS = _read_int_env("PW_AUTH_TIMEOUT_MS", 15_000)
PW_NAVIGATION_TIMEOUT_MS = _read_int_env("PW_NAVIGATION_TIMEOUT_MS", 30_000)
PW_LONG_TIMEOUT_MS = _read_int_env("PW_LONG_TIMEOUT_MS", 30_000)
PW_LOGIN_FINAL_URL_TIMEOUT_MS = _read_int_env("PW_LOGIN_FINAL_URL_TIMEOUT_MS", 60_000)
