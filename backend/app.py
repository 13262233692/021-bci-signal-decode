import os
os.environ['PYTHONUNBUFFERED'] = '1'

import sys
import time
import threading
import numpy as np
from flask import Flask, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import Config
from signal_processing import SignalProcessor
from zmq_subscriber import ZMQSubscriber
from redis_queue import RedisQueueManager
from simulator import SignalSimulator

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bci-signal-decode-2024'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

signal_processor = SignalProcessor()
redis_queue = RedisQueueManager()
simulator = None
zmq_subscriber = None

_broadcast_thread = None
_broadcast_running = False
_sample_counter = 0
_start_timestamp = None
_lock = threading.Lock()


def on_raw_data(raw_samples):
    global _sample_counter, _start_timestamp

    try:
        processed = signal_processor.process(raw_samples)

        with _lock:
            if _start_timestamp is None:
                _start_timestamp = time.time() * 1000

            num_samples = processed.shape[1]
            timestamps = np.linspace(
                _start_timestamp + _sample_counter * (1000.0 / Config.SAMPLE_RATE),
                _start_timestamp + (_sample_counter + num_samples - 1) * (1000.0 / Config.SAMPLE_RATE),
                num_samples
            )

            data_packet = {
                "timestamps": timestamps.tolist(),
                "samples": processed.tolist(),
                "channels": Config.NUM_CHANNELS,
                "sampleRate": Config.SAMPLE_RATE,
                "chunkSize": num_samples
            }

            redis_queue.push(data_packet)
            _sample_counter += num_samples

    except Exception as e:
        print(f"[Data] Processing error: {e}", flush=True)


def broadcast_loop():
    global _broadcast_running
    print("[Broadcast] Starting WebSocket broadcast loop", flush=True)

    while _broadcast_running:
        try:
            packets = redis_queue.pop_all()
            if packets:
                socketio.emit('signal_data', {"packets": packets})
            time.sleep(0.01)
        except Exception as e:
            print(f"[Broadcast] Error: {e}", flush=True)
            time.sleep(0.05)

    print("[Broadcast] Stopped", flush=True)


def start_broadcast():
    global _broadcast_thread, _broadcast_running
    if _broadcast_thread is None or not _broadcast_running:
        _broadcast_running = True
        _broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
        _broadcast_thread.start()


@app.route('/')
def index():
    return jsonify({
        "service": "BCI Signal Decode Service",
        "status": "running",
        "channels": Config.NUM_CHANNELS,
        "sampleRate": Config.SAMPLE_RATE,
        "simulateMode": Config.SIMULATE_MODE
    })


@app.route('/api/status')
def status():
    latest = redis_queue.get_latest()
    with _lock:
        total = _sample_counter
    return jsonify({
        "running": True,
        "simulateMode": Config.SIMULATE_MODE,
        "channels": Config.NUM_CHANNELS,
        "sampleRate": Config.SAMPLE_RATE,
        "notchFreq": Config.NOTCH_FREQ,
        "bandpass": [Config.BANDPASS_LOW, Config.BANDPASS_HIGH],
        "totalSamples": total,
        "hasData": latest is not None
    })


@socketio.on('connect')
def handle_connect():
    print("[SocketIO] Client connected", flush=True)
    start_broadcast()
    latest = redis_queue.get_latest()
    if latest:
        emit('signal_data', {"packets": [latest]})
    emit('config', {
        "channels": Config.NUM_CHANNELS,
        "sampleRate": Config.SAMPLE_RATE,
        "notchFreq": Config.NOTCH_FREQ,
        "bandpass": [Config.BANDPASS_LOW, Config.BANDPASS_HIGH]
    })


@socketio.on('disconnect')
def handle_disconnect():
    print("[SocketIO] Client disconnected", flush=True)


@socketio.on('request_latest')
def handle_request_latest():
    latest = redis_queue.get_latest()
    if latest:
        emit('signal_data', {"packets": [latest]})


@socketio.on('reset')
def handle_reset():
    global _sample_counter, _start_timestamp
    with _lock:
        _sample_counter = 0
        _start_timestamp = None
    signal_processor.reset_state()
    redis_queue.clear()
    emit('reset_done')
    print("[SocketIO] State reset requested", flush=True)


def init_pipeline():
    global zmq_subscriber, simulator

    if Config.SIMULATE_MODE:
        print("[Init] Starting in SIMULATE mode", flush=True)
        simulator = SignalSimulator()
        simulator.start()
        time.sleep(0.5)
        print("[Init] Simulator started, ZMQ publisher bound", flush=True)
    else:
        print("[Init] Starting in LIVE hardware mode", flush=True)

    zmq_subscriber = ZMQSubscriber(on_data_callback=on_raw_data)
    zmq_subscriber.connect()
    zmq_subscriber.start()
    print("[Init] ZMQ subscriber connected", flush=True)

    start_broadcast()
    print("[Init] Pipeline initialized", flush=True)


if __name__ == '__main__':
    print("=" * 50, flush=True)
    print("  BCI Signal Decode Backend Service", flush=True)
    print("=" * 50, flush=True)
    print(f"  Channels: {Config.NUM_CHANNELS}", flush=True)
    print(f"  Sample Rate: {Config.SAMPLE_RATE} Hz", flush=True)
    print(f"  Notch Filter: {Config.NOTCH_FREQ} Hz", flush=True)
    print(f"  Bandpass: {Config.BANDPASS_LOW}-{Config.BANDPASS_HIGH} Hz", flush=True)
    print(f"  Mode: {'SIMULATE' if Config.SIMULATE_MODE else 'LIVE HARDWARE'}", flush=True)
    print("=" * 50, flush=True)

    init_pipeline()

    print(f"[Flask] Starting server on {Config.FLASK_HOST}:{Config.FLASK_PORT}", flush=True)

    socketio.run(
        app,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
