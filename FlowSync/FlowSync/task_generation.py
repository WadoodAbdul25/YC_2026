from datetime import datetime

class TaskGenerator:
    def __init__(self, email):
        self.email = email

    def _is_actionable(self):
        subject = self.email.get('subject', '').lower()
        if not subject:
            raise ValueError('Subject is required for task generation.')
        return 'task' in subject

    def generate_task(self):
        if not self._is_actionable():
            raise ValueError('Email is not actionable. No task generated.')
        due_date = self.email.get('due_date')
        if due_date and not isinstance(due_date, str):
            raise ValueError('Due date must be a string.')
        # Implementation for task generation goes here

