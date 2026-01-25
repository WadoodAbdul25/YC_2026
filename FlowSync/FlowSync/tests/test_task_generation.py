import pytest
from FlowSync.task_generation import TaskGenerator

class TestTaskGenerator:
    def test_generate_task_success(self):
        email = {'subject': 'This is a task', 'due_date': '2023-10-01'}
        generator = TaskGenerator(email)
        assert generator.generate_task() is not None  # Logic to be implemented

    def test_is_actionable_no_subject(self):
        email = {'due_date': '2023-10-01'}
        generator = TaskGenerator(email)
        with pytest.raises(ValueError, match='Subject is required for task generation.'):
            generator._is_actionable()

