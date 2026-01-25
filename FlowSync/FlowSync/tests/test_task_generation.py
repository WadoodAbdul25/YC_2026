import pytest
from datetime import datetime  # Added missing import
from FlowSync.task_generation import TaskGenerator

@pytest.fixture
def sample_email_data():
    return [{'body': 'Finish the quarterly report', 'due_date': '2023-10-30', 'subject': 'Task: Complete report'}, {'body': 'Don’t forget the meeting today', 'due_date': None, 'subject': 'Meeting reminder'}]

def test_format_task_with_no_due_date(sample_email_data):
    email_without_due = {'subject': 'Task: Buy groceries', 'body': 'Milk, Eggs, Bread', 'due_date': None}
    generator = TaskGenerator([email_without_due])
    task = generator.generate_tasks()
    assert task[0]['due_date'] is not None
    assert task[0]['due_date'] > datetime.now()  # Should default to a week from now