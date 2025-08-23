import unittest
from unittest.mock import MagicMock, patch

import requests

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class ServiceClientTestsMixin:
    CLIENT_CLASS = None
    IP = "127.0.0.1"
    PORT = 8000

    def setUp(self):
        assert self.CLIENT_CLASS is not None
        self.client = self.CLIENT_CLASS(self.IP, self.PORT)

    @patch("src.service_clients.requests.get")
    def test_positive_status(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        self.assertTrue(self.client.get_service_status())
        mock_get.assert_called_once_with(
            f"http://{self.IP}:{self.PORT}/health", timeout=1
        )

    @patch("src.service_clients.requests.get")
    def test_negative_status_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError()
        self.assertFalse(self.client.get_service_status())
        mock_get.assert_called_once_with(
            f"http://{self.IP}:{self.PORT}/health", timeout=1
        )

    @patch("src.service_clients.requests.get")
    def test_negative_status_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        self.assertFalse(self.client.get_service_status())
        mock_get.assert_called_once_with(
            f"http://{self.IP}:{self.PORT}/health", timeout=1
        )


class TestWindowsWebcamClient(ServiceClientTestsMixin, unittest.TestCase):
    CLIENT_CLASS = WindowsWebcamClient


class TestVisionTrackingClient(ServiceClientTestsMixin, unittest.TestCase):
    CLIENT_CLASS = VisionTrackingClient
