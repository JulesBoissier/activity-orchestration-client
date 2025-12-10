from dataclasses import dataclass
from typing import List, Optional, Union

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
    @dataclass
    class VirtualMonitor:
        x: int
        y: int
        width: int
        height: int

    @staticmethod
    def select_monitor(
        display_index: Optional[int],
    ) -> Union[Monitor, "MonitorUtility.VirtualMonitor"]:
        """
        Select a monitor based on index (1 for primary, 2 for secondary, etc.)
        - If display_index is None, return a VirtualMonitor covering all displays.
        """

        monitors = get_monitors()
        num_displays = len(monitors)

        if display_index is None:
            min_x = min(m.x for m in monitors)
            min_y = min(m.y for m in monitors)
            max_x = max(m.x + m.width for m in monitors)
            max_y = max(m.y + m.height for m in monitors)
            return MonitorUtility.VirtualMonitor(
                x=int(min_x),
                y=int(min_y),
                width=int(max_x - min_x),
                height=int(max_y - min_y),
            )

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
    def find_screen_region(x, y, monitor, resolution):
        regions = MonitorUtility.create_screen_region_list(monitor, resolution)
        for region in regions:
            if region.is_point_in_region(x, y):
                return region

    @staticmethod
    def create_positions_list(
        monitor: Union[Monitor, "MonitorUtility.VirtualMonitor"], resolution: int
    ):
        """
        Create a list of positions forming a resolution x resolution grid.
        - If a Monitor is provided, positions are in that monitor's local coordinates.
        - If a VirtualMonitor is provided, positions cover EACH real monitor and are
          placed in virtual desktop space (offset by the top-left of the leftmost/topmost monitor).
        """
        if resolution < 2:
            # Fallback to a single point at the origin of each target area
            def gen_points(w, h, ox=0, oy=0):
                return [(ox, oy)]

        else:

            def gen_points(w, h, ox=0, oy=0):
                step_x = w // (resolution - 1)
                step_y = h // (resolution - 1)
                return [
                    (ox + step_x * col, oy + step_y * row)
                    for row in range(resolution)
                    for col in range(resolution)
                ]

        if isinstance(monitor, MonitorUtility.VirtualMonitor):
            monitors = get_monitors()
            if not monitors:
                return []
            min_x = min(m.x for m in monitors)
            min_y = min(m.y for m in monitors)
            positions: List[tuple[int, int]] = []
            for m in monitors:
                offset_x = int(m.x - min_x)
                offset_y = int(m.y - min_y)
                positions.extend(
                    gen_points(int(m.width), int(m.height), offset_x, offset_y)
                )
            return positions
        else:
            return gen_points(int(monitor.width), int(monitor.height))
