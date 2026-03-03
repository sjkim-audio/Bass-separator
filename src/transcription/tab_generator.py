import numpy as np
import librosa
from typing import List, Tuple, Dict, Optional, Any
from .fingering import ViterbiSmartFingering
from .quantization import RhythmicQuantizer

class BassTabGenerator:
    def __init__(self, sr: int = 16000, hop_length: int = 160):
        self.tuning = [28, 33, 38, 43]
        self.sr, self.hop_length = sr, hop_length
        self.events: List[Dict[str, Any]] = []
        self.quantizer: Optional[RhythmicQuantizer] = None

    def get_fret_candidates(self, hz: float) -> List[Tuple[int, int]]:
        if hz <= 0 or np.isnan(hz): return []
        midi_note = int(round(librosa.hz_to_midi(hz)))
        return [(i, midi_note - start) for i, start in enumerate(self.tuning) if 0 <= midi_note - start <= 24]

    def parse_f0_to_events(self, f0_array: np.ndarray, min_duration_frames=5, tolerance_frames=3):
        self.events = []
        frame_time = self.hop_length / self.sr
        # ... (기존 State Machine 기반 파싱 로직) ...
        # (생략: 기존 코드와 로직 동일)
        pass

    def _register_event(self, midi_note: int, time_sec: float):
        candidates = self.get_fret_candidates(librosa.midi_to_hz(midi_note))
        if candidates:
            best = min(candidates, key=lambda x: x[1])
            self.events.append({'time': time_sec, 'string_idx': best[0], 'fret': best[1], 'midi_note': midi_note})

    def optimize_fingering(self, **kwargs):
        decoder = ViterbiSmartFingering(**kwargs)
        self.events = decoder.decode(self.events, self.get_fret_candidates)

    def process_quantization(self, audio_y: np.ndarray):
        self.quantizer = RhythmicQuantizer(self.sr, self.hop_length)
        self.quantizer.estimate_bpm_and_grid(audio_y)
        self.events = self.quantizer.quantize_events(self.events)

    def render_tab(self, mode='quantized', **kwargs):
        # 시각화 로직 호출 (mode에 따라 분기)
        if mode == 'quantized':
            self._display_quantized_tab(**kwargs)
        else:
            self._display_physical_tab(**kwargs)

    def display_tab(self, chars_per_line: int = 80) -> None:
        if not self.events:
            print("⚠️ 시각화할 노트 이벤트가 없습니다.")
            return
        print("\n🎸 Generated Bass Tab (Physical Time Proportional)\n")
        line_buffers = ["G |", "D |", "A |", "E |"]
        last_time = 0.0
        for event in self.events:
            string_idx = event['string_idx']
            fret = event['fret']
            time_diff = event['time'] - last_time
            num_dashes = max(2, min(12, int(time_diff * 10)))
            spacer = "-" * num_dashes
            fret_str = str(fret)
            added_length = len(spacer) + len(fret_str)
            if len(line_buffers[0]) + added_length > chars_per_line:
                self._print_system(line_buffers)
                line_buffers = ["G |", "D |", "A |", "E |"]
                spacer = "-" * 2  
            for i in range(4):
                current_string_target = 3 - i
                if current_string_target == string_idx:
                    line_buffers[i] += spacer + fret_str
                else:
                    line_buffers[i] += spacer + ("-" * len(fret_str))
            last_time = event['time']
        if len(line_buffers[0]) > 3:
            self._print_system(line_buffers)

    def display_quantized_tab(self, measures_per_line: int = 4) -> None:
        if not self.events or 'grid_index' not in self.events[0]:
            print("⚠️ 양자화된 데이터가 없습니다. process_quantization을 먼저 실행하세요.")
            return
        bpm = self.quantizer.bpm if self.quantizer else 0.0
        print(f"\n🎸 Quantized Bass Tab (BPM: {bpm:.0f})\n")
        grids_per_measure = 16
        max_grid = max(e['grid_index'] for e in self.events)
        total_measures = (max_grid // grids_per_measure) + 1
        event_dict = {e['grid_index']: e for e in self.events}
        
        for measure_group in range(0, total_measures, measures_per_line):
            line_buffers = ["G |", "D |", "A |", "E |"]
            for m in range(measures_per_line):
                current_measure = measure_group + m
                if current_measure >= total_measures:
                    break
                for step in range(grids_per_measure):
                    global_grid = (current_measure * grids_per_measure) + step
                    event = event_dict.get(global_grid)
                    for string_idx in range(4):
                        target_string = 3 - string_idx
                        if event and event['string_idx'] == target_string:
                            fret_str = f"{event['fret']}"
                            line_buffers[string_idx] += f"{fret_str.ljust(2, '-')}-"
                        else:
                            line_buffers[string_idx] += "---"
                for i in range(4):
                    line_buffers[i] += "|"
            self._print_system(line_buffers)

    def _print_system(self, buffers: List[str]) -> None:
        for line in buffers:
            print(line)
        print("")


