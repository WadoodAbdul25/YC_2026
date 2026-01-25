import pytest
from unittest.mock import patch, MagicMock
from FlowSync.response_service import ResponseService

@pytest.fixture
def response_service():
    return ResponseService()

@patch('requests.post')
def test_draft_response_openai(mock_post, response_service):
    mock_response = MagicMock()
    mock_response.json.return_value = {'choices': [{'text': 'This is a response from OpenAI.'}]}
    mock_post.return_value = mock_response

    response = response_service.draft_response('Hello')
    assert response == 'This is a response from OpenAI.'
    mock_post.assert_called_once()

@patch('requests.post')
def test_draft_response_cerebras_fallback(mock_post, response_service):
    mock_response_openai = MagicMock()
    mock_response_openai.json.side_effect = Exception('Error calling OpenAI API')
    mock_post.return_value = mock_response_openai

    mock_response_cerebras = MagicMock()
    mock_response_cerebras.json.return_value = {'generated_text': 'This is a response from Cerebras.'}
    mock_post.side_effect = [mock_response_openai, mock_response_cerebras]

    response = response_service.draft_response('Hello')
    assert response == 'This is a response from Cerebras.'
    assert mock_post.call_count == 2
