from abc import ABC
from io import BytesIO

import cv2
import numpy as np
import requests


class ServiceClient(ABC):
    def __init__(self, service_ip, service_port):
        self.root_url = f"http://{service_ip}:{service_port}"

    def get_service_status(self):
        try:
            requests.get(self.root_url + "/health", timeout=1)
            return True
        except requests.ConnectionError as e:
            print(f"Windows Webcam service is down: {e}")
            return False
        except requests.Timeout as e:
            print(f"Windows Webcam service is down: {e}")
            return False


class WindowsWebcamClient(ServiceClient):
    def get_camera_input(self):
        # Connect to the video stream
        response = requests.get(self.root_url + "/video_feed", stream=True, timeout=5)
        if response.status_code != 200:
            raise Exception(f"Failed to connect to camera feed: {response.status_code}")

        print("Reading from stream...")

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

        return response.json()
