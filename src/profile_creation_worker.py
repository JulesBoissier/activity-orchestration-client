import tkinter as tk
from tkinter import messagebox

from src.service_clients import VisionTrackingClient, WindowsWebcamClient


class ProfileCreationUnit:
    def __init__(self, positions, wwc: WindowsWebcamClient, vtc: VisionTrackingClient):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<Return>", self.next_position)
        self.root.bind("<BackSpace>", self.prev_position)

        self.positions = positions
        self.index = -1
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.wwc = wwc
        self.vtc = vtc
        self.images = []
        self.root.mainloop()  # Run main event loop inside the class

    def draw_element(self):
        """Draws the shape at the current position."""
        self.canvas.delete("all")  # Clear previous elements
        x, y = self.positions[self.index]

        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="white", outline="")

    def next_position(self, event=None):
        """Move to the next position."""
        if self.index < len(self.positions) - 1:
            image = self.wwc.get_camera_input()  # Capture an image of the face
            self.images.append(image)

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
