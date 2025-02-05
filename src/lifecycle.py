import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from tabulate import tabulate

from src.focus_area_worker import FocusAreaWorker
from src.screen_region import MonitorUtility
from src.service_clients import VisionTrackingClient, WindowsWebcamClient
from src.user_interfaces.performance_monitoring import PerformanceMonitoringGUI
from src.user_interfaces.profile_creation import ProfileCreationGUI

load_dotenv()


class ApplicationLifecycle:
    def __init__(self, monitor_index: int = 1, period: int = 2):
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
        self.monitor = MonitorUtility.select_monitor(monitor_index)
        self.regions = MonitorUtility.create_screen_region_list(self.monitor, 2)
        self.faw = FocusAreaWorker(self.wwc, self.vtc, self.regions)

        self.now = datetime.now()

    def check_services(self):
        """Ensure that both services are running before proceeding."""
        if not (self.vtc.get_service_status() and self.wwc.get_service_status()):
            raise Exception(
                "Service connection error: VisionTrackingClient or WindowsWebcamClient is unavailable."
            )

    def _display_profiles(self):
        profiles = self.vtc.list_profiles()["profiles"]

        if not profiles:
            print("No profiles found.")
            return None

        # Convert profiles into a table format
        table = [
            [profile["id"], profile["profile_name"], profile["updated_at"]]
            for profile in profiles
        ]
        print(
            tabulate(
                table, headers=["ID", "Profile Name", "Last Updated"], tablefmt="grid"
            )
        )

        return profiles  # Return the list for further use if needed

    def select_or_create_profile(self):
        """Prompt user to select an existing profile or create a new one."""

        print(
            "Select a Profile ID from the following, or press enter to create a new profile:"
        )
        self._display_profiles()
        profile_id = input()

        if profile_id == "0" or not profile_id:
            self.create_new_profile()
        else:
            self.vtc.load_profile(profile_id)

    def create_new_profile(self):
        """Handles new profile creation with calibration."""

        positions = MonitorUtility.create_positions_list(self.monitor, 3)
        ProfileCreationGUI(self.monitor, positions, self.wwc, self.vtc)

    def run_performance_analysis(self):
        choice = input("Run performance analysis? [Y/N]: ")

        if choice.lower() == "y":
            self._performance_analysis()
        elif choice.lower() == "n":
            return
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")
            self.run_performance_analysis()

    def _performance_analysis(self):
        PerformanceMonitoringGUI(self.monitor, 5, self.wwc, self.vtc)

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
        self.run_performance_analysis()
        self.monitor_focus()


# Run the lifecycle
if __name__ == "__main__":
    app = ApplicationLifecycle(period=2)
    app.run()
