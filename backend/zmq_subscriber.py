import zmq
import numpy as np
import json
import threading
import time
from config import Config


class ZMQSubscriber:
    def __init__(self, on_data_callback):
        self.on_data = on_data_callback
        self.context = None
        self.socket = None
        self._running = False
        self._thread = None
        self.num_channels = Config.NUM_CHANNELS
        self.chunk_size = Config.CHUNK_SIZE

    def connect(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        addr = f"tcp://{Config.ZMQ_SUBSCRIBE_HOST}:{Config.ZMQ_SUBSCRIBE_PORT}"
        self.socket.connect(addr)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, Config.ZMQ_TOPIC)
        print(f"[ZMQ] Subscribed to {addr}, topic: {Config.ZMQ_TOPIC}")

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()

    def _receive_loop(self):
        while self._running:
            try:
                message = self.socket.recv_string(flags=zmq.NOBLOCK)
                self._parse_message(message)
            except zmq.Again:
                time.sleep(0.001)
            except Exception as e:
                print(f"[ZMQ] Receive error: {e}")
                time.sleep(0.01)

    def _parse_message(self, message):
        try:
            parts = message.split(" ", 1)
            if len(parts) < 2:
                return
            payload = parts[1]
            data = json.loads(payload)

            if "samples" in data:
                samples = np.array(data["samples"], dtype=np.float64)
                if samples.shape == (self.num_channels, self.chunk_size):
                    self.on_data(samples)
                elif samples.ndim == 2 and samples.shape[0] == self.num_channels:
                    self.on_data(samples)
        except Exception as e:
            print(f"[ZMQ] Parse error: {e}")


class ZMQPublisher:
    def __init__(self):
        self.context = None
        self.socket = None
        self.num_channels = Config.NUM_CHANNELS
        self.chunk_size = Config.CHUNK_SIZE

    def bind(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        addr = f"tcp://*:{Config.ZMQ_SUBSCRIBE_PORT}"
        self.socket.bind(addr)
        print(f"[ZMQ] Publisher bound to {addr}")
        time.sleep(0.5)

    def publish(self, samples):
        payload = json.dumps({"samples": samples.tolist()})
        message = f"{Config.ZMQ_TOPIC} {payload}"
        self.socket.send_string(message)

    def close(self):
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()
