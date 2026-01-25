from unittest.mock import patch

class MockResponse:
    @staticmethod
    def json():
        return {
            'choices': [
                {'message': {'content': 'This is a mock response.'}}
            ]
        }

    @staticmethod
    def raise_for_status():
        pass

@patch('FlowSync.response_drafting.requests.post')
def mock_post(mock_post):
    mock_post.return_value = MockResponse()
