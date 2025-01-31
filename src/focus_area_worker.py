from typing import List

from src.screen_region import ScreenRegion
from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class FocusAreaWorker:
    def __init__(
        self,
        wws_client: WindowsWebcamClient,
        vts_client: VisionTrackingClient,
        screen_region_list: List[ScreenRegion],
    ):
        # Dependency injection. FAW doesn't need to need to know about API implementations.
        self.vts_client = vts_client
        self.wws_client = wws_client

        self.screen_region_list = screen_region_list

    def predict_point_of_regard(self):
        image = self.wws_client.get_camera_input()
        predictions = self.vts_client.predict_por(image=image)
        return predictions

    def get_focus_region(self, x, y):
        for region in self.screen_region_list:
            if region.is_point_in_region(x, y):
                return region
        return False
