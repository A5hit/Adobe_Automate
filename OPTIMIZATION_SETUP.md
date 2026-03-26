# Adobe Automate — Device Optimization Setup Guide

> **Target:** Maximum performance for Playwright-based Adobe Express automation
> **Device Spec:** i5-11320H, 16GB RAM, NVIDIA MX450 + Intel Iris Xe, NVMe SSD
> **Goal:** 5 parallel workers, GPU-accelerated canvas rendering

---

## Pre-Setup Checklist

Before starting, confirm the following:

- Laptop is plugged into charger
- Laptop is on a hard flat surface (not bed/carpet)
- Cooling pad is connected (if available)
- All non-essential apps are closed
- Task Manager is open to monitor progress

---

## STEP 1 — NVIDIA Control Panel Settings

1. Right-click Desktop → **NVIDIA Control Panel**
2. Go to **Manage 3D Settings → Global Settings**
   - Power management mode → `Prefer Maximum Performance`
   - Texture filtering quality → `High Performance`
   - Vertical sync → `Off`
   - Low Latency Mode → `Ultra`
3. Go to **Manage 3D Settings → Program Settings**
4. Click **Add** → navigate to the Playwright Chrome:
   - First run this in CMD to find the path:
     ```cmd
     where /r "%LOCALAPPDATA%\ms-playwright" chrome.exe
     ```
   - Example path: `C:\Users\YourName\AppData\Local\ms-playwright\chromium-1140\chrome-win\chrome.exe`
5. Set **Preferred graphics processor** → `High-performance NVIDIA processor`
6. Click **Apply**
7. Go to **Set PhysX Configuration** → select `NVIDIA GeForce MX450`
8. Click **Apply**

> **Note:** Select the Playwright Chrome (found via CMD above), NOT the regular Chrome browser.

---

## STEP 2 — Windows Power & Performance Settings

### 2A — Enable Ultimate Performance Power Plan

Open CMD as Administrator and run:

```cmd
powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
```

Then:
1. Control Panel → Power Options
2. Select **Ultimate Performance**

### 2B — Visual Effects

1. `Win + R` → type `sysdm.cpl` → Enter
2. Advanced tab → Performance → **Settings**
3. Select **Adjust for best performance**
4. Click Apply → OK

### 2C — Disable Sleep During Automation

1. Settings → System → Power & Sleep
2. Screen → **Never**
3. Sleep → **Never**

### 2D — Turn Off Game Mode

1. Settings → Gaming → Game Mode → **OFF**

### 2E — Enable Hardware Accelerated GPU Scheduling

1. Settings → System → Display → Graphics Settings
2. Hardware-accelerated GPU scheduling → **ON**

---

## STEP 3 — Disable Background Services

### 3A — Via Services

1. `Win + R` → type `services.msc` → Enter
2. Find each service below → Right-click → Properties → Startup type → **Disabled** → Stop

| Service | Action |
|---|---|
| SysMain (Superfetch) | Disable |
| Windows Search | Disable |
| Connected User Experiences | Disable |
| Xbox services (all) | Disable |

### 3B — Via Task Manager Startup Tab

1. Task Manager → **Startup** tab
2. Disable the following:

| App | Action |
|---|---|
| OneDrive | Disable |
| Microsoft Teams | Disable |
| Discord / Slack | Disable |
| Any browser auto-start | Disable |
| Any manufacturer bloatware | Disable |

---

## STEP 4 — Chrome GPU Registry Keys

Open CMD as **Administrator** and run these commands **one at a time**:

```cmd
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v "HardwareAccelerationModeEnabled" /t REG_DWORD /d 1 /f
```

```cmd
reg add "HKLM\SOFTWARE\Policies\Google\Chrome" /v "GpuRasterization" /t REG_DWORD /d 1 /f
```

Expected output after each command:
```
The operation completed successfully.
```

---

## STEP 5 — Windows Graphics Settings for Playwright Chrome

1. Settings → System → Display → **Graphics Settings**
2. Click **Browse**
3. Navigate to Playwright Chrome (same path from Step 1 CMD command)
4. Click **Options** → **High Performance**
5. Save

