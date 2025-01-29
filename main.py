import os

from dotenv import load_dotenv

from src.health_check import HealthCheck

# Load environment variables from .env file
load_dotenv()

# Read values from environment variables with fallbacks
VISION_TRACKING_SERVICE_IP = os.getenv("VISION_TRACKING_SERVICE_IP", "127.0.0.1")
VISION_TRACKING_SERVICE_PORT = int(os.getenv("VISION_TRACKING_SERVICE_PORT", 8000))
WINDOWS_WEBCAM_SERVICE_IP = os.getenv("WINDOWS_WEBCAM_SERVICE_IP", "127.0.0.1")
WINDOWS_WEBCAM_SERVICE_PORT = int(os.getenv("WINDOWS_WEBCAM_SERVICE_PORT", 8001))


if __name__ == "__main__":
    health_check = HealthCheck(
        VISION_TRACKING_SERVICE_IP,
        VISION_TRACKING_SERVICE_PORT,
        WINDOWS_WEBCAM_SERVICE_IP,
        WINDOWS_WEBCAM_SERVICE_PORT,
    )
    health_check.check_services()
