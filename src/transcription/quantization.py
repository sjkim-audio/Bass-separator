import numpy as np
import librosa
from typing import List, Optional, Tuple
from src.models.events import NoteEvent

class RhythmicQuantizer:
    # [수정 3] 박자 기호(Time Signature) 파라미터화 (기본값: 4/4박자)
    def __init__(self, sr: int, hop_length: int, time_signature: Tuple[int, int] = (4, 4)):
        self.sr = sr
        self.hop_length = hop_length
        self.time_signature = time_signature
        self.bpm = 0.0
        self.beat_times = np.array([])
        self.visual_margin = 0.01  # 오버랩 커팅 시 여백 (delta = 10ms)

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

    # [수정 5] 3연음(Triplet) 보존을 위한 동적 격자 평가 함수
    def _get_best_subdivision(self, b_start: float, b_end: float, onsets: List[float]) -> int:
        if not onsets:
            return 4  # 기본값: 16분음표 격자
        
        beat_len = b_end - b_start
        
        # N=3 (8분 3연음 격자)의 SSE Cost 계산
        cost_3 = 0.0
        grids_3 = [b_start + (j / 3) * beat_len for j in range(4)]
        for t in onsets:
            cost_3 += min(abs(t - g) for g in grids_3) ** 2
            
        # N=4 (16분음표 격자)의 SSE Cost 계산
        cost_4 = 0.0
        grids_4 = [b_start + (j / 4) * beat_len for j in range(5)]
        for t in onsets:
            cost_4 += min(abs(t - g) for g in grids_4) ** 2
            
        return 3 if cost_3 < cost_4 else 4

    def _snap_time(self, time_sec: float, subdiv: int) -> float:
        if len(self.beat_times) < 2:
            interval = (60.0 / self.bpm) / subdiv if self.bpm > 0 else 0
            return round(time_sec / interval) * interval if interval > 0 else time_sec

        idx = np.searchsorted(self.beat_times, time_sec) - 1
        idx = max(0, min(idx, len(self.beat_times) - 2))
        b_start = self.beat_times[idx]
        beat_len = self.beat_times[idx + 1] - b_start
        
        # [수정 2] 양자화 거리 측정 (1차원 절댓값 최솟값 Q(t))
        grids = [b_start + (j / subdiv) * beat_len for j in range(subdiv + 1)]
        return min(grids, key=lambda g: abs(g - time_sec))

    def quantize_events(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if self.bpm <= 0 or not events:
            return events

        # 박자(Beat)별 최적 격자 해상도 사전 계산
        beat_subdivs = {}
        if len(self.beat_times) >= 2:
            for idx in range(len(self.beat_times) - 1):
                b_start = self.beat_times[idx]
                b_end = self.beat_times[idx + 1]
                onsets_in_beat = [e.time for e in events if b_start <= e.time < b_end]
                beat_subdivs[idx] = self._get_best_subdivision(b_start, b_end, onsets_in_beat)

        pre_quantized = []
        for event in events:
            if len(self.beat_times) >= 2:
                idx = np.searchsorted(self.beat_times, event.time) - 1
                idx = max(0, min(idx, len(self.beat_times) - 2))
                subdiv = beat_subdivs.get(idx, 4)

                b_start = self.beat_times[idx]
                beat_len = self.beat_times[idx + 1] - b_start
                
                q_onset = self._snap_time(event.time, subdiv)
                
                # 시각적 렌더링을 위해 N=3 격자라도 16분음표 기반의 인덱스로 근사 매핑
                sub_idx = round((q_onset - b_start) / (beat_len / subdiv))
                visual_sub_idx = round(sub_idx * (4 / subdiv))
                grid_idx = int(idx * 4 + visual_sub_idx)
            else:
                subdiv = 4
                q_onset = self._snap_time(event.time, subdiv)
                grid_idx = int(np.round(q_onset / ((60.0 / self.bpm) / 4)))

            q_offset = self._snap_time(event.time + event.duration, subdiv)
            q_duration = max(q_offset - q_onset, 0.01)

            pre_quantized.append(event.update(
                grid_index=grid_idx,
                quantized_time=q_onset,
                quantized_duration=q_duration
            ))

        pre_quantized.sort(key=lambda x: x.quantized_time)

        # [수정 4] 템포 의존적 노트 병합 (Grid-based Merging)
        merged_events = []
        curr = pre_quantized[0]
        for nxt in pre_quantized[1:]:
            # 동일 피치 & 동일 격자(Grid Index) 배정 시 기계적 노이즈로 간주하여 병합
            if curr.midi_note == nxt.midi_note and curr.grid_index == nxt.grid_index:
                new_dur = (nxt.quantized_time + nxt.quantized_duration) - curr.quantized_time
                curr = curr.update(quantized_duration=new_dur)
            else:
                merged_events.append(curr)
                curr = nxt
        merged_events.append(curr)

        # [수정 1] 음수 지속시간 버그 방어 및 단선율 강제화 (Overlap Clamp)
        for i in range(len(merged_events) - 1):
            curr = merged_events[i]
            nxt = merged_events[i + 1]
            
            o_i = curr.quantized_time
            e_i = curr.quantized_time + curr.quantized_duration
            o_next = nxt.quantized_time
            
            if e_i > o_next:
                # E'_i = max(O'_i + 0.01, min(E'_i, O'_{i+1} - delta))
                resolved_end = max(o_i + 0.01, min(e_i, o_next - self.visual_margin))
                merged_events[i] = curr.update(quantized_duration=(resolved_end - o_i))

        return merged_events

    def _apply_musical_smoothing(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if not events: return []
        min_threshold = (60.0 / self.bpm) / 8 if self.bpm > 0 else 0.05
        return [e for e in events if e.quantized_duration >= min_threshold]
