from typing import List

from src.screen_region import ScreenRegion
from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class FocusAreaWorker:
    def __init__(
        self,
        windows_webcam_client: WindowsWebcamClient,
        vision_tracking_client: VisionTrackingClient,
        screen_region_list: List[ScreenRegion],
    ):
        # Dependency injection. focus_area_worker doesn't need to need to know about API implementations.
        self.vision_tracking_client = vision_tracking_client
        self.windows_webcam_client = windows_webcam_client

        self.screen_region_list = screen_region_list

    def predict_point_of_regard(self):
        image = self.windows_webcam_client.get_camera_input()
        prediction = self.vision_tracking_client.predict_por(image=image)
        return prediction[0], prediction[1]  # Returns x, y coordinates

    def get_focus_region(self, x, y):
        for region in self.screen_region_list:
            if region.is_point_in_region(x, y):
                return region
        return False
