import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / '.env')

def test_timing(host):
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME')
    
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}?connect_timeout=10"
    print(f"Testing connection to {host}...")
    
    start = time.time()
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        end = time.time()
        print(f"Success! Time: {end - start:.4f}s")
    except Exception as e:
        end = time.time()
        print(f"Failed! Time: {end - start:.4f}s")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_timing("localhost")
    test_timing("127.0.0.1")
