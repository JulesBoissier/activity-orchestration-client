import unittest
from unittest.mock import MagicMock, patch

from src.lifecycle import ApplicationLifecycle


class TestApplicationLifecycleHealthCheck(unittest.TestCase):
    MAX_RETRIES = 3

    def setUp(self):
        # Patching to run in headless environments.
        dummy_monitor = MagicMock()
        with patch(
            "src.screen_region.MonitorUtility.select_monitor",
            return_value=dummy_monitor,
        ):
            self.app = ApplicationLifecycle(period=0.1)

    @patch(
        "src.clients.vision_tracking_client.VisionTrackingClient.get_service_status",
        return_value=True,
    )
    @patch(
        "src.clients.windows_webcam_client.WindowsWebcamClient.get_service_status",
        return_value=True,
    )
    @patch(
        "src.clients.system_watchdog_client.SystemWatchdogClient.get_service_status",
        return_value=True,
    )
    def test_positive_global_health(
        self, windows_webcam_client_get, vision_tracking_client_get, watchdog_get
    ):
        self.app.check_services()

        windows_webcam_client_get.assert_called_once()
        vision_tracking_client_get.assert_called_once()
        watchdog_get.assert_called_once()

    @patch(
        "src.clients.vision_tracking_client.VisionTrackingClient.get_service_status",
        return_value=False,
    )
    @patch(
        "src.clients.windows_webcam_client.WindowsWebcamClient.get_service_status",
        return_value=False,
    )
    @patch(
        "src.clients.system_watchdog_client.SystemWatchdogClient.get_service_status",
        return_value=False,
    )
    def test_negative_global_health(
        self, windows_webcam_client_get, vision_tracking_client_get, watchdog_get
    ):
        with self.assertRaises(Exception) as context:
            self.app.check_services(max_retries=self.MAX_RETRIES)

        self.assertEqual(windows_webcam_client_get.call_count, self.MAX_RETRIES)
        self.assertEqual(vision_tracking_client_get.call_count, self.MAX_RETRIES)
        self.assertEqual(watchdog_get.call_count, self.MAX_RETRIES)
