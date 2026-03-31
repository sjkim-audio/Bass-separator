import numpy as np
import librosa
from typing import List
from src.models.events import NoteEvent

class RhythmicQuantizer:
    def __init__(self, sr: int, hop_length: int):
        self.sr = sr
        self.hop_length = hop_length
        self.bpm = 0.0
        self.beat_times = np.array([])  # 동적 템포 맵
        self.min_gap_sec = 0.05         # 노트 병합을 위한 최대 허용 간격 (50ms)
        self.visual_margin = 0.01       # 오버랩 렌더링 충돌 방지용 최소 여백 (10ms)

    def estimate_bpm_and_grid(self, y_bassless: np.ndarray, y_bass: np.ndarray) -> float:
        """Bassless MR을 1순위로 하여 동적 비트 배열을 추출한다. 실패 시 Bass 트랙으로 Fallback."""
        # 1순위: Bassless MR 기반 온셋 강도 연산
        onset_env = librosa.onset.onset_strength(y=y_bassless, sr=self.sr, hop_length=self.hop_length, aggregate=np.median, fmax=8000)
        
        # 신뢰도 검증 (무음/노이즈 판별)
        if np.max(onset_env) < 0.5:
            print("⚠ [Quantizer] Bassless MR 온셋 에너지가 희박합니다. Bass 트랙 단독 비트 트래킹(Fallback)을 수행합니다.")
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
        """음악적 분절: 동일 피치이며 간격이 50ms 이하인 파편 노트를 병합(Duration 연장)한다."""
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
        """Tempo Map을 참조하여 가장 가까운 로컬 격자 좌표를 반환한다."""
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

        # 1. 노이즈 및 파편화 논리 병합
        merged_events = self._merge_fragmented_notes(events)
        
        quantized = []
        for event in merged_events:
            # 2. 시작점(Onset)과 종료점(Offset) 동적 양자화
            q_onset = self._snap_to_dynamic_grid(event.time)
            q_offset = self._snap_to_dynamic_grid(event.time + event.duration)
            q_duration = max(q_offset - q_onset, 0.01) # 최소 길이 강제 보장
            
            # 절대 그리드 인덱스 매핑 (렌더링 정렬용)
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

        # 3. Monophonic Enforcer (오버랩 충돌 해소 및 절단)
        quantized.sort(key=lambda x: x.quantized_time)
        for i in range(len(quantized) - 1):
            curr = quantized[i]
            nxt = quantized[i + 1]
            
            if curr.quantized_time + curr.quantized_duration > nxt.quantized_time:
                resolved_duration = max(nxt.quantized_time - curr.quantized_time - self.visual_margin, 0.01)
                quantized[i] = curr.update(quantized_duration=resolved_duration)

        return quantized
