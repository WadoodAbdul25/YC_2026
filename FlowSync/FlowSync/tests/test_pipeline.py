import pytest
from unittest.mock import patch
from FlowSync.pipeline import EmailPipeline

class TestEmailPipeline:
    @patch('FlowSync.noise_filtering.NoiseFilter')
    @patch('FlowSync.task_generation.TaskGenerator')
    @patch('FlowSync.response_drafting.ResponseDrafting')
    def test_process_email(self, mock_response_drafting, mock_task_generator, mock_noise_filter):
        email_pipeline = EmailPipeline()
        mock_noise_filter.return_value.apply.return_value = "filtered_email"
        mock_task_generator.return_value.generate.return_value = ["task1"]
        mock_response_drafting.return_value.draft_response.return_value = "Drafted response"

        tasks, response = email_pipeline.process_email('{"email": "test@example.com"}')
        assert tasks == ["task1"]
        assert response == "Drafted response"
