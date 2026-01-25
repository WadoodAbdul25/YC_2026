import json
from FlowSync.noise_filtering import NoiseFilter
from FlowSync.task_generation import TaskGenerator
from FlowSync.response_drafting import ResponseDrafting


def process_email(email):
    noise_filter = NoiseFilter(['spam', 'irrelevant'])  # Define irrelevant keywords
    filtered_email = noise_filter.filter_emails([email])
    if filtered_email:
        task_generator = TaskGenerator(filtered_email)
        tasks = task_generator.generate_tasks()
        response_drafter = ResponseDrafting(api_key='YOUR_API_KEY')  # Replace with your actual API key
        response = response_drafter.draft_response(filtered_email)
        return { 'tasks': tasks, 'response': response }
    return None
