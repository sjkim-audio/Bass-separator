import numpy as np
import librosa
from typing import List, Tuple, Optional
from src.models.events import NoteEvent

class PitchParser:
    def __init__(self, sr: int = 16000, hop_length: int = 160):
        self.sr = sr
        self.hop_length = hop_length
        self.tuning_map: List[Tuple[int, int]] = [
            (0, 23), (1, 28), (2, 33), (3, 38), (4, 43)
        ]
        self.is_5_string = False

    def _get_candidates_by_midi(self, midi_note: int) -> List[Tuple[int, int]]:
        candidates = []
        for s_idx, start_midi in self.tuning_map:
            if not self.is_5_string and s_idx == 0:
                continue
            fret = midi_note - start_midi
            if 0 <= fret <= 24:
                candidates.append((s_idx, fret))
        return candidates

    def get_fret_candidates(self, hz: float) -> List[Tuple[int, int]]:
        if hz <= 0 or np.isnan(hz):
            return []
        midi_note = int(round(librosa.hz_to_midi(hz)))
        return self._get_candidates_by_midi(midi_note)

    def choose_fret_greedy(self, candidates: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        if not candidates:
            return None
        return min(candidates, key=lambda x: x[1])

    def parse_f0_to_events(self, f0_array: np.ndarray, confidence_array: np.ndarray, onset_mask: np.ndarray) -> List[NoteEvent]:
        valid_mask = (f0_array > 0) & (~np.isnan(f0_array))
        midi_array = np.full(len(f0_array), np.nan)
        midi_array[valid_mask] = np.round(librosa.hz_to_midi(f0_array[valid_mask]))

        events = []
        frame_time = self.hop_length / self.sr
        
        current_note = None
        note_start_frame = 0
        blank_counter = 0
        
        wobble_note = None
        wobble_counter = 0
        WOBBLE_TOLERANCE_FRAMES = 5  
        # 완전5도(7반음) 이하의 변동은 정상 연주(스케일 이동)로 승인하여 버퍼 우회
        WOBBLE_PITCH_JUMP_THRESHOLD = 7 

        MIN_DURATION_FRAMES = 7
        TOLERANCE_FRAMES = 15.0
        LATENCY_COMP_SEC = 0.005

        for i, midi_val in enumerate(midi_array):
            current_onset = onset_mask[i]
            
            if not np.isnan(midi_val):
                midi_note = int(midi_val)
                
                if current_note is None:
                    current_note = midi_note
                    note_start_frame = i
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
                    
                elif current_onset is True:
                    end_idx = i - int(blank_counter) - int(wobble_counter)
                    duration_frames = end_idx - note_start_frame
                    
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(NoteEvent(time=comp_start_time, duration=duration_sec, midi_note=current_note, confidence=conf_avg))
                        
                    current_note = midi_note
                    note_start_frame = i
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
                    
                elif midi_note != current_note:
                    if abs(midi_note - current_note) <= WOBBLE_PITCH_JUMP_THRESHOLD:
                        end_idx = i - int(blank_counter)
                        duration_frames = end_idx - note_start_frame
                        
                        if duration_frames >= MIN_DURATION_FRAMES:
                            conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                            duration_sec = float(duration_frames * frame_time)
                            comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                            events.append(NoteEvent(time=comp_start_time, duration=duration_sec, midi_note=current_note, confidence=conf_avg))
                            
                        current_note = midi_note
                        note_start_frame = i
                        wobble_note = None
                        wobble_counter = 0
                        blank_counter = 0
                    else:
                        if wobble_note == midi_note:
                            wobble_counter += 1
                        else:
                            wobble_note = midi_note
                            wobble_counter = 1
                            
                        if wobble_counter >= WOBBLE_TOLERANCE_FRAMES:
                            end_idx = i - int(wobble_counter) + 1 - int(blank_counter)
                            duration_frames = end_idx - note_start_frame
                            
                            if duration_frames >= MIN_DURATION_FRAMES:
                                conf_avg = float(np.mean(confidence_array[note_start_frame:end_idx]))
                                duration_sec = float(duration_frames * frame_time)
                                comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                                events.append(NoteEvent(time=comp_start_time, duration=duration_sec, midi_note=current_note, confidence=conf_avg))
                                
                            current_note = wobble_note
                            note_start_frame = i - int(wobble_counter) + 1
                            wobble_note = None
                            wobble_counter = 0
                            blank_counter = 0
                else:
                    wobble_note = None
                    wobble_counter = 0
                    blank_counter = 0
            else:
                blank_counter += 1
                wobble_counter = 0  
                
                if current_note is not None and blank_counter >= TOLERANCE_FRAMES:
                    end_idx = i - int(blank_counter)
                    duration_frames = end_idx - note_start_frame
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf = float(np.mean(confidence_array[note_start_frame:end_idx]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(NoteEvent(time=comp_start_time, duration=duration_sec, midi_note=current_note, confidence=conf))
                    current_note = None
                    
        if current_note is not None:
            end_idx = len(midi_array) - int(blank_counter) - int(wobble_counter)
            duration_frames = end_idx - note_start_frame
            if duration_frames >= MIN_DURATION_FRAMES:
                conf = float(np.mean(confidence_array[note_start_frame:end_idx]))
                duration_sec = float(duration_frames * frame_time)
                comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                events.append(NoteEvent(time=comp_start_time, duration=duration_sec, midi_note=current_note, confidence=conf))

        events = self._post_process_garbage_pitch(events)

        # [Fix] 디바운싱 및 가비지 피치 제거를 통과한 유효 노트 기준으로 5현 베이스 여부 최종 판별
        self.is_5_string = any(23 <= e.midi_note < 28 and e.confidence > 0.5 for e in events)

        # 확정된 튜닝 기준(4현/5현)으로 초기 Fallback 운지(Greedy) 일괄 할당
        events = [self._assign_greedy_fret(e) for e in events]
        return events

    def _assign_greedy_fret(self, event: NoteEvent) -> NoteEvent:
        candidates = self._get_candidates_by_midi(event.midi_note)
        pos = self.choose_fret_greedy(candidates)
        if pos:
            return event.update(string_idx=pos[0], fret=pos[1])
        return event

    def _create_event(self, midi_note: int, time_sec: float, duration_sec: float, confidence: float) -> NoteEvent:
        candidates = self._get_candidates_by_midi(midi_note)
        pos = self.choose_fret_greedy(candidates)
        if pos:
            return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, string_idx=pos[0], fret=pos[1], confidence=confidence)
        return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, confidence=confidence)

    def _post_process_garbage_pitch(self, events: List[NoteEvent]) -> List[NoteEvent]:
        if not events:
            return []
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
