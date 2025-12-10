import random
from typing import Optional

import numpy as np
from screeninfo import Monitor

from src.backend.clients.vision_tracking_client import VisionTrackingClient
from src.backend.clients.windows_webcam_client import WindowsWebcamClient
from src.backend.screen_region import MonitorUtility
from src.backend.user_interfaces.gui_base_class import BaseGUITest


class PerformanceMonitoringGUI(BaseGUITest):
    def __init__(
        self,
        monitor: Optional[Monitor],
        nbr_of_points: int,
        windows_webcam_client: WindowsWebcamClient,
        vision_tracking_client: VisionTrackingClient,
    ):
        super().__init__(monitor, windows_webcam_client, vision_tracking_client)
        # Use resolved monitor (Monitor or VirtualMonitor) for both positions and confusion matrix
        area_width = int(self.monitor.width)
        area_height = int(self.monitor.height)
        self._confusion_monitor = self.monitor

        self.positions = [
            (random.randint(0, area_width), random.randint(0, area_height))
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

        image = self.windows_webcam_client.get_camera_input()
        prediction = self.vision_tracking_client.predict_por(image)
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

    def _calculate_rmse(self):
        if len(self.predictions) == len(self.positions):
            errors = np.array(self.predictions) - np.array(self.positions)
            rmse = np.sqrt(np.mean(errors**2))
            return rmse
        else:
            return None

    def _calculate_confusion_matrix(self):
        # Define the four screen regions
        screen_regions = MonitorUtility.create_screen_region_list(
            self._confusion_monitor, resolution=2
        )
        # Initialize a confusion matrix with zeros (4x4 for 4 regions)
        confusion_matrix = np.zeros(
            (len(screen_regions), len(screen_regions)), dtype=int
        )

        # Map positions and predictions to their corresponding regions
        target_screen_regions = [
            MonitorUtility.find_screen_region(
                position[0], position[1], self._confusion_monitor, 2
            )
            for position in self.positions
        ]

        predict_screen_regions = [
            MonitorUtility.find_screen_region(
                prediction[0], prediction[1], self._confusion_monitor, 2
            )
            for prediction in self.predictions
        ]

        # Populate the confusion matrix
        print("Target screen regions:")
        print(target_screen_regions)
        print("Predict screen regions:")
        print(predict_screen_regions)
        for target, prediction in zip(target_screen_regions, predict_screen_regions):
            target_idx = screen_regions.index(target)
            prediction_idx = screen_regions.index(prediction)
            confusion_matrix[target_idx, prediction_idx] += 1

        # Calculate accuracy
        total_predictions = np.sum(confusion_matrix)
        correct_predictions = np.trace(confusion_matrix)
        accuracy = (
            correct_predictions / total_predictions if total_predictions > 0 else 0
        )

        return confusion_matrix, accuracy

    def report_results(self):
        # Calculate RMSE
        rmse = self._calculate_rmse()
        confusion_matrix, accuracy = self._calculate_confusion_matrix()

        print("Performance monitoring complete!")
        if rmse is not None:
            print(f"RMSE: {rmse:.2f}")
        else:
            print("No RMSE calculated due to mismatched data.")

        # Calculate Confusion Matrix and Accuracy
        print("Confusion Matrix:")
        print(confusion_matrix)
        print(f"Accuracy: {accuracy * 100:.2f}%")
