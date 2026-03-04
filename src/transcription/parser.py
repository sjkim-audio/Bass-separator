import numpy as np
import librosa
from typing import List, Tuple, Optional
from models.events import NoteEvent

# 오디오 특성(F0)을 도메인 모델(NoteEvent)로 변환하는 파서(Parser) 계층

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

    def parse_f0_to_events(self, f0_array: np.ndarray, min_duration_frames: int = 5, tolerance_frames: int = 3) -> List[NoteEvent]:
        events = []
        frame_time = self.hop_length / self.sr
        current_note = None
        note_start_frame = 0
        blank_counter = 0

        valid_mask = (f0_array > 0) & (~np.isnan(f0_array))
        midi_array = np.full(len(f0_array), np.nan)
        midi_array[valid_mask] = np.round(librosa.hz_to_midi(f0_array[valid_mask]))

        for i, midi_val in enumerate(midi_array):
            if not np.isnan(midi_val):
                midi_note = int(midi_val)
                blank_counter = 0 
                if current_note is None:
                    current_note = midi_note
                    note_start_frame = i
                elif current_note != midi_note:
                    duration = i - note_start_frame
                    if duration >= min_duration_frames:
                        events.append(self._create_event(current_note, note_start_frame * frame_time))
                    current_note = midi_note
                    note_start_frame = i
            else:
                blank_counter += 1
                if current_note is not None and blank_counter >= tolerance_frames:
                    duration = (i - blank_counter) - note_start_frame
                    if duration >= min_duration_frames:
                        events.append(self._create_event(current_note, note_start_frame * frame_time))
                    current_note = None
                    
        if current_note is not None and (len(midi_array) - note_start_frame) >= min_duration_frames:
            events.append(self._create_event(current_note, note_start_frame * frame_time))

        return events

    def _create_event(self, midi_note: int, time_sec: float) -> NoteEvent:
        candidates = self.get_fret_candidates(librosa.midi_to_hz(midi_note))
        pos = self.choose_fret_greedy(candidates)
        if pos:
            return NoteEvent(time=time_sec, midi_note=midi_note, string_idx=pos[0], fret=pos[1])
        return NoteEvent(time=time_sec, midi_note=midi_note)
