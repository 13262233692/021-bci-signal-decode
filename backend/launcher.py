import subprocess
import sys
import os
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

log_file = "service_output.log"
with open(log_file, "w", buffering=1) as f:
    f.write(f"Launcher started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Working directory: {os.getcwd()}\n")
    f.flush()
    
    try:
        result = subprocess.run(
            [sys.executable, "-u", "quick_start.py"],
            stdout=f,
            stderr=subprocess.STDOUT,
            bufsize=1
        )
        f.write(f"\nProcess exited with code: {result.returncode}\n")
    except Exception as e:
        f.write(f"Launcher error: {e}\n")
        import traceback
        traceback.print_exc(file=f)
