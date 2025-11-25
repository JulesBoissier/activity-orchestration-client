from typing import Any, Dict, List

import requests
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from src.clients.service_client import ServiceClient


class SystemWatchdogClient(ServiceClient):
    def get_windows_info(self):
        url = self.root_url + "/windows_info"
        response = requests.get(url)
        return response.json()

    def get_visible_windows(
        self,
        monitor=None,
        exclude_exe_names: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """Fetch windows from the watchdog service and compute visible portions within an optional monitor.
        Returns a list of dicts with keys: exe_name, title, z_index, pid, clipped_rect, visible_rects, visible_area, visible_fraction.
        """
        data = self.get_windows_info()
        windows: List[Dict[str, Any]] = (
            data.get("windows", data) if isinstance(data, dict) else data
        )
        return self.compute_visible_windows(
            windows=windows, monitor=monitor, exclude_exe_names=exclude_exe_names
        )

    def _geometry_to_rects(self, geometry) -> List[List[int]]:
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
        self,
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
                monitor.x,
                monitor.y,
                monitor.x + monitor.width,
                monitor.y + monitor.height,
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
                        # stable keys for consumers
                        "exe_name": w.get("exe_name"),
                        # keep a backwards-compatible alias just in case
                        "name": w.get("exe_name"),
                        "title": w["title"],
                        "z_index": w.get("z_index", 0),
                        "pid": w.get("pid"),
                        "clipped_rect": self._geometry_to_rects(clipped),
                        "visible_rects": self._geometry_to_rects(visible),
                        "visible_area": visible_area,
                        "visible_fraction": (visible_area / window_area)
                        if window_area > 0
                        else 0.0,
                    }
                )

        return results
