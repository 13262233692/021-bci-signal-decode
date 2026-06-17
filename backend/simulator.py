import numpy as np
import threading
import time
from config import Config
from zmq_subscriber import ZMQPublisher


class SignalSimulator:
    def __init__(self):
        self.num_channels = Config.NUM_CHANNELS
        self.sample_rate = Config.SAMPLE_RATE
        self.chunk_size = Config.CHUNK_SIZE
        self.notch_freq = Config.NOTCH_FREQ
        self.publisher = ZMQPublisher()
        self._running = False
        self._thread = None
        self._t = 0.0

    def _generate_alpha_wave(self, t, channel_idx):
        freq_base = 8 + (channel_idx % 8) * 0.3
        amp = 30 + (channel_idx % 10) * 2
        return amp * np.sin(2 * np.pi * freq_base * t)

    def _generate_beta_wave(self, t, channel_idx):
        freq_base = 15 + (channel_idx % 6) * 1.2
        amp = 15 + (channel_idx % 7) * 1.5
        return amp * np.sin(2 * np.pi * freq_base * t)

    def _generate_gamma_wave(self, t, channel_idx):
        freq_base = 40 + (channel_idx % 10) * 2.5
        amp = 8 + (channel_idx % 5) * 1.0
        return amp * np.sin(2 * np.pi * freq_base * t)

    def _generate_noise(self, shape):
        return np.random.normal(0, 5, shape)

    def _generate_powerline_noise(self, t):
        harmonics = 1
        noise = np.zeros_like(t)
        for h in range(1, harmonics + 1):
            noise += 50 * h * np.sin(2 * np.pi * self.notch_freq * h * t + np.random.rand() * 2 * np.pi)
        return noise

    def _generate_spikes(self, t, channel_idx):
        spikes = np.zeros_like(t)
        if channel_idx % 7 == 0:
            spike_indices = np.random.choice(len(t), size=3, replace=False)
            spikes[spike_indices] = np.random.uniform(80, 150, size=3)
        return spikes

    def generate_chunk(self):
        dt = 1.0 / self.sample_rate
        duration = self.chunk_size * dt
        t = np.linspace(self._t, self._t + duration - dt, self.chunk_size)
        self._t += duration

        samples = np.zeros((self.num_channels, self.chunk_size), dtype=np.float64)

        for ch in range(self.num_channels):
            alpha = self._generate_alpha_wave(t, ch)
            beta = self._generate_beta_wave(t, ch)
            gamma = self._generate_gamma_wave(t, ch)
            noise = self._generate_noise(self.chunk_size)
            spikes = self._generate_spikes(t, ch)
            samples[ch, :] = alpha + beta + gamma + noise + spikes

        powerline = self._generate_powerline_noise(t)
        for ch in range(self.num_channels):
            samples[ch, :] += powerline

        return samples

    def start(self):
        self.publisher.bind()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[Simulator] Started signal generation")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.publisher.close()
        print("[Simulator] Stopped")

    def _run(self):
        chunk_interval = self.chunk_size / self.sample_rate
        next_time = time.time()

        while self._running:
            try:
                chunk = self.generate_chunk()
                self.publisher.publish(chunk)
            except Exception as e:
                print(f"[Simulator] Error: {e}")

            next_time += chunk_interval
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_time = time.time()
