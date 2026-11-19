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
    def _jpeg_file(image):
        """Multipart file entry for a frame: JPEG bytes are sent as they are, arrays are encoded.

        Forwarding the webcam's JPEG unchanged avoids a decode/re-encode round trip, which
        costs CPU and adds a second round of compression artefacts.
        """
        if isinstance(image, (bytes, bytearray)):
            data = bytes(image)
        else:
            ok, encoded = cv2.imencode(".jpg", image)
            if not ok:
                raise ValueError("could not encode frame as JPEG")
            data = encoded.tobytes()
        return {"file": ("image.jpg", BytesIO(data), "image/jpeg")}

    def add_calibration_point(self, x, y, image):
        """Send one calibration frame (JPEG bytes or a BGR array) for screen point (x, y)."""
        url = self.root_url + "/cal_point"
        data = {"x": x, "y": y}
        response = requests.post(url, data=data, files=self._jpeg_file(image))
        return response.status_code

    def predict_por(self, image):
        """Point of regard ``[x, y]`` (or ``[None, None]``) for a frame (JPEG bytes or BGR array)."""
        url = self.root_url + "/predict"
        response = requests.post(url, files=self._jpeg_file(image))
        return response.json()["prediction"]
