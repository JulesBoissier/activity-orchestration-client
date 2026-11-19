# activity-orchestration-client

The hub of the attention-tracking system ("Reflective Application"). It talks to the three services, runs the calibration GUIs and the main tracking loop, stores attention samples in SQLite, and serves a Dash dashboard. See `../CLAUDE.md` for the full system and cross-repo contracts.

## Layout

- `main.py` — CLI entry: `python main.py backend|app|both`.
- `run_gunicorn.sh` — production-style launcher: gunicorn (4 workers, 127.0.0.1:8050) in the background + backend lifecycle in the foreground.
- `src/backend/lifecycle.py` — `ApplicationLifecycle` (health checks → profile select/create → optional accuracy test → `monitor_focus()` loop) and `ProfileManager` (CLI prompts via `input()` + `tabulate`).
- `src/backend/clients/` — one HTTP client per service, all subclassing `ServiceClient` (`root_url`, `get_service_status()` → `GET /health`, 1s timeout).
  - `windows_webcam_client.py` — opens `/video_feed`, returns the first JPEG found between SOI/EOI markers as a BGR ndarray.
  - `system_watchdog_client.py` — fetches `/windows_info` and computes visible regions with Shapely (front-to-back by `z_index`, clip to monitor, subtract already-covered area).
  - `vision_tracking_client.py` — profile CRUD, `add_calibration_point`, `predict_por`.
- `src/backend/screen_region.py` — `MonitorUtility` (monitor selection via `screeninfo`, calibration grid positions, quadrant regions).
- `src/backend/user_interfaces/` — fullscreen GUIs (Tkinter on `main`, Pygame on `develop`): `ProfileCreationGUI` (3×3 calibration dots, frames captured on ENTER and sent in a batch at the end) and `PerformanceMonitoringGUI` (random dots → RMSE + 2×2 quadrant confusion matrix).
- `src/backend/attention_tracker_store.py` — SQLAlchemy model `attention_tracker(id, timestamp, process_name, window_title)` in `sqlite:///attention_tracker.db`.
- `src/app/` — Dash dashboard: `app.py` (layout + callbacks; exposes `server` for gunicorn), `time_aggregation.py`, `period_iterators.py`, `chart_builder.py`, `stats_cards.py`, `metadata/exe_display_names.json`.
- `tools.py` — **stale**: imports modules that no longer exist (`src.focus_area_worker`, `src.service_clients`). Ignore or delete.

## Commands

```bash
pip install -r requirements.txt
python main.py backend        # lifecycle only (interactive prompts in the terminal)
python main.py app            # Dash dev server on :8050
./run_gunicorn.sh             # dashboard + backend together (PORT, WEB_CONCURRENCY env vars)
pytest tests/
pytest tests/test_service_clients.py::TestVisionTrackingClient::test_positive_status
```

Run everything from the repo root: both the lifecycle and the dashboard open `attention_tracker.db` by relative path, so different working directories mean different databases. Service endpoints come from env vars / `.env` (see `../CLAUDE.md`).

CI runs `pytest tests/` on Python 3.12 for pushes/PRs to `main` and `develop`.

## Tests

The suite tests behaviour, not internals. Every test docstring says what is tested and **why the behaviour is designed that way**; read the "Why" before changing or deleting a test.
- `tests/conftest.py`: fakes (`FakeWebcam`, `FakeVision`, `monitor()`, `window()`, `mjpeg_stream()`) and `make_lifecycle`, which builds an `ApplicationLifecycle` with fake services and a temp DB. Everything runs headless.
- `test_lifecycle.py` drives real ticks of `monitor_focus` via `run_ticks()` and asserts only on stored rows. If the loop is refactored (e.g. a `tick()` method), update `run_ticks` only.
- `xfail(strict=True)` tests document known bugs. When a fix lands they XPASS, which fails the suite; remove the marker in the same change.
- Accuracy is not unit-tested: use `../attention-benchmark` before merging to `develop`.

## How time is attributed (dashboard)

Each sample is one row. Its duration = `min(60s, gap to previous sample, gap to next sample)` (`compute_event_duration_seconds`). Durations are summed per bucket (hour/day/week/month depending on period) per process. Rows with empty `process_name` (no face / no PoR) are skipped. The optional "2% threshold" hides apps under 2% of the period's total.

## Gotchas (state of `main`)

- **Crash when PoR is off every window:** `_determine_viewed_window_info` can return `None` and `monitor_focus` then indexes it (`viewed_window_info['exe_name']`). Fixed on `multi-monitor-support` (not yet in `develop`).
- **Busy loop:** `monitor_focus` spins on `datetime.now()` comparisons without sleeping, so one core runs at 100%.
- **Timezone mismatch:** `timestamp` defaults to `func.now()` → SQLite `CURRENT_TIMESTAMP` (UTC), but the dashboard filters with local `datetime.now()`. Period boundaries are off by the UTC offset.
- **Display-name lookup lowercases the exe name**, so mixed-case keys in `exe_display_names.json` (`sourceTree.exe`, `7zFM.exe`) never match. Keep keys lowercase.
- **Two coordinate frames:** PoR and calibration targets are monitor-relative (`screeninfo` monitor, chosen by `monitor_index`, default 1 = primary); watchdog rects are absolute Windows desktop coords. Conversion is `monitor.x + x`. If the client runs in WSLg, its `screeninfo` view of the monitors must match Windows (DPI scaling breaks this).
- The dashboard reloads the **entire** table every second (`dcc.Interval` 1s), which gets slower as the DB grows.
- `PerformanceMonitoringGUI` breaks if any prediction is `[None, None]` (numpy maths and region lookup).
- `README` calls this module "dockerized" but there's no Dockerfile. It needs a display for Tkinter and `screeninfo`.
- `develop` (and `multi-monitor-support`, which adds two commits on top) replace Tkinter with Pygame and add a `VirtualMonitor` abstraction for multi-monitor support. Check those branches before working on GUIs or `screen_region.py`.
