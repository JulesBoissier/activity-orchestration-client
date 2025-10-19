# from src.lifecycle import ApplicationLifecycle

# if __name__ == "__main__":
#     app = ApplicationLifecycle(period=2)
#     app.run()

import os

from dotenv import load_dotenv

from src.screen_region import MonitorUtility
from src.service_clients import SystemWatchdogClient

load_dotenv()

from typing import Any, Dict, List

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union


def _geometry_to_rects(geometry) -> List[List[int]]:
    """Convert a shapely geometry to a list of rectangle bounds [l, t, r, b].
    For complex polygons, returns the bounds of each polygon part. Coordinates are ints.
    """
    rects: List[List[int]] = []
    if geometry.is_empty:
        return rects

    if isinstance(geometry, Polygon):
        minx, miny, maxx, maxy = geometry.bounds
        rects.append([int(minx), int(miny), int(maxx), int(maxy)])
    elif isinstance(geometry, MultiPolygon):
        for poly in geometry.geoms:
            minx, miny, maxx, maxy = poly.bounds
            rects.append([int(minx), int(miny), int(maxx), int(maxy)])
    else:
        # Fallback to overall bounds for any other geometry types
        minx, miny, maxx, maxy = geometry.bounds
        rects.append([int(minx), int(miny), int(maxx), int(maxy)])
    return rects


def compute_visible_windows(
    windows: List[Dict[str, Any]],
    monitor=None,
    exclude_exe_names: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Compute visible portions of top-level windows within a monitor's bounds.

    - Windows are sorted by z_index ascending (front-most first)
    - Each window is clipped to the monitor rectangle
    - Minimized/off-screen windows are ignored (empty intersection)
    - Visible area is computed by subtracting already covered regions
    """
    # Optionally exclude certain executables (e.g., Windows taskbar via explorer.exe)
    if exclude_exe_names:
        windows = [
            w for w in windows if w.get("exe_name") not in set(exclude_exe_names)
        ]
    if monitor is None:
        # If no monitor provided, assume full virtual screen starting at 0,0 sized to max extents from windows
        if not windows:
            return []
        minx = min(w["rect"][0] for w in windows)
        miny = min(w["rect"][1] for w in windows)
        maxx = max(w["rect"][2] for w in windows)
        maxy = max(w["rect"][3] for w in windows)
        monitor_box = box(minx, miny, maxx, maxy)
    else:
        monitor_box = box(
            monitor.x, monitor.y, monitor.x + monitor.width, monitor.y + monitor.height
        )

    # Sort windows by z_index ascending (front-most first). Default missing z to 0
    ordered = sorted(windows, key=lambda w: w.get("z_index", 0))

    covered = None
    results: List[Dict[str, Any]] = []

    for w in ordered:
        left, top, right, bottom = w["rect"]

        # Skip obviously invalid windows (degenerate rects)
        if right <= left or bottom <= top:
            continue

        window_geom = box(left, top, right, bottom)
        clipped = window_geom.intersection(monitor_box)

        # Ignore minimized/off-screen windows (e.g., -32000 coords) or those not intersecting the monitor
        if clipped.is_empty:
            continue

        visible = clipped if covered is None else clipped.difference(covered)

        # Update covered area regardless of visibility; window still occludes below
        covered = clipped if covered is None else unary_union([covered, clipped])

        # Only keep windows with some visible area
        if not visible.is_empty:
            window_area = clipped.area
            visible_area = visible.area
            results.append(
                {
                    "name": w["exe_name"],
                    "title": w["title"],
                    "clipped_rect": _geometry_to_rects(clipped),
                    "visible_rects": _geometry_to_rects(visible),
                    "visible_area": visible_area,
                    "visible_fraction": (visible_area / window_area)
                    if window_area > 0
                    else 0.0,
                }
            )

    return results


if __name__ == "__main__":
    swc = SystemWatchdogClient(
        os.getenv("SYSTEM_WATCHDOG_SERVICE_IP", "127.0.0.1"),
        int(os.getenv("SYSTEM_WATCHDOG_SERVICE_PORT", 8002)),
    )
    system_watchdog_client_ok = swc.get_service_status()

    if system_watchdog_client_ok:
        info = swc.get_windows_info()

    # print(info)
    # for window in info:
    #     print()
    #     print(f"{window['title']} / {window['rect']} / {window['z_index']}")

    # Select monitor 1 (primary) and compute visible windows within its bounds
    monitor = MonitorUtility.select_monitor(1)
    results = compute_visible_windows(info, monitor, exclude_exe_names=["explorer.exe"])
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
