import sys
import os

# Ensure proper app structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import Email, Task, Response

# Add your test cases here