import cv2
import numpy as np
import requests

from src.clients.service_client import ServiceClient


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
