from tabulate import tabulate

from src.backend.screen_region import MonitorUtility
from src.backend.user_interfaces.profile_creation import ProfileCreationGUI


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
