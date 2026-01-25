class NoiseFilter:
    def __init__(self, email):
        self.email = email

    def filter_noise(self):
        if not isinstance(self.email, dict):
            raise ValueError('Email must be a dictionary.')
        subject_keywords = ['urgent', 'meeting', 'follow up']
        return any(keyword in self.email.get('subject', '').lower() for keyword in subject_keywords)

