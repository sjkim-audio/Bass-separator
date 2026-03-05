# src/transcription/quantization.py (전체 수정)
import numpy as np
import librosa
from typing import List
from models.events import NoteEvent

class RhythmicQuantizer:
    def __init__(self, sr: int, hop_length: int):
        self.sr = sr
        self.hop_length = hop_length
        self.bpm = 0.0
        self.grid_interval_sec = 0.0

    def estimate_bpm_and_grid(self, y: np.ndarray, fallback_bpm: float = 120.0) -> float:
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr, hop_length=self.hop_length, aggregate=np.median, fmax=400)
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length)
        bpm_result, _ = librosa.beat.beat_track(onset_envelope=pulse, sr=self.sr, hop_length=self.hop_length, tightness=100)
        
        self.bpm = float(bpm_result[0]) if isinstance(bpm_result, np.ndarray) else float(bpm_result)
        
        # [Fix 1] BPM 추정 실패(0 이하) 시 Fallback 처리 (예외 방지)
        if self.bpm <= 0:
            print(f"⚠️ BPM 추정 실패. 기본값({fallback_bpm} BPM)으로 대체합니다.")
            self.bpm = fallback_bpm
            
        self.grid_interval_sec = 15.0 / self.bpm
        return self.bpm

    def quantize_events(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if self.grid_interval_sec <= 0: 
            return events
        
        # [Fix 2] Dictionary 덮어쓰기에 의한 Data Loss(소실) 현상을 List 누적으로 해결
        quantized_events = []
        for event in events:
            grid_idx = int(np.round(event.time / self.grid_interval_sec))
            quantized_events.append(event.update(
                grid_index=grid_idx, 
                quantized_time=grid_idx * self.grid_interval_sec
            ))
            
        # 격자 인덱스와 물리적 발생 시간을 기준으로 정렬하여 반환
        return sorted(quantized_events, key=lambda x: (x.grid_index, x.time))
