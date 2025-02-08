import random
from tkinter import messagebox

import numpy as np
from screeninfo import Monitor

from src.service_clients import VisionTrackingClient, WindowsWebcamClient
from src.user_interfaces.gui_base_class import BaseGUITest


class PerformanceMonitoringGUI(BaseGUITest):
    def __init__(
        self,
        monitor: Monitor,
        nbr_of_points: int,
        wwc: WindowsWebcamClient,
        vtc: VisionTrackingClient,
    ):
        super().__init__(monitor, wwc, vtc)

        self.positions = [
            (random.randint(0, monitor.width), random.randint(0, monitor.height))
            for _ in range(nbr_of_points)
        ]
        self.predictions = []

    def show_start_message(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            self.root.winfo_screenheight() // 2,
            text="Follow the white circle with your gaze and press ENTER.\nPress BACKSPACE to go back.\nPress ENTER to start.",
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
        prediction = self.vtc.predict_por(image)
        self.predictions.append(prediction)

        if self.index < len(self.positions) - 1:
            self.index += 1
            self.draw_element()
        else:
            self.report_results()
            self.exit_app()

    def prev_position(self, event=None):
        if self.index > 0:
            self.predictions.pop(-1)
            self.index -= 1
            self.draw_element()

    def report_results(self):
        from src.screen_region import MonitorUtility

        # Create screen regions based on the monitor
        regions = MonitorUtility.create_screen_region_list(self.monitor, resolution=2)

        # Map positions and predictions to their corresponding regions
        target_screen_regions = [
            region
            for position in self.positions
            for region in regions
            if region.is_point_in_region(position[0], position[1])
        ]

        predict_screen_regions = [
            region
            for prediction in self.predictions
            for region in regions
            if region.is_point_in_region(prediction[0], prediction[1])
        ]

        # Compare target and predicted regions
        results = [
            (target, prediction, target == prediction)
            for target, prediction in zip(target_screen_regions, predict_screen_regions)
        ]

        # Handle the results (e.g., logging or returning for further processing)
        for target, prediction, is_accurate in results:
            if is_accurate:
                print(target, prediction)
                pass

        if len(self.predictions) == len(self.positions):
            errors = np.array(self.predictions) - np.array(self.positions)
            rmse = np.sqrt(np.mean(errors**2))
            messagebox.showinfo(
                "Info", f"Performance monitoring complete! RMSE: {rmse:.2f}"
            )
        else:
            messagebox.showinfo("Info", "Performance monitoring complete!")
