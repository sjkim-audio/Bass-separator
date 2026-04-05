import numpy as np
import librosa
from typing import List, Optional
from src.models.events import NoteEvent

class RhythmicQuantizer:
    def __init__(self, sr: int, hop_length: int):
        self.sr = sr
        self.hop_length = hop_length
        self.bpm = 0.0
        self.beat_times = np.array([])
        self.min_gap_sec = 0.05
        self.visual_margin = 0.01

    def estimate_bpm_and_grid(self, y_bassless: Optional[np.ndarray], y_bass: np.ndarray) -> float:
        if y_bassless is not None:
            onset_env = librosa.onset.onset_strength(y=y_bassless, sr=self.sr, hop_length=self.hop_length, aggregate=np.median, fmax=8000)
            if np.max(onset_env) < 0.5:
                print("⚠ [Quantizer] Bassless MR 온셋 에너지가 희박합니다. Bass 트랙 단독 비트 트래킹(Fallback)을 수행합니다.")
                y_bassless = None
                
        if y_bassless is None:
            onset_env = librosa.onset.onset_strength(y=y_bass, sr=self.sr, hop_length=self.hop_length, aggregate=np.median, fmax=400)
            
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length)
        bpm_result, beat_frames = librosa.beat.beat_track(onset_envelope=pulse, sr=self.sr, hop_length=self.hop_length, tightness=100)
        
        self.bpm = float(bpm_result[0]) if isinstance(bpm_result, np.ndarray) else float(bpm_result)
        self.beat_times = librosa.frames_to_time(beat_frames, sr=self.sr, hop_length=self.hop_length)
        
        if self.bpm <= 0 or np.isnan(self.bpm) or len(self.beat_times) < 2:
            self.bpm = 0.0
            self.beat_times = np.array([])
            
        return self.bpm

    def _merge_fragmented_notes(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if not events:
            return []
            
        sorted_events = sorted(events, key=lambda x: x.time)
        merged = [sorted_events[0]]
        
        for curr in sorted_events[1:]:
            prev = merged[-1]
            gap = curr.time - (prev.time + prev.duration)
            
            if prev.midi_note == curr.midi_note and 0 <= gap <= self.min_gap_sec:
                new_duration = (curr.time + curr.duration) - prev.time
                merged[-1] = prev.update(duration=new_duration)
            else:
                merged.append(curr)
                
        return merged

    def _snap_to_dynamic_grid(self, time_sec: float, subdivisions: int = 4) -> float:
        if len(self.beat_times) < 2:
            static_grid_interval = (60.0 / self.bpm) / subdivisions if self.bpm > 0 else 0
            if static_grid_interval == 0:
                return time_sec
            return round(time_sec / static_grid_interval) * static_grid_interval

        idx = np.searchsorted(self.beat_times, time_sec) - 1
        idx = max(0, min(idx, len(self.beat_times) - 2))
        
        b_start = self.beat_times[idx]
        b_end = self.beat_times[idx + 1]
        beat_len = b_end - b_start
        
        grids = [b_start + (j / subdivisions) * beat_len for j in range(subdivisions + 1)]
        return min(grids, key=lambda g: abs(g - time_sec))

    def quantize_events(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if self.bpm <= 0 or not events:
            return events

        merged_events = self._merge_fragmented_notes(events)
        quantized = []
        
        for event in merged_events:
            q_onset = self._snap_to_dynamic_grid(event.time)
            q_offset = self._snap_to_dynamic_grid(event.time + event.duration)
            q_duration = max(q_offset - q_onset, 0.01) 
            
            if len(self.beat_times) >= 2:
                idx = np.searchsorted(self.beat_times, q_onset) - 1
                idx = max(0, min(idx, len(self.beat_times) - 2))
                b_start = self.beat_times[idx]
                beat_len = self.beat_times[idx + 1] - b_start
                sub_idx = round((q_onset - b_start) / (beat_len / 4))
                grid_idx = int(idx * 4 + sub_idx)
            else:
                grid_idx = int(np.round(q_onset / ((60.0 / self.bpm) / 4)))
            
            quantized.append(event.update(
                grid_index=grid_idx,
                quantized_time=q_onset,
                quantized_duration=q_duration
            ))

        quantized.sort(key=lambda x: x.quantized_time)
        for i in range(len(quantized) - 1):
            curr = quantized[i]
            nxt = quantized[i + 1]
            
            if curr.quantized_time + curr.quantized_duration > nxt.quantized_time:
                resolved_duration = max(nxt.quantized_time - curr.quantized_time - self.visual_margin, 0.01)
                quantized[i] = curr.update(quantized_duration=resolved_duration)

        return quantized
    
    def _apply_musical_smoothing(self, events: List[NoteEvent]) -> List[NoteEvent]:
        """
        악보 가독성을 저해하는 32분 음표 이하의 짧은 파편 노트를 제거하거나 
        인접한 긴 노트에 병합함.
        """
        if not events: return []
    
        # 예: 16분 음표 미만의 아주 짧은 노트를 가비지로 판단하여 제거 (BPM 기반 계산)
        min_threshold = (60.0 / self.bpm) / 8 if self.bpm > 0 else 0.05
        return [e for e in events if e.quantized_duration >= min_threshold]
