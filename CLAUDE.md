# activity-orchestration-client

The hub of the attention-tracking system ("Reflective Application"). It talks to the three services, runs the calibration GUIs and the main tracking loop, stores attention samples in SQLite, and serves a Dash dashboard. See `../CLAUDE.md` for the full system and cross-repo contracts.

## Layout

- `main.py` — CLI entry: `python main.py backend|app|both`.
- `run_gunicorn.sh` — production-style launcher: gunicorn (4 workers, 127.0.0.1:8050) in the background + backend lifecycle in the foreground.
- `src/settings.py` — `Settings.from_env()`: the only place that reads the environment/`.env` (service hosts/ports, `TRACKING_PERIOD_S`, `TRACKED_MONITOR_INDEX`, `ACTIVITY_DB_URL`, `FRAMES_PER_PREDICTION`). Variables are listed in the workspace's `.env.example`.
- `src/backend/lifecycle.py` — `ApplicationLifecycle(settings, **collaborators)`: health checks → profile select/create → optional accuracy test → `monitor_focus()`, which runs `check_services()` + `tracker.tick()` through the scheduler until `stop()`. A tick that raises is logged and recorded as a `tick failed` gap. Clients, store and monitor default to being built from settings; pass them in to substitute fakes.
- `src/backend/tracker.py` — `Tracker.tick()`: one sample (a burst of `FRAMES_PER_PREDICTION` frames, default 3 → windows → one PoR from one `/predict` request → attribution → stored row), returns a `TickResult`. No timing, no looping. No camera frame short-circuits to a `camera unavailable` gap without querying the other services.
- `src/backend/attribution.py` — pure `attribute(por, visible_windows, monitor) -> Attribution` and the gap reasons (`no face`, `no window at point`, `camera unavailable`, `tick failed`).
- `src/backend/scheduler.py` — `run_every(period, job, stop)`: fixed-rate (start to start), sleeps between runs, skips missed slots after an overrun (logging a warning that names the settings to change), survives job exceptions. Clock injectable for tests.
- `src/backend/profile_manager.py` — `ProfileManager` (CLI prompts via `input()` + `tabulate`; re-prompts when the vision service answers 404 for an unknown profile id).
- `src/backend/accuracy_scoring.py` — pure scoring for the interactive accuracy test (Euclidean error, no-prediction count, 2×2 quadrant confusion with an off-monitor column), same rules as the benchmark.
- `src/backend/clients/` — one HTTP client per service, all subclassing `ServiceClient` (`root_url`, `get_service_status()` → `GET /health`, 1s timeout).
  - `windows_webcam_client.py` — `get_camera_jpeg()` returns `/snapshot`'s JPEG bytes unchanged (a frame captured after the request; `None` on 503), falling back to the first JPEG of `/video_feed` on older webcam services. `get_camera_input()` decodes it to a BGR array.
  - `system_watchdog_client.py` — fetches `/windows_info` and computes visible regions with Shapely (front-to-back by `z_index`, clip to monitor, subtract already-covered area).
  - `vision_tracking_client.py` — profile CRUD, `add_calibration_point`, `predict_por`. Frames may be JPEG bytes (sent unchanged, the normal path) or BGR arrays (encoded).
- `src/backend/screen_region.py` — `MonitorUtility` (monitor selection via `screeninfo`, calibration grid positions, quadrant regions).
- `src/backend/user_interfaces/` — fullscreen GUIs (Tkinter on `main`, Pygame on `develop`): `ProfileCreationGUI` (3×3 calibration dots, frames captured on ENTER and sent in a batch at the end) and `PerformanceMonitoringGUI` (random dots → RMSE + 2×2 quadrant confusion matrix).
- `src/backend/attention_tracker_store.py` — SQLAlchemy model `attention_tracker(id, timestamp, process_name, window_title, gap_reason)` (database from `ACTIVITY_DB_URL`, default `sqlite:///attention_tracker.db`). Timestamps are **local time** (Python `datetime.now`). `PRAGMA user_version` records the schema version; opening an older database converts version-0 UTC timestamps to local time once and adds the `gap_reason` column (version 2), under `BEGIN IMMEDIATE`.
- `src/app/` — Dash dashboard: `app.py` (layout + callbacks; exposes `server` for gunicorn), `time_aggregation.py`, `period_iterators.py`, `chart_builder.py`, `stats_cards.py`, `display_names.py` + `metadata/exe_display_names.json` (case-insensitive exe → readable name).
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
- `test_lifecycle.py` drives real ticks via `run_ticks()` (`tracker.tick()`) and asserts only on stored rows and gap reasons; `make_lifecycle` injects fakes through the constructor. `test_scheduler.py` runs the scheduler on a fake clock (no sleeping).
- `xfail(strict=True)` tests document known bugs. When a fix lands they XPASS, which fails the suite; remove the marker in the same change.
- Accuracy is not unit-tested: use `../attention-benchmark` before merging to `develop`.

## How time is attributed (dashboard)

Each sample is one row. Its duration = `min(60s, gap to previous sample, gap to next sample)` (`compute_event_duration_seconds`), where neighbours include gap rows. Durations are summed per bucket (hour/day/week/month depending on period) per process. Rows with empty `process_name` (no face / no PoR / no camera frame) count for no app, but still end the previous sample's time. The optional "2% threshold" hides apps under 2% of the period's total.

## Gotchas (state of `main`)

- **PoR on no window** (bare desktop, or off every window) records a gap row, like "no face".
- **Two coordinate frames:** PoR and calibration targets are relative to the tracked monitor (or `VirtualMonitor`); watchdog rects are absolute Windows desktop coords. Conversion is `monitor.x + x`. Monitor geometry comes from the watchdog's `/get_monitors` (Windows' view, same coordinates as the rects), falling back to local `screeninfo`. The calibration GUI still draws on this machine's display: if WSLg's layout differs from Windows' (scaling), the lifecycle logs a warning and dots may be misplaced.
- The dashboard reloads the **entire** table every second (`dcc.Interval` 1s), which gets slower as the DB grows.
- `README` calls this module "dockerized" but there's no Dockerfile. It needs a display for Tkinter and `screeninfo`.
- GUIs use Pygame (not Tkinter) and `MonitorUtility.select_monitor(None)` returns a `VirtualMonitor` spanning all displays; calibration positions and PoR are then relative to its top-left corner.
