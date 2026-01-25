import json
from datetime import datetime, timedelta

class TaskGenerator:
    def __init__(self, email_data):
        self.email_data = email_data

    def generate_tasks(self):
        tasks = []
        for email in self.email_data:
            if self._is_actionable(email):
                task = self._format_task(email)
                tasks.append(task)
        return tasks

    def _is_actionable(self, email):
        # Logic to determine if the email requires an action
        return 'task' in email['subject'].lower()

    def _format_task(self, email):
        return {
            'title': email['subject'],
            'description': email.get('body', ''),
            'due_date': self._parse_due_date(email.get('due_date')),
        }

    @staticmethod
    def _parse_due_date(due_date_str):
        if due_date_str:
            return datetime.strptime(due_date_str, '%Y-%m-%d')
        return datetime.now() + timedelta(days=7)  # Default to a week from now
