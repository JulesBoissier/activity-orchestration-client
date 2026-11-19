"""The orchestrator's HTTP clients and the wire contracts they implement.

Each client is tested at the ``requests`` boundary: given what a service sends back, does
the client return the right thing, and does it send what the service expects? The formats
mirror the real services (see each test), so a failure here usually means a cross-repo
contract changed.
"""

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
import requests

from src.backend.clients.system_watchdog_client import SystemWatchdogClient
from src.backend.clients.vision_tracking_client import VisionTrackingClient
from src.backend.clients.windows_webcam_client import WindowsWebcamClient
from tests.conftest import mjpeg_stream

IP, PORT = "127.0.0.1", 8000
ALL_CLIENTS = [WindowsWebcamClient, VisionTrackingClient, SystemWatchdogClient]


@pytest.mark.parametrize("client_cls", ALL_CLIENTS)
class TestHealthCheck:
    """Every client shares ``get_service_status`` from ``ServiceClient``."""

    @patch("src.backend.clients.service_client.requests.get")
    def test_reachable_service_is_healthy(self, mock_get, client_cls):
        """A service that answers ``GET /health`` within the timeout is reported healthy.

        Why: the orchestrator gates startup and each tick on this. The 1s timeout keeps a
        hung service from stalling the tracking loop for long.
        """
        mock_get.return_value = MagicMock(status_code=200)

        assert client_cls(IP, PORT).get_service_status() is True
        mock_get.assert_called_once_with(f"http://{IP}:{PORT}/health", timeout=1)

    @pytest.mark.parametrize("error", [requests.ConnectionError, requests.Timeout])
    @patch("src.backend.clients.service_client.requests.get")
    def test_unreachable_service_is_unhealthy(self, mock_get, client_cls, error):
        """Connection errors and timeouts are reported as unhealthy rather than raised.

        Why: a service being down is an expected state at startup. The caller decides whether
        to retry; the client shouldn't crash it.
        """
        mock_get.side_effect = error()

        assert client_cls(IP, PORT).get_service_status() is False


def _streaming_response(body, chunk_size=1024, status=200):
    response = MagicMock(status_code=status)
    response.iter_content = lambda chunk_size=chunk_size: (
        body[i : i + chunk_size] for i in range(0, len(body), chunk_size)
    )
    return response


class TestWebcamClient:
    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_returns_first_frame_of_mjpeg_stream(self, mock_get):
        """``get_camera_input`` returns the first JPEG of ``/video_feed`` as a BGR image.

        Why: the orchestrator needs one frame per tick, and the webcam service only offers a
        continuous MJPEG stream. The stream format here is the one the webcam service emits.
        Frames are larger than one chunk, so this also checks reassembly across chunks.
        """
        yy, xx = np.mgrid[0:120, 0:160]
        first = np.dstack([xx * 1.5, yy * 2, (xx + yy) % 256]).astype(np.uint8)
        second = np.zeros((120, 160, 3), dtype=np.uint8)
        mock_get.return_value = _streaming_response(mjpeg_stream([first, second]))

        image = WindowsWebcamClient(IP, 8001).get_camera_input()

        assert image.shape == first.shape
        assert np.abs(image.astype(int) - first.astype(int)).mean() < 20  # JPEG-lossy
        assert mock_get.call_args.args[0] == f"http://{IP}:8001/video_feed"

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_empty_stream_returns_none(self, mock_get):
        """A stream that ends before a full frame arrives yields ``None``.

        Why: the webcam service ends the stream when the camera can't be read (unplugged or
        in use by another app).
        """
        mock_get.return_value = _streaming_response(b"")

        assert WindowsWebcamClient(IP, 8001).get_camera_input() is None

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_error_status_raises(self, mock_get):
        """A non-200 answer from ``/video_feed`` raises.

        Why: unlike a missing frame, an HTTP error means the service is misconfigured. It
        should be visible, not silently recorded as "no face".
        """
        mock_get.return_value = _streaming_response(b"", status=500)

        with pytest.raises(Exception):
            WindowsWebcamClient(IP, 8001).get_camera_input()


class TestVisionClient:
    FRAME = np.full((48, 64, 3), 128, dtype=np.uint8)

    @staticmethod
    def _sent_image(call):
        name, payload, mime = call.kwargs["files"]["file"]
        data = payload.read() if hasattr(payload, "read") else payload
        assert mime == "image/jpeg"
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

    @patch("src.backend.clients.vision_tracking_client.requests.post")
    def test_predict_sends_jpeg_and_returns_prediction(self, mock_post):
        """``predict_por`` uploads the frame as JPEG to ``/predict`` and returns ``[x, y]``.

        Why: matches the vision service contract (multipart field ``file``, response
        ``{"prediction": [x, y]}`` with nulls when no PoR).
        """
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"prediction": [12.5, None]}
        )

        result = VisionTrackingClient(IP, PORT).predict_por(self.FRAME)

        assert result == [12.5, None]
        assert mock_post.call_args.args[0] == f"http://{IP}:{PORT}/predict"
        assert self._sent_image(mock_post.call_args).shape == self.FRAME.shape

    @patch("src.backend.clients.vision_tracking_client.requests.post")
    def test_calibration_point_sends_target_coordinates(self, mock_post):
        """``add_calibration_point`` sends the dot position as form fields ``x``/``y`` with the frame.

        Why: the vision service stores these as the ground-truth screen position for the
        frame's gaze features. The coordinate space chosen here (monitor-local pixels) is
        the space predictions come back in.
        """
        mock_post.return_value = MagicMock(status_code=200)

        VisionTrackingClient(IP, PORT).add_calibration_point(640, 360, self.FRAME)

        assert mock_post.call_args.args[0] == f"http://{IP}:{PORT}/cal_point"
        assert mock_post.call_args.kwargs["data"] == {"x": 640, "y": 360}
        assert self._sent_image(mock_post.call_args).shape == self.FRAME.shape
