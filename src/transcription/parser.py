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
        
        # [추가] 피치 이탈(Wobble) 제어 변수
        wobble_note = None
        wobble_counter = 0
        WOBBLE_TOLERANCE_FRAMES = 5  # 50ms 지연 버퍼
        WOBBLE_PITCH_JUMP_THRESHOLD = 3 # 단3도(3반음) 이하의 변동은 슬라이드로 간주하여 버퍼 예외

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
                
                if current_note is None:
                    current_note = midi_note
                    note_start_frame = i
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
                    
                elif current_onset is True:
                    # 명시적 어택 감지 시 버퍼 무시하고 즉시 분할
                    end_idx = i - int(blank_counter) - int(wobble_counter)
                    duration_frames = end_idx - note_start_frame
                    
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                        
                    current_note = midi_note
                    note_start_frame = i
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
                    
                elif midi_note != current_note:
                    # [핵심] 슬라이드/비브라토 보호: 피치 도약이 3반음 이하이면 즉시 분할
                    if abs(midi_note - current_note) <= WOBBLE_PITCH_JUMP_THRESHOLD:
                        end_idx = i - int(blank_counter)
                        duration_frames = end_idx - note_start_frame
                        
                        if duration_frames >= MIN_DURATION_FRAMES:
                            conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                            duration_sec = float(duration_frames * frame_time)
                            comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                            events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                            
                        current_note = midi_note
                        note_start_frame = i
                        wobble_note = None
                        wobble_counter = 0
                        blank_counter = 0
                    else:
                        # 급격한 피치 도약(4반음 이상): 배음 스파이크 의심, 지연 버퍼 가동
                        if wobble_note == midi_note:
                            wobble_counter += 1
                        else:
                            wobble_note = midi_note
                            wobble_counter = 1
                            
                        # 버퍼 임계치 도달 시 새로운 노트로 승인
                        if wobble_counter >= WOBBLE_TOLERANCE_FRAMES:
                            end_idx = i - int(wobble_counter) + 1 - int(blank_counter)
                            duration_frames = end_idx - note_start_frame
                            
                            if duration_frames >= MIN_DURATION_FRAMES:
                                conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                                duration_sec = float(duration_frames * frame_time)
                                comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                                events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                                
                            current_note = wobble_note
                            note_start_frame = i - int(wobble_counter) + 1
                            wobble_note = None
                            wobble_counter = 0
                            blank_counter = 0
                else:
                    # 정상 피치 유지: 찰나의 이탈 기록 초기화
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
            else:
                blank_counter += 1
                wobble_counter = 0  # 신호 단절 시 버퍼도 초기화
                
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
            end_idx = len(midi_array) - int(blank_counter) - int(wobble_counter)
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
