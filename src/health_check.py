import requests


class HealthCheck:
    def __init__(self, vts_ip, vts_port, wws_ip, wws_port):
        self.vts_url = f"http://{vts_ip}:{vts_port}/health"
        self.wws_url = f"http://{wws_ip}:{wws_port}/health"

        self.vts_status = False
        self.wws_status = False

    def _check_service(self, url):
        try:
            response = requests.get(url, timeout=5)
            print(f"Service at {url} is running.")
            return True
        except requests.ConnectionError:
            print(f"Service at {url} is down.")
            return False
        except requests.Timeout:
            print(f"Service at {url} is down.")
            return False

    def check_services(self):
        self.vts_status = self._check_service(self.vts_url)
        self.wws_status = self._check_service(self.wws_url)
