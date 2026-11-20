from io import BytesIO

import cv2
import numpy as np
import requests

from src.backend.clients.service_client import ServiceClient


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

    @staticmethod
    def _jpeg_bytes(image) -> bytes:
        """JPEG bytes for a frame: bytes are sent as they are, arrays are encoded.

        Forwarding the webcam's JPEG unchanged avoids a decode/re-encode round trip, which
        costs CPU and adds a second round of compression artefacts.
        """
        if isinstance(image, (bytes, bytearray)):
            return bytes(image)
        ok, encoded = cv2.imencode(".jpg", image)
        if not ok:
            raise ValueError("could not encode frame as JPEG")
        return encoded.tobytes()

    @classmethod
    def _jpeg_file(cls, image):
        """Multipart file entry for one frame."""
        return {"file": ("image.jpg", BytesIO(cls._jpeg_bytes(image)), "image/jpeg")}

    def add_calibration_point(self, x, y, image, implicit: bool = False):
        """Send a calibration frame or burst (JPEG bytes or BGR arrays) for screen point (x, y).

        ``implicit=True`` marks evidence gathered during use (a click) rather than a
        calibration dot. Returns the HTTP status for explicit points (as before) and the
        service's answer (``{"added": ...}``) for implicit ones.
        """
        url = self.root_url + "/cal_point"
        data = {"x": x, "y": y}
        if implicit:
            data["implicit"] = "true"
        if isinstance(image, (list, tuple)):
            files = [
                ("file", (f"frame{i}.jpg", BytesIO(self._jpeg_bytes(f)), "image/jpeg"))
                for i, f in enumerate(image)
            ]
        else:
            files = self._jpeg_file(image)
        response = requests.post(url, data=data, files=files)
        if not implicit:
            return response.status_code
        return response.json() if response.status_code == 200 else {"added": False}

    def predict_por(self, image):
        """Point of regard ``[x, y]`` (or ``[None, None]``) for one frame or a burst.

        ``image`` is a frame (JPEG bytes or BGR array) or a list of frames. A burst is sent
        as repeated ``file`` parts; the vision service averages their gaze features into
        one prediction.
        """
        url = self.root_url + "/predict"
        if isinstance(image, (list, tuple)):
            files = [
                ("file", (f"frame{i}.jpg", BytesIO(self._jpeg_bytes(f)), "image/jpeg"))
                for i, f in enumerate(image)
            ]
        else:
            files = self._jpeg_file(image)
        response = requests.post(url, files=files)
        return response.json()["prediction"]
