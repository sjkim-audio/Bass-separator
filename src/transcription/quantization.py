import numpy as np
import librosa
from typing import List, Dict, Any

class RhythmicQuantizer:
    def __init__(self, sr: int, hop_length: int):
        self.sr = sr
        self.hop_length = hop_length
        self.bpm = 0.0
        self.grid_interval_sec = 0.0

    def estimate_bpm_and_grid(self, y: np.ndarray) -> float:
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr, hop_length=self.hop_length, aggregate=np.median, fmax=400)
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length)
        bpm_result, _ = librosa.beat.beat_track(onset_envelope=pulse, sr=self.sr, hop_length=self.hop_length, tightness=100)
        self.bpm = float(bpm_result[0]) if isinstance(bpm_result, np.ndarray) else float(bpm_result)
        self.grid_interval_sec = 15.0 / self.bpm if self.bpm > 0 else 0.0
        return self.bpm

    def quantize_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.grid_interval_sec <= 0: return events
        quantized_dict = {}
        for event in events:
            grid_idx = int(np.round(event['time'] / self.grid_interval_sec))
            event.update({'grid_index': grid_idx, 'quantized_time': grid_idx * self.grid_interval_sec})
            quantized_dict[grid_idx] = event
        return sorted(list(quantized_dict.values()), key=lambda x: x['grid_index'])
