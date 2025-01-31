import os

from dotenv import load_dotenv

from src.focus_area_worker import FocusAreaWorker
from src.screen_region import create_screen_region_list
from src.service_clients import VisionTrackingClient, WindowsWebcamClient

# Load environment variables from .env file
load_dotenv()

# Read values from environment variables with fallbacks
VISION_TRACKING_SERVICE_IP = os.getenv("VISION_TRACKING_SERVICE_IP", "127.0.0.1")
VISION_TRACKING_SERVICE_PORT = int(os.getenv("VISION_TRACKING_SERVICE_PORT", 8000))
WINDOWS_WEBCAM_SERVICE_IP = os.getenv("WINDOWS_WEBCAM_SERVICE_IP", "127.0.0.1")
WINDOWS_WEBCAM_SERVICE_PORT = int(os.getenv("WINDOWS_WEBCAM_SERVICE_PORT", 8001))


def predict():
    vtc = VisionTrackingClient(
        service_ip=VISION_TRACKING_SERVICE_IP, service_port=VISION_TRACKING_SERVICE_PORT
    )
    print(vtc.get_service_status())
    wwc = WindowsWebcamClient(
        service_ip=WINDOWS_WEBCAM_SERVICE_IP, service_port=WINDOWS_WEBCAM_SERVICE_PORT
    )
    print(wwc.get_service_status())

    image = wwc.get_camera_input()
    vtc.add_calibration_point(0, 0, image)

    regions = create_screen_region_list(2)

    faw = FocusAreaWorker(wwc, vtc, regions)

    x, y = faw.predict_point_of_regard()

    print(x, y)
    print("PREDICTION")
    print(faw.get_focus_region(x, y))
