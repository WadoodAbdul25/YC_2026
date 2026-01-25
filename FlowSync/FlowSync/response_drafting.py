import os

class ResponseDrafting:
    def __init__(self):
        self.api_keys = self.get_api_keys()

    def get_api_keys(self):
        # Ensure the get_api_keys method is implemented and callable here.
        # Implement your logic to retrieve OpenAI and Cerebras API keys
        return {
            'openai_key': os.getenv('OPENAI_API_KEY'),
            'cerebras_key': os.getenv('CEREBRAS_API_KEY')
        }
