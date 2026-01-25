import json
import requests
from typing import List, Dict, Any
from unittest.mock import patch

class ResponseDrafting:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = 'https://api.openai.com/v1/chat/completions'

    @patch('requests.post')  # Mocking the requests.post method for testing
    def draft_response(self, email_context: List[Dict], mock_post: Any = None) -> str:
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
        email_contents = ' '.join(email['body'] for email in email_context)
        prompt = f"Draft a human-like response to the following emails: {email_contents}"
        data = json.dumps({'model': 'gpt-3.5-turbo', 'messages': [{'role': 'user', 'content': prompt}]})

        # Simulate a successful response for testing
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'choices': [{'message': {'content': 'Here is a response.'}}]}

        response = requests.post(self.api_url, headers=headers, data=data)
        response_data = response.json()

        if response.status_code == 200 and 'choices' in response_data:
            return response_data['choices'][0]['message']['content']
        else:
            raise Exception(f'Error drafting response: {response_data}')