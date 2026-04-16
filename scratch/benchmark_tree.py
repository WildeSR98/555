import sys
import os
import time
from pathlib import Path
from sqlalchemy.orm import selectinload

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_session
from src.models import Project, Device, Operation

def benchmark_tree():
    with get_session() as db:
        print("Benchmarking Project Tree Query...")
        start_time = time.time()
        
        # Using the same optimization logic as in the API
        query = db.query(Project).options(
            selectinload(Project.devices).selectinload(Device.operations)
        ).order_by(Project.created_at.desc())
        
        projects = query.all()
        fetch_duration = time.time() - start_time
        print(f"Fetch completed in {fetch_duration:.4f} seconds")
        
        print(f"Total projects: {len(projects)}")
        
        # Verify N+1 by checking if we can iterate without more queries 
        # (Though benchmark doesn't strictly prove it, standard logging or Profiler would)
        loop_start = time.time()
        total_devices = 0
        total_ops = 0
        for p in projects:
            for d in p.devices:
                total_devices += 1
                for op in d.operations:
                    total_ops += 1
        
        loop_duration = time.time() - loop_start
        print(f"Loop through {total_devices} devices and {total_ops} operations completed in {loop_duration:.4f} seconds")
        print(f"Total duration: {time.time() - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark_tree()
