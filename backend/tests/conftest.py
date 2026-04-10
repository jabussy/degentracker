import sys
import os

# Add the project root to sys.path so that 'backend' is importable
# when pytest is run from the backend/ directory:  cd backend && python -m pytest tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
