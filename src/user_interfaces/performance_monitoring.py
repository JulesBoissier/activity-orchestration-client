import random
import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class PerformanceMonitoringGUI:
    def __init__(
        self,
        monitor,
        nbr_of_points: int,
        wwc: WindowsWebcamClient,
        vtc: VisionTrackingClient,
    ):
        self.started_calibration = False
        self.wwc = wwc
        self.vtc = vtc
        self.positions = [
            (random.randint(0, monitor.width), random.randint(0, monitor.height))
            for _ in range(nbr_of_points)
        ]
        self.predictions = []
        self.start_tk(monitor=monitor)

    def start_tk(self, monitor):
        self.root = tk.Tk()

        self.root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        self.root.update()

        # Apply fullscreen mode
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<Return>", self.next_position)
        self.root.bind("<BackSpace>", self.prev_position)

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.show_start_message()
        self.root.mainloop()  # Run main event loop inside the class

    def show_start_message(self):
        """Displays a text box with instructions."""
        self.canvas.delete("all")
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            self.root.winfo_screenheight() // 2,
            text="Follow the white circle with your gaze and press ENTER. \nPress BACKSPACE to go back. \nPress ENTER to start.",
            fill="white",
            font=("Arial", 24, "bold"),
            justify="center",
        )

    def draw_element(self):
        """Draws the shape at the current position, adjusting for monitor position."""
        self.canvas.delete("all")  # Clear previous elements
        x, y = self.positions[self.index]
        print(x, y)

        # Convert from global screen space to Tkinter's local window space
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="white", outline="")

    def next_position(self, event=None):
        """Move to the next position."""
        if not self.started_calibration:  # This gets passed the initial message.
            self.started_calibration = True
            self.index = 0
            self.draw_element()
            return

        image = self.wwc.get_camera_input()  # Capture an image of the face
        prediction = self.vtc.predict_por(image)
        self.predictions.append(prediction)

        print(prediction)

        if (
            self.index < len(self.positions) - 1
        ):  # While there are positions left, move to next
            self.index += 1
            self.draw_element()
        else:
            self.report_results()
            self.exit_app()

    def prev_position(self):
        pass

    def report_results(self):
        pass

    def exit_app(self, event=None):
        """Exit the application."""
        self.root.destroy()
