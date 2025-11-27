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
