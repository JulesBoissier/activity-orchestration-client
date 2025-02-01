import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from src.focus_area_worker import FocusAreaWorker
from src.profile_creation_worker import ProfileCreationUnit
from src.screen_region import create_screen_region_list
from src.service_clients import VisionTrackingClient, WindowsWebcamClient

# Load environment variables from .env file
load_dotenv()

# Read values from environment variables with fallbacks
VISION_TRACKING_SERVICE_IP = os.getenv("VISION_TRACKING_SERVICE_IP", "127.0.0.1")
VISION_TRACKING_SERVICE_PORT = int(os.getenv("VISION_TRACKING_SERVICE_PORT", 8000))
WINDOWS_WEBCAM_SERVICE_IP = os.getenv("WINDOWS_WEBCAM_SERVICE_IP", "127.0.0.1")
WINDOWS_WEBCAM_SERVICE_PORT = int(os.getenv("WINDOWS_WEBCAM_SERVICE_PORT", 8001))


def lifecycle(period: int = 2):
    vtc = VisionTrackingClient(
        service_ip=VISION_TRACKING_SERVICE_IP, service_port=VISION_TRACKING_SERVICE_PORT
    )
    wwc = WindowsWebcamClient(
        service_ip=WINDOWS_WEBCAM_SERVICE_IP, service_port=WINDOWS_WEBCAM_SERVICE_PORT
    )

    regions = create_screen_region_list(2)
    faw = FocusAreaWorker(wwc, vtc, regions)

    if vtc.get_service_status() and wwc.get_service_status():
        profile_id = input(
            f"Select a profile from one of {vtc.list_profiles()}, or choose 0 to create a new profile: \n"
        )
        if int(profile_id):
            vtc.load_profile(profile_id)
        else:
            positions = [
                (0, 0),
                (960, 0),
                (1920, 0),
                (0, 540),
                (960, 540),
                (1920, 540),
                (0, 1080),
                (960, 1080),
                (1920, 1080),
            ]

            ProfileCreationUnit(positions, wwc, vtc)
            input("Continue...")
    else:
        raise Exception

    now = datetime.now()
    while True:
        if datetime.now() - now > timedelta(seconds=period):
            if vtc.get_service_status() and wwc.get_service_status():
                # Check that connections are alive.
                #! If connection has dropped, vtc needs to reload profile?
                # ? Does VTC need a "curr_profile" method? For now just load the profile each time?

                # TODO: OS-Watchdog to retrieve OS-State

                x, y = faw.predict_point_of_regard()
                region = faw.get_focus_region(x, y)
                print(region)

                # TODO: Aggregator takes OS-State + Region and returns Focus Info
                # TODO: Focus Info is pushed to DB
                now = datetime.now()

            else:
                raise Exception
