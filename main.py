from src.health_check import HealthCheck

VISION_TRACKING_SERVICE_PORT = 8000
WINDOWS_WEBCAM_SERVICE_PORT = 8001

if __name__ == "__main__":
    health_check = HealthCheck(VISION_TRACKING_SERVICE_PORT, WINDOWS_WEBCAM_SERVICE_PORT)
    health_check.check_services()