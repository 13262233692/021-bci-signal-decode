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
        self.inject_artifacts = Config.ICA_INJECT_ARTIFACTS
        self.publisher = ZMQPublisher()
        self._running = False
        self._thread = None
        self._t = 0.0

        self._init_artifact_topo()
        self._init_artifact_schedulers()

    def _init_artifact_topo(self):
        self._eog_topo = np.zeros(self.num_channels, dtype=np.float64)
        for ch in range(self.num_channels):
            row = ch // 8
            col = ch % 8
            frontal_score = max(0.0, 1.0 - (row / 7.0)) * max(0.0, 1.0 - abs(col - 3.5) / 4.0)
            self._eog_topo[ch] = frontal_score
        self._eog_topo = self._eog_topo / (np.max(self._eog_topo) + 1e-8)

        self._ecg_topo = np.zeros(self.num_channels, dtype=np.float64)
        for ch in range(self.num_channels):
            col = ch % 8
            temporal_score = max(0.0, 1.0 - abs(col - 3.5) / 4.0) * 0.6
            self._ecg_topo[ch] = temporal_score + 0.1
        self._ecg_topo = self._ecg_topo / (np.max(self._ecg_topo) + 1e-8)

    def _init_artifact_schedulers(self):
        self._next_blink_time = 3.0 + np.random.uniform(0, 2.0)
        self._next_saccade_time = 5.0 + np.random.uniform(0, 5.0)
        self._next_heartbeat_time = 1.0
        self._global_t = 0.0

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

    def _generate_blink_waveform(self, t_rel, duration=0.35):
        sigma = duration / 5.0
        mu = duration / 2.0
        gaussian = np.exp(-0.5 * ((t_rel - mu) / sigma) ** 2)
        sharpness = 1.0 + 0.5 * np.sin(2 * np.pi * 3.0 * t_rel / duration)
        amplitude = 250 + np.random.uniform(-50, 80)
        return amplitude * gaussian * sharpness

    def _generate_saccade_waveform(self, t_rel, duration=1.5):
        ramp = np.minimum(t_rel / (duration * 0.3), 1.0)
        decay = np.exp(-(t_rel - duration * 0.3) / (duration * 0.5))
        envelope = np.where(t_rel < duration * 0.3, ramp, decay)
        freq_sweep = 0.8 + 2.0 * (t_rel / duration)
        oscillation = np.sin(2 * np.pi * freq_sweep * t_rel + np.random.uniform(0, np.pi))
        amplitude = 120 + np.random.uniform(-30, 60)
        direction = 1.0 if np.random.rand() > 0.5 else -1.0
        return direction * amplitude * envelope * oscillation

    def _generate_heartbeat_waveform(self, t_rel, duration=0.6):
        sigma_qrs = 0.04
        mu_qrs = 0.2
        qrs = np.exp(-0.5 * ((t_rel - mu_qrs) / sigma_qrs) ** 2)
        t_wave = 0.3 * np.exp(-0.5 * ((t_rel - 0.4) / 0.08) ** 2)
        p_wave = 0.15 * np.exp(-0.5 * ((t_rel - 0.1) / 0.03) ** 2)
        amplitude = 180 + np.random.uniform(-20, 30)
        return amplitude * (qrs + t_wave - p_wave)

    def _inject_eog_artifacts(self, samples, t_array):
        chunk_start_time = self._global_t
        chunk_duration = self.chunk_size / self.sample_rate
        chunk_end_time = chunk_start_time + chunk_duration
        dt = 1.0 / self.sample_rate

        while self._next_blink_time < chunk_end_time:
            blink_start_t = self._next_blink_time
            blink_duration = 0.35
            blink_chunk_start = max(0, int((blink_start_t - chunk_start_time) / dt))
            blink_chunk_end = min(
                self.chunk_size,
                int((blink_start_t + blink_duration - chunk_start_time) / dt) + 1
            )

            if blink_chunk_start < self.chunk_size and blink_chunk_end > 0:
                local_t = np.arange(blink_chunk_start, blink_chunk_end) * dt
                rel_t = local_t
                blink_wave = self._generate_blink_waveform(rel_t, blink_duration)
                valid_len = min(len(blink_wave), blink_chunk_end - blink_chunk_start)
                for ch in range(self.num_channels):
                    weight = self._eog_topo[ch]
                    if weight > 0.05:
                        samples[ch, blink_chunk_start:blink_chunk_start + valid_len] += (
                            weight * blink_wave[:valid_len]
                        )

            self._next_blink_time += 3.0 + np.random.uniform(2.0, 5.0)

        while self._next_saccade_time < chunk_end_time:
            sacc_start_t = self._next_saccade_time
            sacc_duration = 1.2 + np.random.uniform(0, 0.8)
            sacc_chunk_start = max(0, int((sacc_start_t - chunk_start_time) / dt))
            sacc_chunk_end = min(
                self.chunk_size,
                int((sacc_start_t + sacc_duration - chunk_start_time) / dt) + 1
            )

            if sacc_chunk_start < self.chunk_size and sacc_chunk_end > 0:
                local_t = np.arange(sacc_chunk_start, sacc_chunk_end) * dt
                rel_t = local_t
                sacc_wave = self._generate_saccade_waveform(rel_t, sacc_duration)
                valid_len = min(len(sacc_wave), sacc_chunk_end - sacc_chunk_start)
                for ch in range(self.num_channels):
                    weight = self._eog_topo[ch] * 0.8
                    if weight > 0.03:
                        samples[ch, sacc_chunk_start:sacc_chunk_start + valid_len] += (
                            weight * sacc_wave[:valid_len]
                        )

            self._next_saccade_time += 6.0 + np.random.uniform(4.0, 10.0)

        return samples

    def _inject_ecg_artifacts(self, samples, t_array):
        chunk_start_time = self._global_t
        chunk_duration = self.chunk_size / self.sample_rate
        chunk_end_time = chunk_start_time + chunk_duration
        dt = 1.0 / self.sample_rate

        while self._next_heartbeat_time < chunk_end_time:
            hb_start_t = self._next_heartbeat_time
            hb_duration = 0.6
            hb_chunk_start = max(0, int((hb_start_t - chunk_start_time) / dt))
            hb_chunk_end = min(
                self.chunk_size,
                int((hb_start_t + hb_duration - chunk_start_time) / dt) + 1
            )

            if hb_chunk_start < self.chunk_size and hb_chunk_end > 0:
                local_t = np.arange(hb_chunk_start, hb_chunk_end) * dt
                rel_t = local_t
                hb_wave = self._generate_heartbeat_waveform(rel_t, hb_duration)
                valid_len = min(len(hb_wave), hb_chunk_end - hb_chunk_start)
                for ch in range(self.num_channels):
                    weight = self._ecg_topo[ch]
                    if weight > 0.05:
                        samples[ch, hb_chunk_start:hb_chunk_start + valid_len] += (
                            weight * hb_wave[:valid_len]
                        )

            self._next_heartbeat_time += 0.85 + np.random.uniform(-0.08, 0.1)

        return samples

    def generate_chunk(self):
        dt = 1.0 / self.sample_rate
        duration = self.chunk_size * dt
        t = np.linspace(self._t, self._t + duration - dt, self.chunk_size)

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

        if self.inject_artifacts:
            samples = self._inject_eog_artifacts(samples, t)
            samples = self._inject_ecg_artifacts(samples, t)

        self._t += duration
        self._global_t += duration

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
