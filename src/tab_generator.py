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

    def parse_f0_to_events(self, f0_array: np.ndarray) -> None:
        """
        [성능 최적화] 정제 완료된 f0_array의 변화량만 추적하여 노트를 파싱합니다.
        주의: 현재 로직은 쉼표(NaN) 없이 동일한 음이 연속 연주될 경우 하나의 긴 음으로 병합됩니다.
             (추후 Phase 3의 Note Quantization 단계에서 해결 예정)
        """
        self.events = []
        frame_time = self.hop_length / self.sr
        current_note = None

        for i, hz in enumerate(f0_array):
            is_valid = (not np.isnan(hz)) and (hz > 0)
            midi_note = int(round(librosa.hz_to_midi(hz))) if is_valid else None

            # 새로운 노트 시작점 감지
            if is_valid and midi_note != current_note:
                candidates = self.get_fret_candidates(hz)
                pos = self.choose_fret_greedy(candidates)

                if pos:
                    self.events.append({
                        'time': i * frame_time,
                        'string_idx': pos[0],
                        'fret': pos[1],
                        'midi_note': midi_note
                    })
                current_note = midi_note

            # 음이 끊기면 현재 노트 초기화 (다음 노트 어택을 잡기 위함)
            elif not is_valid:
                current_note = None

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
