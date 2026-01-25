from .noise_filtering import NoiseFilter
from .task_generation import TaskGenerator
from .response_drafting import ResponseDrafting
from .performance_monitoring import PerformanceMonitoring

class EmailPipeline:
    def __init__(self):
        self.noise_filter = NoiseFilter()
        self.task_generator = TaskGenerator()
        self.response_drafting = ResponseDrafting()
        self.performance_monitoring = PerformanceMonitoring()

    def process_email(self, email_json):
        filtered_email = self.noise_filter.apply(email_json)
        tasks = self.task_generator.generate(filtered_email)
        response = self.response_drafting.draft_response(filtered_email)
        return tasks, response
