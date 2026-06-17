import redis
import pickle
import threading
from config import Config

REDIS_QUEUE_KEY = "bci_signal_queue"
REDIS_LATEST_KEY = "bci_signal_latest"
MAX_QUEUE_SIZE = 1000


class RedisQueueManager:
    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self._connected = False

    @property
    def client(self):
        if self._client is None:
            self._connect()
        return self._client

    def _connect(self):
        try:
            self._client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=False
            )
            self._client.ping()
            self._connected = True
            print(f"[Redis] Connected to {Config.REDIS_HOST}:{Config.REDIS_PORT}")
        except Exception as e:
            print(f"[Redis] Connection failed: {e}, using in-memory fallback")
            self._connected = False
            self._queue = []
            self._latest = None

    def push(self, data):
        serialized = pickle.dumps(data)
        with self._lock:
            if self._connected:
                try:
                    pipe = self.client.pipeline()
                    pipe.rpush(REDIS_QUEUE_KEY, serialized)
                    pipe.ltrim(REDIS_QUEUE_KEY, -MAX_QUEUE_SIZE, -1)
                    pipe.set(REDIS_LATEST_KEY, serialized)
                    pipe.execute()
                    return
                except Exception as e:
                    print(f"[Redis] Push error: {e}, using in-memory fallback")
                    self._connected = False
                    self._queue = []
                    self._latest = None

            if not hasattr(self, '_queue'):
                self._queue = []
            self._queue.append(serialized)
            if len(self._queue) > MAX_QUEUE_SIZE:
                self._queue = self._queue[-MAX_QUEUE_SIZE:]
            self._latest = serialized

    def pop_all(self):
        with self._lock:
            if self._connected:
                try:
                    items = self.client.lrange(REDIS_QUEUE_KEY, 0, -1)
                    self.client.delete(REDIS_QUEUE_KEY)
                    return [pickle.loads(item) for item in items]
                except Exception as e:
                    print(f"[Redis] Pop error: {e}")
                    return []

            if not hasattr(self, '_queue'):
                return []
            items = self._queue[:]
            self._queue.clear()
            return [pickle.loads(item) for item in items]

    def get_latest(self):
        with self._lock:
            if self._connected:
                try:
                    data = self.client.get(REDIS_LATEST_KEY)
                    if data:
                        return pickle.loads(data)
                    return None
                except Exception as e:
                    print(f"[Redis] Get latest error: {e}")
                    return None

            if hasattr(self, '_latest') and self._latest is not None:
                return pickle.loads(self._latest)
            return None

    def clear(self):
        with self._lock:
            if self._connected:
                try:
                    self.client.delete(REDIS_QUEUE_KEY)
                    self.client.delete(REDIS_LATEST_KEY)
                except Exception:
                    pass
            if hasattr(self, '_queue'):
                self._queue.clear()
            self._latest = None
