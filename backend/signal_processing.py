import numpy as np
from scipy import signal
from config import Config
from artifact_removal import ICAArtifactRemover


class SignalProcessor:
    def __init__(self):
        self.sample_rate = Config.SAMPLE_RATE
        self.num_channels = Config.NUM_CHANNELS
        self.notch_freq = Config.NOTCH_FREQ
        self.bandpass_low = Config.BANDPASS_LOW
        self.bandpass_high = Config.BANDPASS_HIGH

        self._init_filters()

        self.ica_remover = ICAArtifactRemover(
            num_channels=self.num_channels,
            sample_rate=self.sample_rate,
            window_seconds=Config.ICA_WINDOW_SECONDS,
            retrain_interval_seconds=Config.ICA_RETRAIN_INTERVAL,
            enable=Config.ICA_ENABLE
        )

    def _init_filters(self):
        nyquist = self.sample_rate / 2.0

        notch_wn = self.notch_freq / nyquist
        self.notch_b, self.notch_a = signal.iirnotch(notch_wn, 30.0)

        low_wn = self.bandpass_low / nyquist
        high_wn = self.bandpass_high / nyquist
        self.bp_b, self.bp_a = signal.butter(4, [low_wn, high_wn], btype='band')

        self._notch_zi = np.zeros(
            (self.num_channels, max(len(self.notch_a), len(self.notch_b)) - 1)
        )
        self._bp_zi = np.zeros(
            (self.num_channels, max(len(self.bp_a), len(self.bp_b)) - 1)
        )

    def apply_notch_filter(self, data_chunk):
        filtered = np.zeros_like(data_chunk)
        for ch in range(self.num_channels):
            filtered[ch, :], self._notch_zi[ch, :] = signal.lfilter(
                self.notch_b, self.notch_a,
                data_chunk[ch, :], zi=self._notch_zi[ch, :]
            )
        return filtered

    def apply_bandpass_filter(self, data_chunk):
        filtered = np.zeros_like(data_chunk)
        for ch in range(self.num_channels):
            filtered[ch, :], self._bp_zi[ch, :] = signal.lfilter(
                self.bp_b, self.bp_a,
                data_chunk[ch, :], zi=self._bp_zi[ch, :]
            )
        return filtered

    def process(self, data_chunk):
        if data_chunk.shape != (self.num_channels, data_chunk.shape[1]):
            raise ValueError(
                f"Expected shape ({self.num_channels}, N), got {data_chunk.shape}"
            )

        notch_filtered = self.apply_notch_filter(data_chunk)
        bandpass_filtered = self.apply_bandpass_filter(notch_filtered)

        clean_signal = self.ica_remover.process_chunk(bandpass_filtered)

        return clean_signal

    def reset_state(self):
        self._notch_zi = np.zeros(
            (self.num_channels, max(len(self.notch_a), len(self.notch_b)) - 1)
        )
        self._bp_zi = np.zeros(
            (self.num_channels, max(len(self.bp_a), len(self.bp_b)) - 1)
        )
        self.ica_remover.reset()
