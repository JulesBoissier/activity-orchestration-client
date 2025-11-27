from abc import ABC

import requests


class ServiceClient(ABC):
    def __init__(self, service_ip, service_port):
        self.root_url = f"http://{service_ip}:{service_port}"
        self.timeout = 1

    def get_service_status(self):
        try:
            requests.get(self.root_url + "/health", timeout=self.timeout)
            return True
        except requests.ConnectionError:
            print(
                f"{self.__class__.__name__} is down: Connection Error for host at {self.root_url}."
            )
            return False
        except requests.Timeout:
            print(
                f"{self.__class__.__name__} is down: Timeout reached after {self.timeout} seconds for host at {self.root_url}."
            )
            return False
