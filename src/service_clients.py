from abc import ABC
from io import BytesIO
from typing import Any, Dict, List

import cv2
import numpy as np
import requests
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union


class ServiceClient(ABC):
    def __init__(self, service_ip, service_port):
        self.root_url = f"http://{service_ip}:{service_port}"
        self.timeout = 1

    def get_service_status(self):
        try:
            requests.get(self.root_url + "/health", timeout=self.timeout)
            return True
        except requests.ConnectionError:
            print(
                f"{self.__class__.__name__} is down: Connection Error for host at {self.root_url}."
            )
            return False
        except requests.Timeout:
            print(
                f"{self.__class__.__name__} is down: Timeout reached after {self.timeout} seconds for host at {self.root_url}."
            )
            return False


class WindowsWebcamClient(ServiceClient):
    def get_camera_input(self):
        # Connect to the video stream
        response = requests.get(self.root_url + "/video_feed", stream=True, timeout=5)
        if response.status_code != 200:
            raise Exception(f"Failed to connect to camera feed: {response.status_code}")

        # Read from the stream
        byte_stream = b""
        for chunk in response.iter_content(chunk_size=1024):
            byte_stream += chunk
            # Look for the JPEG frame boundary
            start = byte_stream.find(b"\xff\xd8")  # Start of JPEG
            end = byte_stream.find(b"\xff\xd9")  # End of JPEG

            if start != -1 and end != -1:
                jpg_data = byte_stream[start : end + 2]  # Extract frame
                byte_stream = byte_stream[end + 2 :]  # Remove processed frame

                # Convert to OpenCV image
                image = cv2.imdecode(
                    np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR
                )

                return image  # Return single frame as an OpenCV image

        return None  # Return None if no frame is found


class SystemWatchdogClient(ServiceClient):
    def get_windows_info(self):
        url = self.root_url + "/windows_info"
        response = requests.get(url)
        return response.json()

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


class VisionTrackingClient(ServiceClient):
    def save_profile(self, name):
        url = self.root_url + "/save_profile"
        params = {"name": name}
        response = requests.post(url, params=params)
        return response.status_code

    def list_profiles(self):
        url = self.root_url + "/list_profiles"
        response = requests.get(url)
        return response.json()

    def load_profile(self, profile_id):
        url = self.root_url + "/load_profile"
        params = {"profile_id": profile_id}
        response = requests.post(url, params=params)
        return response.status_code

    def delete_profile(self, profile_id):
        url = self.root_url + "/delete_profile"
        params = {"profile_id": profile_id}
        response = requests.post(url, params=params)
        return response.status_code

    def reset_profile(self, profile_id):
        url = self.root_url + "/reset_profile"
        params = {"profile_id": profile_id}
        response = requests.post(url, params=params)
        return response.status_code

    def add_calibration_point(self, x, y, image):
        url = self.root_url + "/cal_point"

        # Convert NumPy array to JPEG bytes
        _, img_encoded = cv2.imencode(".jpg", image)
        image_bytes = BytesIO(img_encoded.tobytes())  # Create file-like object

        # Prepare form data and files
        data = {"x": x, "y": y}  # Form fields
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}  # File upload

        # Send POST request
        response = requests.post(url, data=data, files=files)

        return response.status_code

    def predict_por(self, image):
        url = self.root_url + "/predict"

        # Convert NumPy array to JPEG bytes
        _, img_encoded = cv2.imencode(".jpg", image)
        image_bytes = BytesIO(img_encoded.tobytes())  # Create file-like object

        # Prepare form data and files
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}  # File upload

        # Send POST request
        response = requests.post(url, files=files)

        return response.json()["prediction"]
