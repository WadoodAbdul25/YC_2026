import pytest
import django
import sys
import os

# Set up Django settings for testing
os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.config.settings'
django.setup()

@pytest.fixture(scope='session')
def django_db_setup():
    from django.conf import settings
    settings.DEBUG = True
