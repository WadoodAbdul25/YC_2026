import pytest
from FlowSync.pipeline import process_email

@pytest.fixture
def sample_email():
    return {"subject": "Task needed", "body": "This is an email that requires action.", "due_date": "2023-10-10"}


def test_process_email(sample_email):
    result = process_email(sample_email)
    assert result is not None
    assert 'tasks' in result
    assert 'response' in result
