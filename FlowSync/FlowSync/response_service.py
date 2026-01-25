import requests

class ResponseService:
    def __init__(self, openai_key, cerebras_key):
        self.openai_key = openai_key
        self.cerebras_key = cerebras_key

    def draft_response(self, content):
        try:
            response = requests.post("https://api.openai.com/v1/completions",
                                     headers={"Authorization": f"Bearer {self.openai_key}"},
                                     json={'prompt': content})
            response.raise_for_status()
            return response.json()['choices'][0]['text']
        except Exception:
            return self.fallback_draft(content)

    def fallback_draft(self, content):
        # Implement Cerebras API response drafting logic
        return "Fallback response from Cerebras"
