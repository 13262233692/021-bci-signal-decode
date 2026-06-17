import numpy as np
from scipy import stats, signal
from sklearn.decomposition import FastICA
from config import Config
import threading
import time


class SlidingWindowCollector:
    def __init__(self, num_channels, window_seconds=2.0, sample_rate=1000):
        self.num_channels = num_channels
        self.window_size = int(window_seconds * sample_rate)
        self.sample_rate = sample_rate
        self._buffer = np.zeros((num_channels, self.window_size), dtype=np.float64)
        self._write_pos = 0
        self._total_written = 0

    def push(self, data_chunk):
        chunk_size = data_chunk.shape[1]
        if chunk_size >= self.window_size:
            self._buffer = data_chunk[:, -self.window_size:].copy()
            self._write_pos = 0
            self._total_written += chunk_size
            return

        wrap_point = self.window_size - self._write_pos
        if chunk_size <= wrap_point:
            self._buffer[:, self._write_pos:self._write_pos + chunk_size] = data_chunk
            self._write_pos += chunk_size
        else:
            self._buffer[:, self._write_pos:] = data_chunk[:, :wrap_point]
            self._buffer[:, :chunk_size - wrap_point] = data_chunk[:, wrap_point:]
            self._write_pos = chunk_size - wrap_point

        if self._write_pos >= self.window_size:
            self._write_pos = 0

        self._total_written += chunk_size

    def is_full(self):
        return self._total_written >= self.window_size

    def get_window(self):
        if self._total_written < self.window_size:
            return None

        if self._write_pos == 0:
            return self._buffer.copy()

        result = np.zeros_like(self._buffer)
        result[:, :self.window_size - self._write_pos] = self._buffer[:, self._write_pos:]
        result[:, self.window_size - self._write_pos:] = self._buffer[:, :self._write_pos]
        return result

    def reset(self):
        self._buffer.fill(0)
        self._write_pos = 0
        self._total_written = 0


class ArtifactFeatureDetector:
    def __init__(self, sample_rate=1000):
        self.sample_rate = sample_rate
        self._init_band_filters()

    def _init_band_filters(self):
        nyquist = self.sample_rate / 2.0
        low_wn = 0.5 / nyquist
        high_wn = 4.0 / nyquist
        self._slow_b, self._slow_a = signal.butter(2, [low_wn, high_wn], btype='band')

        low_wn = 8.0 / nyquist
        high_wn = 13.0 / nyquist
        self._alpha_b, self._alpha_a = signal.butter(2, [low_wn, high_wn], btype='band')

    def extract_features(self, ic_source):
        features = {}

        features['mean'] = np.mean(ic_source)
        features['std'] = np.std(ic_source)
        features['variance'] = np.var(ic_source)

        features['skewness'] = stats.skew(ic_source)
        features['kurtosis'] = stats.kurtosis(ic_source, fisher=True)

        abs_ic = np.abs(ic_source)
        sorted_vals = np.sort(abs_ic)[::-1]
        p99 = np.percentile(abs_ic, 99)
        p95 = np.percentile(abs_ic, 95)
        p50 = np.percentile(abs_ic, 50)

        features['peak_to_peak'] = np.max(ic_source) - np.min(ic_source)
        features['p99_ratio'] = p99 / (p50 + 1e-10)
        features['p95_ratio'] = p95 / (p50 + 1e-10)
        features['top1_mean_ratio'] = (np.mean(sorted_vals[:10]) / (p50 + 1e-10))

        try:
            freqs, psd = signal.welch(
                ic_source, fs=self.sample_rate,
                nperseg=min(1024, len(ic_source)),
                scaling='density'
            )
            total_power = np.sum(psd) + 1e-10

            delta_mask = (freqs >= 0.5) & (freqs <= 4.0)
            alpha_mask = (freqs >= 8.0) & (freqs <= 13.0)
            beta_mask = (freqs >= 14.0) & (freqs <= 30.0)
            gamma_mask = (freqs >= 31.0) & (freqs <= 100.0)
            low_mask = (freqs >= 0.5) & (freqs <= 2.0)

            features['delta_power_ratio'] = np.sum(psd[delta_mask]) / total_power
            features['alpha_power_ratio'] = np.sum(psd[alpha_mask]) / total_power
            features['beta_power_ratio'] = np.sum(psd[beta_mask]) / total_power
            features['gamma_power_ratio'] = np.sum(psd[gamma_mask]) / total_power
            features['slow_power_ratio'] = np.sum(psd[low_mask]) / total_power

            features['spectral_centroid'] = np.sum(freqs * psd) / total_power
            features['spectral_entropy'] = self._spectral_entropy(psd)

        except Exception:
            features['delta_power_ratio'] = 0.0
            features['alpha_power_ratio'] = 0.0
            features['beta_power_ratio'] = 0.0
            features['gamma_power_ratio'] = 0.0
            features['slow_power_ratio'] = 0.0
            features['spectral_centroid'] = 0.0
            features['spectral_entropy'] = 0.0

        if len(ic_source) >= self.sample_rate:
            diff_signal = np.diff(ic_source)
            features['mean_gradient'] = np.mean(np.abs(diff_signal))
            features['zero_crossings'] = np.sum(np.diff(np.sign(ic_source)) != 0) / len(ic_source)
        else:
            features['mean_gradient'] = 0.0
            features['zero_crossings'] = 0.0

        return features

    def _spectral_entropy(self, psd):
        psd_norm = psd / (np.sum(psd) + 1e-10)
        psd_norm = psd_norm[psd_norm > 0]
        return -np.sum(psd_norm * np.log2(psd_norm))

    def classify_eog_artifact(self, features):
        score = 0.0

        if abs(features['skewness']) > 2.0:
            score += min(abs(features['skewness']) / 5.0, 1.0) * 25

        if features['kurtosis'] > 5.0:
            score += min(features['kurtosis'] / 10.0, 1.0) * 20

        if features['peak_to_peak'] > 150:
            score += min(features['peak_to_peak'] / 300.0, 1.0) * 20

        if features['p99_ratio'] > 3.0:
            score += min((features['p99_ratio'] - 3.0) / 5.0, 1.0) * 15

        if features['slow_power_ratio'] > 0.15:
            score += min((features['slow_power_ratio'] - 0.15) / 0.3, 1.0) * 15

        if features['delta_power_ratio'] > 0.3:
            score += min((features['delta_power_ratio'] - 0.3) / 0.4, 1.0) * 10

        if features['spectral_centroid'] < 15.0:
            score += (1.0 - min(features['spectral_centroid'] / 15.0, 1.0)) * 5

        is_artifact = score >= 40.0

        artifact_types = []
        if abs(features['skewness']) > 3.0 and features['slow_power_ratio'] > 0.2:
            artifact_types.append('Blink')
        elif features['delta_power_ratio'] > 0.35 and features['kurtosis'] < 8.0:
            artifact_types.append('Eye-Movement')
        if features['peak_to_peak'] > 200 and features['p99_ratio'] > 5.0:
            artifact_types.append('Transient')
        if not artifact_types:
            artifact_types.append('Generic-EOG')

        return is_artifact, score, artifact_types