---

## STEP 6 — Update conftest.py

Open `conftest.py` and find this block:

```python
launch_kwargs: dict[str, object] = {
    "headless": headless,
    "args": ["--disable-http2"],
}
```

Replace it with:

```python
launch_kwargs: dict[str, object] = {
    "headless": headless,
    "args": [
        "--disable-http2",

        # Force NVIDIA MX450
        "--enable-gpu",
        "--use-angle=gl",
        "--enable-gpu-rasterization",
        "--enable-zero-copy",
        "--enable-oop-rasterization",
        "--canvas-oop-rasterization",
        "--enable-accelerated-2d-canvas",
        "--enable-accelerated-video-decode",
        "--enable-accelerated-video-encode",

        # RAM optimization
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--aggressive-cache-discard",
        "--memory-pressure-off",

        # Performance
        "--no-sandbox",
        "--disable-software-rasterizer",
        "--renderer-process-limit=5",
        "--max_old_space_size=512",
    ],
}
```

---

## STEP 7 — Update .env File

Replace the contents of `.env` with:

```env
BASE_URL=https://new.express.adobe.com/
HEADLESS=0
ADOBE_ACCOUNTS_CSV=accounts.csv
ADOBE_RESULTS_CSV=reports\adobe_results.csv
ADOBE_CONSUMED_ACCOUNTS_CSV=reports\adobe_consumed_accounts.csv

PW_DEFAULT_TIMEOUT_MS=12000
PW_EXPECT_TIMEOUT_MS=12000
PW_SHORT_TIMEOUT_MS=4000
PW_BRIEF_TIMEOUT_MS=2000
PW_QUICK_TIMEOUT_MS=1000
PW_AUTH_TIMEOUT_MS=25000
PW_NAVIGATION_TIMEOUT_MS=40000
PW_LONG_TIMEOUT_MS=35000
PW_LOGIN_FINAL_URL_TIMEOUT_MS=60000
```

---

## STEP 8 — Set Workers to 5

Open `pytest.ini` and add:

```ini
[pytest]
addopts = -n 5
```

---

## STEP 9 — Run the Automation

```cmd
cd D:\Adobe_Automate
pytest tests/ -n 5
```

---

## STEP 10 — Verify GPU is Working

Once automation starts, open Task Manager and confirm:

| Metric | Expected | Status |
|---|---|---|
| GPU 0 (MX450) usage | 30–60% | ✅ GPU active |
| GPU 0 temperature | < 88°C | ✅ Safe |
| RAM usage | ~12–13 GB | ✅ Within limit |
| CPU usage | ~70–85% | ✅ Balanced |

> If GPU 0 (MX450) still shows 0%, repeat Steps 1 and 5 and restart the automation.

---

## Temperature Warning

| Temperature | Status | Action |
|---|---|---|
| < 80°C | ✅ Normal | Continue |
| 80–88°C | ⚠️ Warm | Check cooling pad |
| 88–95°C | 🔴 Hot | Reduce to 4 workers |
| > 95°C | 🔴 Critical | Stop immediately |

---

## Expected Output Per Device

| Metric | Value |
|---|---|
| Workers | 5 |
| Accounts/hour | ~150 |
| Accounts/day (14 hrs) | ~2,100 |
| Accounts/day (18 hrs) | ~2,700 |

---

---

# ROLLBACK GUIDE

> Run these steps when the project is complete to restore the device to its original state.
> **Estimated time: ~10 minutes**

---

## ROLLBACK 1 — NVIDIA Control Panel

1. Right-click Desktop → NVIDIA Control Panel
2. Manage 3D Settings → **Program Settings**
3. Find the Playwright `chrome.exe` entry → Click **Remove**
4. Global Settings → Power management mode → `Optimal Power`
5. Click **Apply**

---

## ROLLBACK 2 — Windows Graphics Settings

1. Settings → System → Display → Graphics Settings
2. Find the Playwright `chrome.exe` entry
3. Click **Options** → **Power Saving** OR click **Remove**
4. Save

---

## ROLLBACK 3 — Delete Registry Keys

