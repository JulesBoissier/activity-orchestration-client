import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class ProfileCreationUnit:
    def __init__(
        self,
        monitor,
        positions: List[Tuple[int, int]],
        wwc: WindowsWebcamClient,
        vtc: VisionTrackingClient,
    ):
        self.root = tk.Tk()

        self.root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")

        # self.root.geometry(f"1920x1080+0+0")
        self.root.update()

        # Apply fullscreen mode
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<Return>", self.next_position)
        self.root.bind("<BackSpace>", self.prev_position)

        self.positions = positions
        self.started_calibration = False
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.wwc = wwc
        self.vtc = vtc
        self.images = []
        self.show_start_message()

        self.root.mainloop()  # Run main event loop inside the class

    def show_start_message(self):
        """Displays a text box with instructions."""
        self.canvas.delete("all")
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            self.root.winfo_screenheight() // 2,
            text="Follow the white circle with your gaze and pres ENTER to lock-in a calibration point. \nPress BACKSPACE to go back. \nPress ENTER to start.",
            fill="white",
            font=("Arial", 24, "bold"),
            justify="center",
        )

    def draw_element(self):
        """Draws the shape at the current position."""
        self.canvas.delete("all")  # Clear previous elements
        x, y = self.positions[self.index]

        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="white", outline="")

    def next_position(self, event=None):
        """Move to the next position."""
        if not self.started_calibration:  # This gets passed the initial message.
            self.started_calibration = True
            self.index = 0
            self.draw_element()
            return

        image = self.wwc.get_camera_input()  # Capture an image of the face
        self.images.append(image)

        if (
            self.index < len(self.positions) - 1
        ):  # While there are positions left, move to next
            self.index += 1
            self.draw_element()
        else:
            self.send_data()
            self.exit_app()

    def prev_position(self, event=None):
        """Move back to the previous position."""
        if self.index > 0:
            self.images.pop(-1)  # Removes the last image from the list.

            self.index -= 1
            self.draw_element()

    def send_data(self):
        """Simulate sending data at the end."""

        for position, image in zip(self.positions, self.images):
            print(f"Adding an image to cal_points")
            self.vtc.add_calibration_point(position[0], position[1], image)

        messagebox.showinfo("Info", "Data Sent Successfully!")

    def exit_app(self, event=None):
        """Exit the application."""
        self.root.destroy()
