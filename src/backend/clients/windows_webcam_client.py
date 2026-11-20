from typing import List, Optional

import cv2
import numpy as np
import requests

from src.backend.clients.service_client import ServiceClient

SOI, EOI = b"\xff\xd8", b"\xff\xd9"


class WindowsWebcamClient(ServiceClient):
    def get_camera_jpeg(self) -> Optional[bytes]:
        """One webcam frame as the JPEG bytes the service sent, or ``None`` if there is none.

        Uses ``/snapshot`` (a frame captured after the request). Falls back to the first frame
        of ``/video_feed`` for webcam services that predate ``/snapshot``.
        """
        response = requests.get(self.root_url + "/snapshot", timeout=5)
        if response.status_code == 200:
            return response.content
        if response.status_code == 503:  # the service is up but can't read the camera
            return None
        if response.status_code != 404:
            raise Exception(f"Failed to get a camera frame: {response.status_code}")
        return self._first_video_feed_frame()

    def get_camera_jpegs(self, count: int) -> List[bytes]:
        """Up to ``count`` consecutive frames (a burst); frames the camera couldn't give are skipped.

        Each ``/snapshot`` waits for the next camera frame, so the frames are one frame
        interval apart (~33 ms at 30 fps).
        """
        frames = (self.get_camera_jpeg() for _ in range(count))
        return [f for f in frames if f is not None]

    def get_camera_input(self) -> Optional[np.ndarray]:
        """One webcam frame decoded to a BGR image, or ``None``."""
        jpeg = self.get_camera_jpeg()
        if jpeg is None:
            return None
        return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _first_video_feed_frame(self) -> Optional[bytes]:
        response = requests.get(self.root_url + "/video_feed", stream=True, timeout=5)
        if response.status_code != 200:
            raise Exception(f"Failed to connect to camera feed: {response.status_code}")

        byte_stream = b""
        for chunk in response.iter_content(chunk_size=1024):
            byte_stream += chunk
            start = byte_stream.find(SOI)
            end = byte_stream.find(EOI, start + 2) if start != -1 else -1
            if start != -1 and end != -1:
                return byte_stream[start : end + 2]
        return None
