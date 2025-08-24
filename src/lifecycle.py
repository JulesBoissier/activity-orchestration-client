import os
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from tabulate import tabulate

from src.focus_area_worker import FocusAreaWorker
from src.screen_region import MonitorUtility
from src.service_clients import VisionTrackingClient, WindowsWebcamClient
from src.user_interfaces.performance_monitoring import PerformanceMonitoringGUI
from src.user_interfaces.profile_creation import ProfileCreationGUI

load_dotenv()


class ProfileManager:
    def __init__(self, vision_tracking_client, windows_webcam_client, monitor):
        self.vision_tracking_client = vision_tracking_client
        self.windows_webcam_client = windows_webcam_client
        self.monitor = monitor

    def display_profiles(self):
        profiles = self.vision_tracking_client.list_profiles()["profiles"]

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

    def save_profile(self):
        """Save the current profile with the given name."""
        choice = input("Save profile? [Y/N]: ")

        if choice.lower() == "y":
            profile_name = input("Enter a profile name: ")
            self.vision_tracking_client.save_profile(profile_name)
        elif choice.lower() == "n":
            return
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")
            self.save_profile()

    def delete_profile(self, profile_id: int):
        self.vision_tracking_client.delete_profile(profile_id)

    def reset_profile(self, profile_id: int):
        self.vision_tracking_client.reset_profile(profile_id)

    def create_new_profile(self):
        positions = MonitorUtility.create_positions_list(self.monitor, 3)
        pcg = ProfileCreationGUI(
            self.monitor,
            positions,
            self.windows_webcam_client,
            self.vision_tracking_client,
        )
        pcg.run()
        self.save_profile()

    def select_or_create_profile(self):
        """Prompt user to select an existing profile or create a new one."""

        print(
            "Select a Profile ID from the following, or press enter to create a new profile:"
        )
        self.display_profiles()
        profile_id = input()

        if profile_id == "0" or not profile_id:
            self.create_new_profile()
        else:
            self.vision_tracking_client.load_profile(profile_id)


class ApplicationLifecycle:
    def __init__(self, monitor_index: int = 1, period: int = 2):
        """Initialize the application lifecycle with a given period (seconds)."""
        self.period = period

        # Initialize service clients
        self.vision_tracking_client = VisionTrackingClient(
            service_ip=os.getenv("VISION_TRACKING_SERVICE_IP", "127.0.0.1"),
            service_port=int(os.getenv("VISION_TRACKING_SERVICE_PORT", 8000)),
        )
        self.windows_webcam_client = WindowsWebcamClient(
            service_ip=os.getenv("WINDOWS_WEBCAM_SERVICE_IP", "127.0.0.1"),
            service_port=int(os.getenv("WINDOWS_WEBCAM_SERVICE_PORT", 8001)),
        )

        # Create screen regions
        self.monitor = MonitorUtility.select_monitor(monitor_index)
        self.regions = MonitorUtility.create_screen_region_list(self.monitor, 2)
        self.focus_area_worker = FocusAreaWorker(
            self.windows_webcam_client, self.vision_tracking_client, self.regions
        )

        self.profile_manager = ProfileManager(
            vision_tracking_client=self.vision_tracking_client,
            windows_webcam_client=self.windows_webcam_client,
            monitor=self.monitor,
        )

        self.now = datetime.now()

    def check_services(self, max_retries: int = None):
        """Ensure that both services are running before proceeding."""
        attempts = 0

        while True:
            vision_tracking_client_ok = self.vision_tracking_client.get_service_status()
            windows_webcam_client_ok = self.windows_webcam_client.get_service_status()

            if vision_tracking_client_ok and windows_webcam_client_ok:
                return True

            print(f"Global health-check failed. Re-trying in {self.period} seconds.")
            time.sleep(self.period)

            attempts += 1
            if max_retries is not None and attempts >= max_retries:
                raise Exception("Global Health Check Failed: Too many retries.")

    def run_performance_analysis(self):
        choice = input("Run performance analysis? [Y/N]: ")

        if choice.lower() == "y":
            nbr_of_samples = int(input("Number of samples to run analysis on:"))
            self._performance_analysis(nbr_of_samples=nbr_of_samples)
        elif choice.lower() == "n":
            return
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")
            self.run_performance_analysis()

    def _performance_analysis(self, nbr_of_samples):
        pmg = PerformanceMonitoringGUI(
            self.monitor,
            nbr_of_samples,
            self.windows_webcam_client,
            self.vision_tracking_client,
        )
        pmg.run()

    def monitor_focus(self):
        """Main loop to track and process user focus region."""
        while True:
            if datetime.now() - self.now > timedelta(seconds=self.period):
                self.check_services()  # Ensure connections are alive

                # Predict point of regard and determine focus region
                x, y = self.focus_area_worker.predict_point_of_regard()
                region = self.focus_area_worker.get_focus_region(x, y)
                print(region)

                # TODO: Integrate OS-Watchdog for retrieving OS state
                # TODO: Aggregate OS state + Region for focus info
                # TODO: Push focus info to DB

                self.now = datetime.now()  # Reset timer

    def run(self):
        """Start the application lifecycle."""
        self.check_services()
        self.profile_manager.select_or_create_profile()
        self.run_performance_analysis()
        self.monitor_focus()


# Run the lifecycle
if __name__ == "__main__":
    app = ApplicationLifecycle(period=2)
    app.run()
