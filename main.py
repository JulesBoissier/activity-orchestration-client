# from src.lifecycle import ApplicationLifecycle

# if __name__ == "__main__":
#     app = ApplicationLifecycle(period=2)
#     app.run()

import os

from dotenv import load_dotenv

from src.screen_region import MonitorUtility
from src.service_clients import SystemWatchdogClient

load_dotenv()

if __name__ == "__main__":
    swc = SystemWatchdogClient(
        os.getenv("SYSTEM_WATCHDOG_SERVICE_IP", "127.0.0.1"),
        int(os.getenv("SYSTEM_WATCHDOG_SERVICE_PORT", 8002)),
    )
    system_watchdog_client_ok = swc.get_service_status()

    if system_watchdog_client_ok:
        info = swc.get_windows_info()
    else:
        print("System watchdog client is not running")

    # Select monitor 1 (primary) and compute visible windows within its bounds
    monitor = MonitorUtility.select_monitor(1)

    print(f"Monitor: {monitor}")
    results = swc.compute_visible_windows(
        info, monitor
    )  # , exclude_exe_names=["explorer.exe"])

    print("RESULTS:")
    for r in results:
        print()
        print(
            {
                "name": r["name"],
                "title": r["title"],
                "clipped_rect": r["clipped_rect"],
                "visible_rects": r["visible_rects"],
                "visible_area": r["visible_area"],
                "visible_fraction": r["visible_fraction"],
            }
        )
