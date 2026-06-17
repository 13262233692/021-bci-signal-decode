import subprocess
import sys
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

pid_file = os.path.join(script_dir, "service.pid")
log_file = os.path.join(script_dir, "service.log")

with open(log_file, "w", encoding="utf-8") as log:
    log.write(f"Starting BCI service at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"Python: {sys.executable}\n")
    log.write(f"Script dir: {script_dir}\n")
    log.flush()

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", "quick_start.py"],
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            cwd=script_dir
        )
        
        with open(pid_file, "w") as pf:
            pf.write(str(proc.pid))
        
        log.write(f"Service started with PID: {proc.pid}\n")
        log.flush()
        
        time.sleep(10)
        
        poll = proc.poll()
        if poll is None:
            log.write(f"Service is running (PID: {proc.pid})\n")
        else:
            log.write(f"Service exited early with code: {poll}\n")
        log.flush()
            
    except Exception as e:
        log.write(f"Error: {e}\n")
        import traceback
        traceback.print_exc(file=log)
        log.flush()
