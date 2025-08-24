import tkinter as tk
from abc import ABC, abstractmethod
from tkinter import messagebox
from typing import List, Tuple

from screeninfo import Monitor

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class BaseGUITest(ABC):
    def __init__(
        self,
        monitor: Monitor,
        windows_webcam_client: WindowsWebcamClient,
        vision_tracking_client: VisionTrackingClient,
    ):
        self.monitor = monitor
        self.windows_webcam_client = windows_webcam_client
        self.vision_tracking_client = vision_tracking_client
        self.started_calibration = False

    def run(self):
        self.root = tk.Tk()
        self.root.geometry(
            f"{self.monitor.width}x{self.monitor.height}+{self.monitor.x}+{self.monitor.y}"
        )
        self.root.update()

        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<Return>", self.next_position)
        self.root.bind("<BackSpace>", self.prev_position)

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.show_start_message()
        self.root.mainloop()

    @abstractmethod
    def show_start_message(self):
        pass

    @abstractmethod
    def next_position(self, event=None):
        pass

    @abstractmethod
    def prev_position(self, event=None):
        pass

    def draw_element(self):
        self.canvas.delete("all")
        x, y = self.positions[self.index]
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="white", outline="")

    def exit_app(self, event=None):
        self.root.destroy()
