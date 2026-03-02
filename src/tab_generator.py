import numpy as np
import librosa
from typing import List, Tuple, Dict, Optional, Any

"""
Automatic Bass Transcription - Tablature Generation Module (Baseline)
이 모듈은 피치 트래킹 결과를 기반으로 가로형 ASCII 타브 악보를 렌더링합니다.
추후 Phase 3(Viterbi HMM)에서 운지법 최적화 디코더가 이 클래스를 확장할 예정입니다.
"""

class BassTabGenerator:
    def __init__(self, sr: int = 16000, hop_length: int = 160):
        # 4현 베이스 표준 튜닝 (E1, A1, D2, G2) - MIDI Note Numbers
        self.tuning: List[int] = [28, 33, 38, 43]
        self.string_names: List[str] = ["E", "A", "D", "G"]

        # Phase 2 파이프라인(CREPE)과 동기화된 해상도
        self.sr = sr
        self.hop_length = hop_length
        
        # 파싱된 노트 이벤트 저장소
        # Format: [{'time': float, 'string_idx': int, 'fret': int, 'midi_note': int}, ...]
        self.events: List[Dict[str, Any]] = []

    def get_fret_candidates(self, hz: float) -> List[Tuple[int, int]]:
        """
        [확장성 설계] 주파수를 받아 가능한 '모든' 운지 위치 반환.
        향후 Viterbi HMM 모델이 이 후보군들을 상태(State) 공간으로 활용합니다.
        """
        if hz is None or hz == 0 or np.isnan(hz):
            return []

        midi_note = int(round(librosa.hz_to_midi(hz)))
        candidates = []

        for string_idx, open_note in enumerate(self.tuning):
            fret = midi_note - open_note
            # 일반적인 베이스 지판 범위 (0 ~ 24프렛)
            if 0 <= fret <= 24:
                candidates.append((string_idx, fret))

        return candidates

    def choose_fret_greedy(self, candidates: List[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        """
        [임시 로직] 가장 낮은 프렛을 우선 선택 (Lowest Fret Priority)
        Viterbi 알고리즘 개발 전까지 사용할 베이스라인 디코더입니다.
        """
        if not candidates:
            return None
        return min(candidates, key=lambda x: x[1])

    def parse_f0_to_events(self, f0_array: np.ndarray, min_duration_frames: int = 5, tolerance_frames: int = 3) -> None:
        """
        [고도화] 상태 머신을 활용한 노트 그룹핑 및 디바운싱 로직.
        - min_duration_frames: 유효한 음표로 인정받기 위한 최소 유지 시간 (예: 5프레임 = 0.05초. 그 미만은 노이즈로 무시)
        - tolerance_frames: 음표 중간에 발생하는 찰나의 NaN(끊김)을 무시하고 음을 이어주는 관용도 (예: 3프레임)
        """
        self.events = []
        frame_time = self.hop_length / self.sr
        
        current_note = None
        note_start_frame = 0
        blank_counter = 0

        # 1. 1차 양자화: 유효한 주파수를 MIDI 정수로 일괄 변환 (NaN은 유지)
        valid_mask = (f0_array > 0) & (~np.isnan(f0_array))
        midi_array = np.full(len(f0_array), np.nan)
        midi_array[valid_mask] = np.round(librosa.hz_to_midi(f0_array[valid_mask]))

        # 2. 상태 머신(State Machine) 순회
        for i, midi_val in enumerate(midi_array):
            is_valid = not np.isnan(midi_val)
            
            if is_valid:
                midi_note = int(midi_val)
                blank_counter = 0  # 유효한 음이 들어오면 결측치 카운터 초기화
                
                if current_note is None:
                    # A. 완전히 새로운 음표의 시작
                    current_note = midi_note
                    note_start_frame = i
                    
                elif current_note != midi_note:
                    # B. 음정이 변경됨 (비브라토 노이즈일 수도 있고 진짜 변경일 수도 있음)
                    duration = i - note_start_frame
                    
                    # 이전 음표가 '최소 유지 시간'을 충족했을 때만 진짜 음표로 등록 (노이즈 필터링)
                    if duration >= min_duration_frames:
                        self._register_event(current_note, note_start_frame * frame_time)
                    
                    # 새로운 음표로 상태 전환
                    current_note = midi_note
                    note_start_frame = i
            else:
                # C. 결측치(NaN) 발생 구역
                blank_counter += 1
                
                # 결측치가 관용도(tolerance)를 초과하면 진짜로 연주가 멈춘 것으로 판단 (Rest)
                if current_note is not None and blank_counter >= tolerance_frames:
                    duration = (i - blank_counter) - note_start_frame
                    
                    if duration >= min_duration_frames:
                        self._register_event(current_note, note_start_frame * frame_time)
                    
                    current_note = None  # 상태 초기화
                    
        # 3. 배열 끝에 도달했을 때 마지막 연주 중이던 음표 처리
        if current_note is not None:
            duration = len(midi_array) - note_start_frame
            if duration >= min_duration_frames:
                self._register_event(current_note, note_start_frame * frame_time)

    def _register_event(self, midi_note: int, time_sec: float) -> None:
        """내부 헬퍼 메서드: 이벤트를 배열에 추가 (임시 운지법 사용)"""
        candidates = self.get_fret_candidates(librosa.midi_to_hz(midi_note))
        pos = self.choose_fret_greedy(candidates)
        
        if pos:
            self.events.append({
                'time': time_sec,
                'string_idx': pos[0],
                'fret': pos[1],
                'midi_note': midi_note
            })
    def display_tab(self, chars_per_line: int = 80) -> None:
        """
        [UI 안정화] 수집된 이벤트를 가로형 텍스트 타브 악보로 출력합니다.
        긴 휴지기(Rest)에 의한 무한 대시(-) 출력 및 화면 찢어짐을 방지합니다.
        """
        if not self.events:
            print("⚠️ 시각화할 노트 이벤트가 없습니다.")
            return

        print("\n🎸 Generated Bass Tab (Standard Tuning G-D-A-E)\n")
        
        # 각 줄의 문자열 버퍼 (위에서부터 G, D, A, E 순서)
        line_buffers = ["G |", "D |", "A |", "E |"]
        last_time = 0.0

        for event in self.events:
            string_idx = event['string_idx']
            fret = event['fret']

            # 리듬 간격 계산 (최소 2칸, 최대 12칸 제한)
            time_diff = event['time'] - last_time
            num_dashes = max(2, min(12, int(time_diff * 10)))
            spacer = "-" * num_dashes

            fret_str = str(fret)
            added_length = len(spacer) + len(fret_str)

            # 한 줄의 최대 길이 초과 시 사전 줄바꿈 (Word Wrap)
            if len(line_buffers[0]) + added_length > chars_per_line:
                self._print_system(line_buffers)
                line_buffers = ["G |", "D |", "A |", "E |"]
                spacer = "-" * 2  # 새 줄의 첫 음표 간격 초기화

            # 4개 현 버퍼 채우기 (타겟 줄에는 프렛 번호, 나머지 줄에는 대시)
            for i in range(4):
                current_string_target = 3 - i
                if current_string_target == string_idx:
                    line_buffers[i] += spacer + fret_str
                else:
                    line_buffers[i] += spacer + ("-" * len(fret_str))

            last_time = event['time']

        # 남은 버퍼 최종 렌더링
        if len(line_buffers[0]) > 3:
            self._print_system(line_buffers)

    def _print_system(self, buffers: List[str]) -> None:
        """4줄 버퍼를 출력하는 내부 유틸리티 메서드"""
        for line in buffers:
            print(line + "-|")
        print("") # 시스템 간 여백
