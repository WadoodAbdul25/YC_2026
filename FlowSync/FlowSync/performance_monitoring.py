import time
import logging

class PerformanceMonitoring:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def profile(self, func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            self.logger.info(f"{func.__name__} took {end_time - start_time} seconds")
            return result
        return wrapper

    def monitor_api_performance(self, api_name, response_time):
        self.logger.info(f"API {api_name} responded in {response_time:.2f} seconds")
