import random
from typing import Optional

from screeninfo import Monitor

from src.backend.clients.vision_tracking_client import VisionTrackingClient
from src.backend.clients.windows_webcam_client import WindowsWebcamClient
from src.backend.accuracy_scoring import score_accuracy_test
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
        # Use resolved monitor (Monitor or VirtualMonitor) for both positions and scoring
        area_width = int(self.monitor.width)
        area_height = int(self.monitor.height)

        self.positions = [
            (random.randint(0, area_width - 1), random.randint(0, area_height - 1))
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

        image = self.windows_webcam_client.get_camera_jpeg()
        prediction = None if image is None else self.vision_tracking_client.predict_por(image)
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
        report = score_accuracy_test(self.positions, self.predictions, self.monitor)

        def px(v):
            return "-" if v is None else f"{v:.0f}px"

        print("Accuracy test complete!")
        print(f"Dots: {report.samples}  no prediction (no face): {report.no_prediction}")
        print(f"Error: median {px(report.median_error_px)}  RMSE {px(report.rmse_px)}")
        if report.quadrant_accuracy is not None:
            print(
                f"Right quadrant: {report.quadrant_accuracy * 100:.1f}%  "
                f"off the monitor: {report.off_monitor}"
            )
        print("Quadrant confusion (rows: target TL TR BL BR; columns: predicted TL TR BL BR off):")
        for row in report.confusion:
            print("  " + " ".join(f"{v:3d}" for v in row))