Open CMD as **Administrator** and run these one at a time:

```cmd
reg delete "HKLM\SOFTWARE\Policies\Google\Chrome" /v "HardwareAccelerationModeEnabled" /f
```

```cmd
reg delete "HKLM\SOFTWARE\Policies\Google\Chrome" /v "GpuRasterization" /f
```

Expected output after each:
```
The operation completed successfully.
```

---

## ROLLBACK 4 — Power Plan

1. Control Panel → Power Options
2. Select **Balanced** (default Windows plan)

To remove the Ultimate Performance plan entirely, run in CMD (Admin):

```cmd
powercfg -delete e9a42b02-d5df-448d-aa00-03f14749eb61
```

---

## ROLLBACK 5 — Visual Effects

1. `Win + R` → `sysdm.cpl` → Enter
2. Advanced → Performance → Settings
3. Select **Let Windows choose what's best**
4. Click Apply → OK

---

## ROLLBACK 6 — Re-enable Services

1. `Win + R` → `services.msc` → Enter
2. Re-enable the following (Right-click → Properties → Startup type → **Automatic** → Start):

| Service | Startup Type |
|---|---|
| SysMain (Superfetch) | Automatic |
| Windows Search | Automatic |
| Connected User Experiences | Automatic |
| Xbox services (if used) | Automatic |

---

## ROLLBACK 7 — Re-enable Startup Apps

1. Task Manager → **Startup** tab
2. Re-enable whatever was disabled in Step 3B:

| App | Action |
|---|---|
| OneDrive | Enable (if used) |
| Teams / Slack / Discord | Enable (if used) |
| Any other apps disabled | Enable |

---

## ROLLBACK 8 — Restore conftest.py

Find the browser launch block and restore to original:

```python
launch_kwargs: dict[str, object] = {
    "headless": headless,
    "args": ["--disable-http2"],
}
```

---

## ROLLBACK 9 — Restore pytest.ini

Remove the `-n 5` workers line:

```ini
[pytest]
addopts =
```

---

## ROLLBACK 10 — Restore Power & Sleep Settings

1. Settings → System → Power & Sleep
2. Screen → set back to **10–15 minutes**
3. Sleep → set back to **30 minutes**
4. Settings → Gaming → Game Mode → **ON**

---

## ROLLBACK 11 — Restore .env Timeouts (Optional)

If you want to restore original timeouts:

```env
BASE_URL=https://new.express.adobe.com/
HEADLESS=0
ADOBE_ACCOUNTS_CSV=accounts.csv
ADOBE_RESULTS_CSV=reports\adobe_results.csv
ADOBE_CONSUMED_ACCOUNTS_CSV=reports\adobe_consumed_accounts.csv

PW_DEFAULT_TIMEOUT_MS=10000
PW_EXPECT_TIMEOUT_MS=10000
PW_SHORT_TIMEOUT_MS=5000
PW_BRIEF_TIMEOUT_MS=3000
PW_QUICK_TIMEOUT_MS=1000
PW_AUTH_TIMEOUT_MS=15000
PW_NAVIGATION_TIMEOUT_MS=30000
PW_LONG_TIMEOUT_MS=30000
PW_LOGIN_FINAL_URL_TIMEOUT_MS=60000
```

---

## Quick Rollback Checklist

```
□ ROLLBACK 1  — NVIDIA Control Panel — remove chrome entries, reset power mode
□ ROLLBACK 2  — Windows Graphics Settings — remove chrome entry
□ ROLLBACK 3  — Run 2 registry delete commands in CMD (Admin)
□ ROLLBACK 4  — Power Plan → switch back to Balanced
□ ROLLBACK 5  — Visual Effects → Let Windows choose
□ ROLLBACK 6  — services.msc → re-enable SysMain + Windows Search
□ ROLLBACK 7  — Task Manager Startup → re-enable your apps
□ ROLLBACK 8  — conftest.py → restore original launch_kwargs
□ ROLLBACK 9  — pytest.ini → remove -n 5
□ ROLLBACK 10 — Power & Sleep → restore original timers
□ ROLLBACK 11 — .env → restore original timeouts (optional)
```
