import numpy as np
import librosa
from typing import List, Optional, Tuple
from src.models.events import NoteEvent

class RhythmicQuantizer:
    def __init__(self, sr: int, hop_length: int, time_signature: Tuple[int, int] = (4, 4)):
        self.sr = sr
        self.hop_length = hop_length
        self.time_signature = time_signature
        self.bpm = 0.0
        self.beat_times = np.array([])
        self.visual_margin = 0.01  
        self.snap_threshold = 0.035 # 35ms: 이 오차 이내일 때만 격자로 끌어당김 (Soft Quantization)

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

    def _get_best_subdivision(self, b_start: float, b_end: float, onsets: List[float]) -> int:
        if not onsets:
            return 4  
        beat_len = b_end - b_start
        cost_3 = sum(min(abs(t - (b_start + (j / 3) * beat_len)) for j in range(4)) ** 2 for t in onsets)
        cost_4 = sum(min(abs(t - (b_start + (j / 4) * beat_len)) for j in range(5)) ** 2 for t in onsets)
        return 3 if cost_3 < cost_4 else 4

    def _snap_time(self, time_sec: float, subdiv: int) -> float:
        if len(self.beat_times) < 2:
            interval = (60.0 / self.bpm) / subdiv if self.bpm > 0 else 0
            if interval == 0: return time_sec
            nearest = round(time_sec / interval) * interval
            # Soft Snapping 적용
            return nearest if abs(time_sec - nearest) <= self.snap_threshold else time_sec

        idx = np.searchsorted(self.beat_times, time_sec) - 1
        idx = max(0, min(idx, len(self.beat_times) - 2))
        b_start = self.beat_times[idx]
        beat_len = self.beat_times[idx + 1] - b_start
        
        grids = [b_start + (j / subdiv) * beat_len for j in range(subdiv + 1)]
        nearest_grid = min(grids, key=lambda g: abs(g - time_sec))
        
        # Soft Snapping: 격자에 충분히 가깝지 않으면 원본 시간 보존 (엇박자, 리듬 왜곡 방지)
        if abs(nearest_grid - time_sec) <= self.snap_threshold:
            return nearest_grid
        return time_sec

    def quantize_events(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if self.bpm <= 0 or not events:
            return events

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
                
                # Visual Grid Index는 별도로 맵핑 유지 (렌더러용)
                nearest_grid = min([b_start + (j / subdiv) * beat_len for j in range(subdiv + 1)], key=lambda g: abs(g - event.time))
                sub_idx = round((nearest_grid - b_start) / (beat_len / subdiv))
                visual_sub_idx = round(sub_idx * (4 / subdiv))
                grid_idx = int(idx * 4 + visual_sub_idx)
            else:
                subdiv = 4
                grid_idx = int(np.round(event.time / ((60.0 / self.bpm) / 4)))

            # 물리적 평가는 Soft Snapping이 적용된 q_onset을 사용
            q_onset = self._snap_time(event.time, subdiv)
            q_offset = self._snap_time(event.time + event.duration, subdiv)
            q_duration = max(q_offset - q_onset, 0.02) # 최소 길이 20ms 보장

            pre_quantized.append(event.update(
                grid_index=grid_idx,
                quantized_time=q_onset,
                quantized_duration=q_duration
            ))

        pre_quantized.sort(key=lambda x: x.quantized_time)

        # 템포 기반이 아닌 '절대적 시간차(Onset Diff)' 기반 노트 병합
        merged_events = []
        curr = pre_quantized[0]
        for nxt in pre_quantized[1:]:
            onset_diff = nxt.quantized_time - curr.quantized_time
            # 같은 피치이고, 간격이 50ms 미만(사람이 물리적으로 두번 튕길 수 없는 속도)일 때만 합침
            if curr.midi_note == nxt.midi_note and onset_diff < 0.05:
                new_dur = (nxt.quantized_time + nxt.quantized_duration) - curr.quantized_time
                curr = curr.update(quantized_duration=new_dur)
            else:
                merged_events.append(curr)
                curr = nxt
        merged_events.append(curr)

        # 서스테인(Sustain) 오버랩 커팅 보정
        for i in range(len(merged_events) - 1):
            curr = merged_events[i]
            nxt = merged_events[i + 1]
            
            o_i = curr.quantized_time
            e_i = curr.quantized_time + curr.quantized_duration
            o_next = nxt.quantized_time
            
            if e_i > o_next:
                resolved_end = max(o_i + 0.02, min(e_i, o_next - self.visual_margin))
                merged_events[i] = curr.update(quantized_duration=(resolved_end - o_i))

        return merged_events

    def _apply_musical_smoothing(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if not events: return []
        min_threshold = (60.0 / self.bpm) / 8 if self.bpm > 0 else 0.05
        return [e for e in events if e.quantized_duration >= min_threshold]
