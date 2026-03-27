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

    # 🔴 [Phase 6 Tuning] onset_mask 추가, Golden State 파라미터 이식 🔴
    def parse_f0_to_events(self, f0_array: np.ndarray, confidence_array: np.ndarray, onset_mask: np.ndarray) -> List[NoteEvent]:
        events = []
        frame_time = self.hop_length / self.sr
        current_note = None
        note_start_frame = 0
        blank_counter = 0

        # [Test 9 Golden State] 파라미터 하드코딩 또는 기본값 설정
        MIN_DURATION_FRAMES = 7
        TOLERANCE_FRAMES = 6.5
        LATENCY_COMP_SEC = 0.005
        RETRIGGER_CONF_THRESH = 0.5 

        valid_mask = (f0_array > 0) & (~np.isnan(f0_array))
        midi_array = np.full(len(f0_array), np.nan)
        midi_array[valid_mask] = np.round(librosa.hz_to_midi(f0_array[valid_mask]))

        for i, midi_val in enumerate(midi_array):
            current_onset = onset_mask[i]
            
            if not np.isnan(midi_val):
                midi_note = int(midi_val)
                conf_val = confidence_array[i]
                blank_counter = 0 
                
                if current_note is None:
                    current_note = midi_note
                    note_start_frame = i
                    
                # 🔴 [기능 추가] 피치 변경 또는 Onset 감지 시 즉시 분할
                elif (current_note != midi_note) or (current_onset is True):
                    duration_frames = i - note_start_frame
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf_avg = float(np.mean(confidence_array[note_start_frame:i]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                    current_note = midi_note
                    note_start_frame = i
                    
                # 🔴 [기능 추가] 피치가 같더라도 신뢰도가 하락하면 강제 분할
                elif (conf_val < RETRIGGER_CONF_THRESH):
                    duration_frames = i - note_start_frame
                    if duration_frames >= MIN_DURATION_FRAMES:
                        conf_avg = float(np.mean(confidence_array[note_start_frame:i]))
                        duration_sec = float(duration_frames * frame_time)
                        comp_start_time = max(0, (note_start_frame * frame_time) - LATENCY_COMP_SEC)
                        events.append(self._create_event(current_note, comp_start_time, duration_sec, conf_avg))
                    # 신뢰도 하락 구간은 노이즈이므로 대기 상태(None)로 진입
                    current_note = None
                    
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

        # 🔴 [기능 추가] Test 11: 플럭 주법 노이즈(Double-Triggering) 필터링
        events = self._post_process_garbage_pitch(events)

        return events

    def _create_event(self, midi_note: int, time_sec: float, duration_sec: float, confidence: float) -> NoteEvent:
        candidates = self.get_fret_candidates(librosa.midi_to_hz(midi_note))
        pos = self.choose_fret_greedy(candidates)
        if pos:
            return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, string_idx=pos[0], fret=pos[1], confidence=confidence)
        return NoteEvent(time=time_sec, duration=duration_sec, midi_note=midi_note, confidence=confidence)

    # -----------------------------------------------------------------
    # 🔴 [신설] MIDI Post-Processing Module (Test 11 로직) 🔴
    # -----------------------------------------------------------------
    def _post_process_garbage_pitch(self, events: List[NoteEvent]) -> List[NoteEvent]:
        """
        슬랩 팝(Pop) 타격 시 발생하는 짧은 옥타브 쓰레기 노트를 식별하여 
        삭제하고, 진짜 노트의 어택 타이밍을 보정하는 기호 영역 필터.
        """
        if not events: 
            return []
            
        cleaned_events = []
        i = 0
        
        while i < len(events) - 1:
            curr_note = events[i]
            next_note = events[i+1]
            
            gap = next_note.time - (curr_note.time + curr_note.duration)

            # Rule: 60ms 이하의 짧은 노트, 간격 40ms 이하, 5반음 이상의 급격한 피치 변화
            if curr_note.duration <= 0.06 and gap <= 0.04 and abs(curr_note.midi_note - next_note.midi_note) >= 5:
                # "띠" 노트를 건너뛰고 "딩" 노트의 시작점을 당겨줌
                adjusted_next_note = NoteEvent(
                    time=curr_note.time,  
                    duration=next_note.duration + (next_note.time - curr_note.time),
                    midi_note=next_note.midi_note,
                    string_idx=next_note.string_idx, # 기존 핑거링 정보 보존
                    fret=next_note.fret,
                    confidence=next_note.confidence
                )
                events[i+1] = adjusted_next_note
                i += 1
                continue

            cleaned_events.append(curr_note)
            i += 1
            
        if i == len(events) - 1:
            cleaned_events.append(events[i])
            
        return cleaned_events
