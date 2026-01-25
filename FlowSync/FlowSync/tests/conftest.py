import pytest
import django
import os
import sys

sys.path.append(os.path.abspath('.'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings')
django.setup()