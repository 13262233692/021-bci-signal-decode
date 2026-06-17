import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    ZMQ_SUBSCRIBE_HOST = os.getenv("ZMQ_SUBSCRIBE_HOST", "localhost")
    ZMQ_SUBSCRIBE_PORT = int(os.getenv("ZMQ_SUBSCRIBE_PORT", "5556"))
    ZMQ_TOPIC = os.getenv("ZMQ_TOPIC", "bci")

    NUM_CHANNELS = int(os.getenv("NUM_CHANNELS", "64"))
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "1000"))
    NOTCH_FREQ = float(os.getenv("NOTCH_FREQ", "50"))
    BANDPASS_LOW = float(os.getenv("BANDPASS_LOW", "0.5"))
    BANDPASS_HIGH = float(os.getenv("BANDPASS_HIGH", "300"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "100"))

    SIMULATE_MODE = os.getenv("SIMULATE_MODE", "true").lower() == "true"
