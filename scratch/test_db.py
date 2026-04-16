import sys
import os
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import test_connection
from src.config import config

print(f"Testing connection to {config.db.db_type} at {config.db.db_host}:{config.db.db_port}")
success, message = test_connection()
print(f"Success: {success}")
print(f"Message: {message}")
