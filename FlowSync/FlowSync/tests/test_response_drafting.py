import pytest
from unittest.mock import patch, MagicMock
from FlowSync.response_drafting import ResponseDrafting

class TestResponseDrafting:
    @patch('openai.ChatCompletion.create')
    def test_draft_response_success(self, mock_create):
        mock_create.return_value = {'choices': [{'message': {'content': 'Response text'}}]}
        responder = ResponseDrafting()
        response = responder.draft_response('Test email context')
        assert response == 'Response text'

    def test_draft_response_invalid_input(self):
        responder = ResponseDrafting()
        with pytest.raises(ValueError, match='Invalid email context provided.'):
            responder.draft_response('')

    @patch('openai.ChatCompletion.create', side_effect=Exception('Test Exception'))
    def test_draft_response_api_failure(self, mock_create):
        responder = ResponseDrafting()
        with pytest.raises(RuntimeError, match='Failed to draft response: Test Exception'):
            responder.draft_response('Test email context')

