import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

diag_file = os.path.join(script_dir, "diagnose_results.txt")

with open(diag_file, "w", encoding="utf-8") as f:
    f.write("=== DIAGNOSTIC START ===\n")
    f.write(f"Python version: {sys.version}\n")
    f.write(f"Python executable: {sys.executable}\n")
    f.write(f"CWD: {os.getcwd()}\n")
    f.flush()

    f.write("\n[1] Testing imports...\n")
    f.flush()
    try:
        import flask
        f.write(f"  Flask OK: {flask.__version__}\n")
    except Exception as e:
        f.write(f"  Flask FAIL: {e}\n")

    try:
        import numpy
        f.write(f"  NumPy OK: {numpy.__version__}\n")
    except Exception as e:
        f.write(f"  NumPy FAIL: {e}\n")

    try:
        import zmq
        f.write(f"  PyZMQ OK: {zmq.__version__}\n")
    except Exception as e:
        f.write(f"  PyZMQ FAIL: {e}\n")

    try:
        import redis
        f.write(f"  Redis OK: {redis.__version__}\n")
    except Exception as e:
        f.write(f"  Redis FAIL: {e}\n")

    try:
        import scipy
        f.write(f"  SciPy OK: {scipy.__version__}\n")
    except Exception as e:
        f.write(f"  SciPy FAIL: {e}\n")

    try:
        import dotenv
        f.write(f"  python-dotenv OK\n")
    except Exception as e:
        f.write(f"  python-dotenv FAIL: {e}\n")

    f.flush()

    f.write("\n[2] Importing project modules...\n")
    f.flush()
    try:
        from config import Config
        f.write("  config.py OK\n")
        f.write(f"    FLASK_HOST={Config.FLASK_HOST}\n")
        f.write(f"    FLASK_PORT={Config.FLASK_PORT}\n")
    except Exception as e:
        f.write(f"  config.py FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        from signal_processing import SignalProcessor
        f.write("  signal_processing.py OK\n")
    except Exception as e:
        f.write(f"  signal_processing.py FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        from redis_queue import RedisQueueManager
        f.write("  redis_queue.py OK\n")
    except Exception as e:
        f.write(f"  redis_queue.py FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        from zmq_subscriber import ZMQSubscriber, ZMQPublisher
        f.write("  zmq_subscriber.py OK\n")
    except Exception as e:
        f.write(f"  zmq_subscriber.py FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        from simulator import SignalSimulator
        f.write("  simulator.py OK\n")
    except Exception as e:
        f.write(f"  simulator.py FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    f.flush()

    f.write("\n[3] Creating components...\n")
    f.flush()
    try:
        signal_processor = SignalProcessor()
        f.write("  SignalProcessor created OK\n")
    except Exception as e:
        f.write(f"  SignalProcessor FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        redis_queue = RedisQueueManager()
        f.write("  RedisQueueManager created OK\n")
    except Exception as e:
        f.write(f"  RedisQueueManager FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    try:
        simulator = SignalSimulator()
        f.write("  SignalSimulator created OK\n")
    except Exception as e:
        f.write(f"  SignalSimulator FAIL: {e}\n")
        import traceback
        traceback.print_exc(file=f)

    f.flush()
    f.write("\n=== DIAGNOSTIC COMPLETE ===\n")
    f.flush()
