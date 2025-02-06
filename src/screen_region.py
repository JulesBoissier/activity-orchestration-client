from dataclasses import dataclass
from typing import List

from screeninfo import Monitor, get_monitors


@dataclass
class ScreenRegion:
    min_x: int
    max_x: int
    min_y: int
    max_y: int

    def is_point_in_region(self, x, y):
        try:
            if self.min_x <= x < self.max_x and self.min_y <= y < self.max_y:
                return True
            return False
        except TypeError:
            print("Invalid coordinates provided.")
            return False


class MonitorUtility:
    @staticmethod
    def select_monitor(display_index) -> Monitor:
        """Select a monitor based on index (1 for primary, 2 for secondary, etc.)"""

        monitors = get_monitors()
        num_displays = len(monitors)

        if display_index < 1 or display_index > num_displays:
            print(
                f"Invalid display index: {display_index}. Defaulting to primary display."
            )
            display_index = (
                1  # Default to the primary display if the index is out of range
            )

        monitor = monitors[display_index - 1]  # Adjust index
        return monitor

    @staticmethod
    def create_screen_region_list(monitor, resolution: int):
        """Creates a list of screen regions with correct local offsets, matching position coordinates."""
        section_width = monitor.width / resolution
        section_height = monitor.height / resolution

        screen_region_list = [
            ScreenRegion(
                int(section_width * i),  # Adjust min_x with monitor.x
                int(section_width * (i + 1)),  # Adjust max_x with monitor.x
                int(section_height * j),  # Adjust min_y with monitor.y
                int(section_height * (j + 1)),  # Adjust max_y with monitor.y
            )
            for j in range(resolution)
            for i in range(resolution)
        ]

        return screen_region_list

    @staticmethod
    def create_positions_list(monitor, resolution: int):
        # Define NxN grid spacing
        step_x = monitor.width // (resolution - 1)  # X spacing
        step_y = monitor.height // (resolution - 1)  # Y spacing

        # Generate NxN grid of points
        positions = [
            (step_x * col, step_y * row)
            for row in range(resolution)
            for col in range(resolution)
        ]
        return positions
