import argparse
import os
import shlex
import signal
import subprocess
import sys
from typing import Optional

from src.app.app import app
from src.backend.lifecycle import ApplicationLifecycle


def run_backend():
    lifecycle = ApplicationLifecycle(period=2)
    lifecycle.run()


def run_app_dev():
    app.run(debug=True)


def run_both():
    # Start Dash app under gunicorn and run backend in the foreground
    cmd = f"gunicorn -b 127.0.0.1:8050 src.app.app:server"

    gunicorn_proc = subprocess.Popen(shlex.split(cmd))

    try:
        run_backend()
    except KeyboardInterrupt:
        # Allow Ctrl+C to break out and proceed to cleanup
        pass
    finally:
        try:
            if gunicorn_proc.poll() is None:
                gunicorn_proc.terminate()
                gunicorn_proc.wait(timeout=10)
        except Exception:
            try:
                gunicorn_proc.kill()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Run components: backend, app, or both."
    )
    parser.add_argument(
        "mode",
        choices=["backend", "app", "both"],
        help="What to run: backend (ApplicationLifecycle), app (Dash dev), both (gunicorn + backend).",
    )
    args = parser.parse_args()

    if args.mode == "backend":
        run_backend()
    elif args.mode == "app":
        run_app_dev()
    elif args.mode == "both":
        run_both()
    else:
        parser.error("Unknown mode")


if __name__ == "__main__":
    main()
