import json

class NoiseFilter:
    def __init__(self, irrelevant_keywords):
        self.irrelevant_keywords = irrelevant_keywords

    def filter_emails(self, emails):
        filtered_emails = []
        for email in emails:
            if not any(keyword.lower() in email['subject'].lower() for keyword in self.irrelevant_keywords):
                filtered_emails.append(email)
        return filtered_emails

if __name__ == '__main__':
    sample_emails = [
        {"subject": "Meeting Scheduled", "body": "Upcoming project meeting details..."},
        {"subject": "Spam Email", "body": "Buy now!"}
    ]
    filterer = NoiseFilter(["spam", "buy"])
    print(filterer.filter_emails(sample_emails))