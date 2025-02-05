import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class PerformanceMonitoringGUI:
    def __init__(
        self,
        monitor,
        # positions: List[Tuple[int, int]],
        wwc: WindowsWebcamClient,
        vtc: VisionTrackingClient,
    ):
        pass

    def show_start_message(self):
        pass

    def draw_element(self):
        pass

    def next_position(self, event=None):
        pass

    def prev_position(self, event=None):
        """Move back to the previous position."""
        if self.index > 0:
            self.images.pop(-1)  # Removes the last image from the list.

            self.index -= 1
            self.draw_element()
