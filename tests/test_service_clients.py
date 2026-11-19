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


def _routes(**by_path):
    """A fake ``requests.get`` answering each URL path with the given response."""

    def get(url, *args, **kwargs):
        return by_path[url.rsplit("/", 1)[1]]

    return get


def _gradient(seed=0):
    yy, xx = np.mgrid[0:120, 0:160]
    return np.dstack([xx * 1.5, yy * 2, (xx + yy + seed) % 256]).astype(np.uint8)


class TestWebcamClient:
    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_snapshot_bytes_are_returned_unchanged(self, mock_get):
        """``get_camera_jpeg`` returns ``/snapshot``'s JPEG exactly as the service sent it.

        Why: ``/snapshot`` guarantees a frame captured after the request (no stale buffered
        frame). Keeping the bytes unchanged lets the orchestrator forward them to the vision
        service without a decode/re-encode round trip, which is what the benchmark measures.
        """
        jpeg = cv2.imencode(".jpg", _gradient())[1].tobytes()
        mock_get.side_effect = _routes(snapshot=MagicMock(status_code=200, content=jpeg))

        client = WindowsWebcamClient(IP, 8001)

        assert client.get_camera_jpeg() == jpeg
        assert client.get_camera_input().shape == (120, 160, 3)

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_falls_back_to_video_feed_on_older_services(self, mock_get):
        """If ``/snapshot`` doesn't exist (404), the first JPEG of ``/video_feed`` is used.

        Why: the webcam service and orchestrator are deployed separately; a newer
        orchestrator must still work with a webcam service that predates ``/snapshot``.
        Frames span several chunks, so this also checks reassembly.
        """
        first, second = _gradient(0), _gradient(99)
        mock_get.side_effect = _routes(
            snapshot=MagicMock(status_code=404),
            video_feed=_streaming_response(mjpeg_stream([first, second])),
        )

        jpeg = WindowsWebcamClient(IP, 8001).get_camera_jpeg()

        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        assert np.abs(image.astype(int) - first.astype(int)).mean() < 20  # JPEG-lossy

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_unavailable_camera_returns_none(self, mock_get):
        """A 503 from ``/snapshot`` (camera unplugged or in use) yields ``None``.

        Why: a missing camera is a temporary condition. The tracking loop records a gap
        and the calibration GUI asks to retry the dot; neither should crash.
        """
        mock_get.side_effect = _routes(snapshot=MagicMock(status_code=503))

        assert WindowsWebcamClient(IP, 8001).get_camera_jpeg() is None

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_old_service_with_empty_stream_returns_none(self, mock_get):
        """On the ``/video_feed`` fallback, a stream that ends without a frame yields ``None``.

        Why: older webcam services end the stream when the camera can't be read.
        """
        mock_get.side_effect = _routes(
            snapshot=MagicMock(status_code=404), video_feed=_streaming_response(b"")
        )

        assert WindowsWebcamClient(IP, 8001).get_camera_jpeg() is None

    @patch("src.backend.clients.windows_webcam_client.requests.get")
    def test_error_status_raises(self, mock_get):
        """Any other error status from the webcam service raises.

        Why: unlike a missing frame, a server error means the service is broken or
        misconfigured. It should be visible, not silently recorded as "no face".
        """
        mock_get.side_effect = _routes(snapshot=MagicMock(status_code=500))

        with pytest.raises(Exception):
            WindowsWebcamClient(IP, 8001).get_camera_jpeg()


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

    @patch("src.backend.clients.vision_tracking_client.requests.post")
    def test_jpeg_bytes_are_forwarded_unchanged(self, mock_post):
        """JPEG bytes from the webcam are sent to the vision service byte for byte.

        Why: decoding and re-encoding each frame cost CPU and added a second round of
        compression. The benchmark replays the webcam's own bytes, so production now
        sends exactly what the benchmark measures.
        """
        jpeg = cv2.imencode(".jpg", self.FRAME)[1].tobytes()
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"prediction": [1, 2]})

        VisionTrackingClient(IP, PORT).predict_por(jpeg)

        sent = mock_post.call_args.kwargs["files"]["file"][1].read()
        assert sent == jpeg