class ICAArtifactRemover:
    def __init__(self, num_channels=64, sample_rate=1000,
                 window_seconds=2.0, retrain_interval_seconds=10.0,
                 max_ica_components=None, enable=True):
        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.enable = enable
        self.max_components = max_ica_components or min(num_channels, 60)

        self._window_collector = SlidingWindowCollector(
            num_channels, window_seconds, sample_rate
        )
        self._feature_detector = ArtifactFeatureDetector(sample_rate)

        self._lock = threading.Lock()
        self._unmixing_matrix = None
        self._mixing_matrix = None
        self._artifact_mask = np.zeros(self.max_components, dtype=bool)
        self._component_features = []
        self._last_retrain_time = 0
        self._retrain_interval = retrain_interval_seconds
        self._retrain_thread = None
        self._retrain_running = False
        self._ica_ready = False
        self._retrain_counter = 0

        self._processing_buffer = None
        self._overlap_samples = int(sample_rate * 0.5)

        self.stats = {
            'total_components': 0,
            'removed_components': 0,
            'retrain_count': 0,
            'last_score_mean': 0.0,
            'artifact_types_count': {}
        }

    def _async_retrain(self, window_data):
        try:
            self._run_ica_decomposition(window_data)
        except Exception as e:
            print(f"[ICA] Async retrain error: {e}", flush=True)
        finally:
            self._retrain_thread = None

    def _run_ica_decomposition(self, window_data):
        ica_input = window_data.T

        means = np.mean(ica_input, axis=0, keepdims=True)
        stds = np.std(ica_input, axis=0, keepdims=True) + 1e-8
        ica_input_centered = (ica_input - means) / stds

        ica = FastICA(
            n_components=self.max_components,
            algorithm='parallel',
            whiten='unit-variance',
            fun='logcosh',
            max_iter=1000,
            tol=1e-3,
            random_state=42
        )

        sources = ica.fit_transform(ica_input_centered)
        components_sources = sources.T

        mixing = ica.mixing_
        unmixing = ica.components_

        artifact_mask = np.zeros(self.max_components, dtype=bool)
        component_info = []

        scores = []
        for i in range(self.max_components):
            ic_source = components_sources[i, :] * stds[0, 0]
            features = self._feature_detector.extract_features(ic_source)
            is_art, score, types = self._feature_detector.classify_eog_artifact(features)
            artifact_mask[i] = is_art
            scores.append(score)
            component_info.append({
                'idx': i,
                'is_artifact': is_art,
                'score': score,
                'types': types,
                'features': {
                    'skewness': round(features['skewness'], 3),
                    'kurtosis': round(features['kurtosis'], 3),
                    'peak_to_peak': round(features['peak_to_peak'], 2),
                    'delta_power_ratio': round(features['delta_power_ratio'], 3)
                }
            })

        sorted_indices = np.argsort(scores)[::-1]
        top_artifact_count = min(3, int(self.max_components * 0.08))
        for i in range(top_artifact_count):
            idx = sorted_indices[i]
            if scores[idx] >= 30 and not artifact_mask[idx]:
                artifact_mask[idx] = True
                for comp in component_info:
                    if comp['idx'] == idx:
                        comp['is_artifact'] = True
                        comp['types'].append('High-Amplitude')
                        break

        removed_channels = np.sum(artifact_mask)
        with self._lock:
            self._unmixing_matrix = unmixing
            self._mixing_matrix = mixing
            self._artifact_mask = artifact_mask
            self._component_features = component_info
            self._ica_ready = True
            self._retrain_counter += 1
            self._last_retrain_time = time.time()

            self.stats['total_components'] = self.max_components
            self.stats['removed_components'] = int(removed_channels)
            self.stats['retrain_count'] = self._retrain_counter
            self.stats['last_score_mean'] = float(np.mean(scores))

            type_counts = {}
            for comp in component_info:
                if comp['is_artifact']:
                    for t in comp['types']:
                        type_counts[t] = type_counts.get(t, 0) + 1
            self.stats['artifact_types_count'] = type_counts

        artifacts = [(c['idx'], c['types'], round(c['score'], 1))
                     for c in component_info if c['is_artifact']]
        print(
            f"[ICA] Retrain #{self._retrain_counter}: "
            f"{self.max_components} components, "
            f"removed {removed_channels} artifacts: {artifacts[:5]}",
            flush=True
        )

    def _request_retrain(self, window_data):
        if not self.enable:
            return

        now = time.time()
        if now - self._last_retrain_time < self._retrain_interval:
            return

        if self._retrain_thread is not None and self._retrain_thread.is_alive():
            return

        self._last_retrain_time = now
        self._retrain_thread = threading.Thread(
            target=self._async_retrain,
            args=(window_data.copy(),),
            daemon=True
        )
        self._retrain_thread.start()

    def process_chunk(self, data_chunk):
        self._window_collector.push(data_chunk)

        if not self.enable:
            return data_chunk

        if self._window_collector.is_full():
            window = self._window_collector.get_window()
            if window is not None:
                self._request_retrain(window)

        if not self._ica_ready:
            return data_chunk

        chunk_size = data_chunk.shape[1]
        result = np.zeros_like(data_chunk)

        try:
            with self._lock:
                unmixing = self._unmixing_matrix
                mixing = self._mixing_matrix
                mask = self._artifact_mask

            if unmixing is None or mixing is None:
                return data_chunk

            input_t = data_chunk.T
            means = np.mean(input_t, axis=0, keepdims=True)
            stds = np.std(input_t, axis=0, keepdims=True) + 1e-8
            centered = (input_t - means) / stds

            sources_chunk = centered @ unmixing.T
            keep_mask = ~mask
            sources_clean = sources_chunk.copy()
            sources_clean[:, mask] = 0.0

            reconstructed = sources_clean @ mixing.T
            reconstructed = reconstructed * stds + means
            result = reconstructed.T

        except Exception as e:
            print(f"[ICA] Online processing error: {e}", flush=True)
            return data_chunk

        if np.any(~np.isfinite(result)):
            return data_chunk

        return result

    def get_status(self):
        with self._lock:
            def _to_python(obj):
                if isinstance(obj, (np.bool_, np.integer)):
                    return int(obj) != 0 if isinstance(obj, np.bool_) else int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: _to_python(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [_to_python(i) for i in obj]
                return obj

            return _to_python({
                'enabled': bool(self.enable),
                'ready': bool(self._ica_ready),
                'retrain_count': int(self.stats['retrain_count']),
                'total_components': int(self.stats['total_components']),
                'removed_components': int(self.stats['removed_components']),
                'mean_score': float(self.stats['last_score_mean']),
                'artifact_types': self.stats['artifact_types_count'],
                'components': self._component_features[:10]
            })

    def reset(self):
        with self._lock:
            self._window_collector.reset()
            self._unmixing_matrix = None
            self._mixing_matrix = None
            self._artifact_mask = np.zeros(self.max_components, dtype=bool)
            self._component_features = []
            self._ica_ready = False
            self._retrain_counter = 0
            self._last_retrain_time = 0
            self.stats = {
                'total_components': 0,
                'removed_components': 0,
                'retrain_count': 0,
                'last_score_mean': 0.0,
                'artifact_types_count': {}
            }
