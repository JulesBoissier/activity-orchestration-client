import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from src.focus_area_worker import FocusAreaWorker
from src.profile_creation_worker import ProfileCreationUnit
from src.screen_region import create_screen_region_list
from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class ApplicationLifecycle:
    def __init__(self, period: int = 2):
        """Initialize the application lifecycle with a given period (seconds)."""
        self.period = period

        # Initialize service clients
        self.vtc = VisionTrackingClient(
            service_ip=os.getenv("VISION_TRACKING_SERVICE_IP", "127.0.0.1"),
            service_port=int(os.getenv("VISION_TRACKING_SERVICE_PORT", 8000)),
        )
        self.wwc = WindowsWebcamClient(
            service_ip=os.getenv("WINDOWS_WEBCAM_SERVICE_IP", "127.0.0.1"),
            service_port=int(os.getenv("WINDOWS_WEBCAM_SERVICE_PORT", 8001)),
        )

        # Create screen regions
        self.regions = create_screen_region_list(2)
        self.faw = FocusAreaWorker(self.wwc, self.vtc, self.regions)

        self.now = datetime.now()

    def check_services(self):
        """Ensure that both services are running before proceeding."""
        if not (self.vtc.get_service_status() and self.wwc.get_service_status()):
            raise Exception(
                "Service connection error: VisionTrackingClient or WindowsWebcamClient is unavailable."
            )

    def select_or_create_profile(self):
        """Prompt user to select an existing profile or create a new one."""
        profile_id = input(
            f"Select a profile from one of {self.vtc.list_profiles()}, or choose 0 to create a new profile: \n"
        )
        if int(profile_id):  #! Bit ugly hack
            self.vtc.load_profile(profile_id)
        else:
            self.create_new_profile()

    def create_new_profile(self):
        """Handles new profile creation with calibration."""
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
        ]  # TODO: Make this dynamic with from screeninfo import get_monitors
        ProfileCreationUnit(positions, self.wwc, self.vtc)
        input("Profile creation complete. Press Enter to continue...")

    def monitor_focus(self):
        """Main loop to track and process user focus region."""
        while True:
            if datetime.now() - self.now > timedelta(seconds=self.period):
                self.check_services()  # Ensure connections are alive

                # Predict point of regard and determine focus region
                x, y = self.faw.predict_point_of_regard()
                region = self.faw.get_focus_region(x, y)
                print(region)

                # TODO: Integrate OS-Watchdog for retrieving OS state
                # TODO: Aggregate OS state + Region for focus info
                # TODO: Push focus info to DB

                self.now = datetime.now()  # Reset timer

    def run(self):
        """Start the application lifecycle."""
        self.check_services()
        self.select_or_create_profile()
        self.monitor_focus()


# Run the lifecycle
if __name__ == "__main__":
    app = ApplicationLifecycle(period=2)
    app.run()
