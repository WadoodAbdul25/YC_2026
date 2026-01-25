import os
import sys
import pytest
import django

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

# Set the settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

django.setup()
