import pytest
from FlowSync.noise_filtering import NoiseFilter

@pytest.fixture
def noise_filter():
    return NoiseFilter(irrelevant_keywords=["spam", "buy"])

def test_filter_emails(noise_filter):
    emails = [
        {"subject": "Meeting Scheduled", "body": "Upcoming project meeting details..."},
        {"subject": "Spam Email", "body": "Buy now!"}
    ]
    filtered = noise_filter.filter_emails(emails)
    assert len(filtered) == 1
    assert filtered[0]["subject"] == "Meeting Scheduled"