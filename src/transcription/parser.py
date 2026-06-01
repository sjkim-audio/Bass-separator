import numpy as np
import librosa
from typing import List, Tuple, Optional
from src.models.events import NoteEvent

class PitchParser:
    def __init__(self, sr: int = 16000, hop_length: int = 160):
        self.sr = sr
        self.hop_length = hop_length
        self.tuning: List[int] = [28, 33, 38, 43] # E, A, D, G

    def get_fret_candidates(self, hz: float) -> List[Tuple[int, int]]:
        if hz <= 0 or np.isnan(hz):
            return []
        midi_note = int(round(librosa.hz_to_midi(hz)))
        return [(i, midi_note - start) for i, start in enumerate(self.tuning) if 0 <= midi_note - start <= 24]

    def choose_fret_greedy(self, candidates: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        if not candidates: return None
        return min(candidates, key=lambda x: x[1])

    def parse_f0_to_events(self, f0_array: np.ndarray, confidence_array: np.ndarray, onset_mask: np.ndarray) -> List[NoteEvent]:
        events = []
        frame_time = self.hop_length / self.sr
        current_note = None
        note_start_frame = 0
        blank_counter = 0

        # [공학적 조율]
        # MIN_DURATION_FRAMES: 7 (70ms) 유지. 슬라이드 시 발생하는 띠리링(Fragmentation) 현상 방어선.
        # TOLERANCE_FRAMES: 15.0 (150ms)로 상향. 서스테인 끝자락의 신뢰도 하락 구간을 관성으로 버티게 함.
        # RETRIGGER_CONF_THRESH: 0.6으로 상향. 동일 피치 연타 시 발생하는 미세한 신뢰도 균열을 좀 더 예민하게 포착.
        # 기존 설정값 유지 (결함이 있는 RETRIGGER 관련 변수 삭제)
        MIN_DURATION_FRAMES = 7
        TOLERANCE_FRAMES = 15.0
        LATENCY_COMP_SEC = 0.005

        valid_mask = (f0_array > 0) & (~np.isnan(f0_array))
        midi_array = np.full(len(f0_array), np.nan)
        midi_array[valid_mask] = np.round(librosa.hz_to_midi(f0_array[valid_mask]))

        for i, midi_val in enumerate(midi_array):
            current_onset = onset_mask[i]
            
            if not np.isnan(midi_val):
                midi_note = int(midi_val)
                conf_val = confidence_array[i]
                
                # [수정 사항 1] 여기서 blank_counter = 0을 실행하던 것을 삭제
                
                if current_note is None:
                    current_note = midi_note
                    note_start_frame = i
                    
                # 피치 변경 또는 Onset 감지 시 노트 분할
                elif (current_note != midi_note) or (current_onset is True):
                    # [수정 사항 2] 누적된 무음(blank_counter) 구간을 빼고 정확한 종료 시점(end_idx) 도출
                    end_idx = i - int(blank_counter)
                    duration_frames = end_idx - note_start_frame
                    
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                    
                    current_note = midi_note
                    note_start_frame = i
                
                # [수정 사항 3] 노트 증발의 원흉인 RETRIGGER_CONF_THRESH(신뢰도 기반 컷오프) 블록 완전 삭제
                
                # [수정 사항 4] 이전 노트 길이에 대한 모든 논리 판정이 끝난 후 안전하게 무음 카운터 리셋
                blank_counter = 0 
                
            else:
                blank_counter += 1
                if current_note is not None and blank_counter >= TOLERANCE_FRAMES:
                    end_idx = i - int(blank_counter)
                    duration_frames = end_idx - note_start_frame
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf = float(np.mean(confidence_array[note_start_frame:end_idx]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(self._create_event(current_note, comp_start_time, duration_sec, conf))
                    current_note = None
                    
        if current_note is not None:
            end_idx = len(midi_array)
            duration_frames = end_idx - note_start_frame
            if duration_frames >= MIN_DURATION_FRAMES:
                conf = float(np.mean(confidence_array[note_start_frame:end_idx]))
                duration_sec = float(duration_frames * frame_time)
                comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                events.append(self._create_event(current_note, comp_start_time, duration_sec, conf))

        events = self._post_process_garbage_pitch(events)
        return events

    def _create_event(self, midi_note: int, time_sec: float, duration_sec: float, confidence: float) -> NoteEvent:
        candidates = self.get_fret_candidates(librosa.midi_to_hz(midi_note))
        pos = self.choose_fret_greedy(candidates)
        if pos:
            return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, string_idx=pos[0], fret=pos[1], confidence=confidence)
        return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, confidence=confidence)

    def _post_process_garbage_pitch(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if not events: return []
        working_events = events.copy()
        cleaned_events = []
        i = 0
        while i < len(working_events) - 1:
            curr_note = working_events[i]
            next_note = working_events[i+1]
            gap = next_note.time - (curr_note.time + curr_note.duration)
            if curr_note.duration <= 0.06 and gap <= 0.04 and abs(curr_note.midi_note - next_note.midi_note) >= 5:
                adjusted_next_note = next_note.update(
                    time=curr_note.time,  
                    duration=next_note.duration + (next_note.time - curr_note.time)
                )
                working_events[i+1] = adjusted_next_note
                i += 1
                continue
            cleaned_events.append(curr_note)
            i += 1
        if i == len(working_events) - 1:
            cleaned_events.append(working_events[-1])
        return cleaned_events
