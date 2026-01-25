import json

class EmailParser:
    def parse(self, email_json):
        email_data = json.loads(email_json)
        tasks = self.extract_tasks(email_data)
        return tasks

    def extract_tasks(self, email_data):
        tasks = []  # Extract tasks based on email content
        return tasks
