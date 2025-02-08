from tkinter import messagebox
from typing import List, Tuple

from screeninfo import Monitor

from src.service_clients import VisionTrackingClient, WindowsWebcamClient
from src.user_interfaces.gui_base_class import BaseGUITest


class ProfileCreationGUI(BaseGUITest):
    def __init__(
        self,
        monitor: Monitor,
        positions: List[Tuple[int, int]],
        wwc: WindowsWebcamClient,
        vtc: VisionTrackingClient,
    ):
        super().__init__(monitor, wwc, vtc)
        self.positions = positions
        self.images = []

    def show_start_message(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            self.root.winfo_screenheight() // 2,
            text="Follow the white circle with your gaze and press ENTER to lock-in a calibration point.\nPress BACKSPACE to go back.\nPress ENTER to start.",
            fill="white",
            font=("Arial", 24, "bold"),
            justify="center",
        )

    def next_position(self, event=None):
        if not self.started_calibration:
            self.started_calibration = True
            self.index = 0
            self.draw_element()
            return

        image = self.wwc.get_camera_input()
        self.images.append(image)

        if self.index < len(self.positions) - 1:
            self.index += 1
            self.draw_element()
        else:
            self.send_data()
            self.exit_app()

    def prev_position(self, event=None):
        if self.index > 0:
            self.images.pop(-1)
            self.index -= 1
            self.draw_element()

    def send_data(self):
        for position, image in zip(self.positions, self.images):
            self.vtc.add_calibration_point(position[0], position[1], image)
        messagebox.showinfo("Info", "Data Sent Successfully!")
