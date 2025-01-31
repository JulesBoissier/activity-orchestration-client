from dataclasses import dataclass
from typing import List

from screeninfo import get_monitors


@dataclass
class ScreenRegion:
    min_x: int
    max_x: int
    min_y: int
    max_y: int

    def is_point_in_region(self, x, y):
        if self.min_x <= x < self.max_x and self.min_y <= y < self.max_y:
            return True
        return False


def create_screen_region_list(resolution) -> List[ScreenRegion]:
    monitor = get_monitors()[0]

    section_width = monitor.width / resolution
    section_height = monitor.height / resolution

    screen_regions = []

    for i in range(resolution):
        for j in range(resolution):
            min_x = int(section_width * i)
            min_y = int(section_height * j)
            max_x = int(section_width * (i + 1))
            max_y = int(section_height * (j + 1))

            screen_regions.append(ScreenRegion(min_x, max_x, min_y, max_y))

    return screen_regions
