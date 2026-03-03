import numpy as np
import librosa
from typing import List, Tuple, Dict, Optional, Any

class ViterbiSmartFingering:
    def __init__(self,
                 weight_fret: float = 1.0,
                 weight_string: float = 2.0,
                 shift_threshold: int = 3,
                 shift_penalty: float = 10.0,
                 open_string_penalty: float = 2.5):
        """
        시간 제약 및 톤 일관성이 추가된 Advanced Viterbi 디코더
        """
        self.w_f = weight_fret
        self.w_s = weight_string
        self.shift_thresh = shift_threshold
        self.shift_penalty = shift_penalty
        self.open_penalty = open_string_penalty

    def _calculate_transition_cost(self, pos1: Tuple[int, int], pos2: Tuple[int, int], dt: float) -> float:
        s1, f1 = pos1
        s2, f2 = pos2

        # 시간 가중치 계산 (최소 0.05초 보장)
        safe_dt = max(dt, 0.05)
        time_multiplier = 1.0 / safe_dt

        # 1. 수직 이동 비용 (줄 넘나들기)
        cost_s = self.w_s * abs(s2 - s1)

        # 2. 하이 프렛 자체 페널티 (Fret Height Penalty)
        cost_height = 0.5 * f2

        # 3. 개방현 관련 및 수평 이동 비용 계산
        cost_open = 0.0
        cost_f = 0.0

        if f1 == 0 and f2 != 0:
            # 개방현에서 닫힌 현으로 이동: 도착 프렛(f2)에 비례하는 거리를 가상으로 계산
            cost_f = self.w_f * f2 * 0.5 * time_multiplier

        elif f1 != 0 and f2 == 0:
            # 닫힌 현에서 개방현으로 진입 (톤 변화 이질감 페널티)
            cost_open = self.open_penalty

        elif f1 != 0 and f2 != 0:
            # 일반적인 프렛 이동
            dist_f = abs(f2 - f1)
            cost_f = self.w_f * dist_f * time_multiplier

            # 손가락 커버 범위를 벗어나는 포지션 이동 시 기하급수적 페널티
            if dist_f > self.shift_thresh:
                cost_f += self.shift_penalty * ((dist_f - self.shift_thresh) ** 2) * time_multiplier

        # 4. 동음 유지 보너스 (플래핑 억제)
        cost_stay = -2.0 if pos1 == pos2 else 0.0

        return cost_s + cost_height + cost_open + cost_f + cost_stay

    def decode(self, events: List[Dict[str, Any]], get_candidates_fn) -> List[Dict[str, Any]]:
        if not events:
            return []

        # 1. State Space 구성
        state_sequence = []
        for event in events:
            hz = librosa.midi_to_hz(event['midi_note']) if event['midi_note'] else 0
            candidates = get_candidates_fn(hz)
            if not candidates:
                candidates = [(0, 0)]
            state_sequence.append(candidates)

        n_steps = len(state_sequence)

        # 2. DP 테이블 초기화
        dp = [np.zeros(len(states)) for states in state_sequence]
        backpointers = [np.zeros(len(states), dtype=int) for states in state_sequence]

        # 3. Forward Pass
        for t in range(1, n_steps):
            prev_states = state_sequence[t-1]
            curr_states = state_sequence[t]

            # 두 노트 사이의 시간 계산 (단위: 초)
            dt = events[t]['time'] - events[t-1]['time']

            for curr_idx, curr_state in enumerate(curr_states):
                min_cost = float('inf')
                best_prev_idx = -1

                for prev_idx, prev_state in enumerate(prev_states):
                    trans_cost = self._calculate_transition_cost(prev_state, curr_state, dt)
                    total_cost = dp[t-1][prev_idx] + trans_cost

                    if total_cost < min_cost:
                        min_cost = total_cost
                        best_prev_idx = prev_idx

                dp[t][curr_idx] = min_cost
                backpointers[t][curr_idx] = best_prev_idx

        # 4. Backward Pass
        best_last_idx = int(np.argmin(dp[-1]))
        best_path_indices = [best_last_idx]

        for t in range(n_steps - 1, 0, -1):
            best_idx = backpointers[t][best_path_indices[-1]]
            best_path_indices.append(best_idx)

        best_path_indices.reverse()

        # 5. 최적화 결과 병합
        optimized_events = []
        for t, event in enumerate(events):
            opt_string, opt_fret = state_sequence[t][best_path_indices[t]]
            opt_event = event.copy()
            opt_event['string_idx'] = opt_string
            opt_event['fret'] = opt_fret
            optimized_events.append(opt_event)

        return optimized_events


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
        if not candidates:
            return None
        return min(candidates, key=lambda x: x[1])

    def parse_f0_to_events(self, f0_array: np.ndarray, min_duration_frames: int = 5, tolerance_frames: int = 3) -> None:
        """
        [고도화] 상태 머신을 활용한 노트 그룹핑 및 디바운싱 로직.
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
                    # B. 음정이 변경됨
                    duration = i - note_start_frame
                    
                    if duration >= min_duration_frames:
                        self._register_event(current_note, note_start_frame * frame_time)
                    
                    current_note = midi_note
                    note_start_frame = i
            else:
                # C. 결측치(NaN) 발생 구역
                blank_counter += 1
                
                if current_note is not None and blank_counter >= tolerance_frames:
                    duration = (i - blank_counter) - note_start_frame
                    
                    if duration >= min_duration_frames:
                        self._register_event(current_note, note_start_frame * frame_time)
                    
                    current_note = None
                    
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
                spacer = "-" * 2  

            # 4개 현 버퍼 채우기
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
        for line in buffers:
            print(line + "-|")
        print("")

    def optimize_fingering(self, 
                           weight_fret: float = 1.0, 
                           weight_string: float = 2.0, 
                           shift_threshold: int = 3, 
                           shift_penalty: float = 10.0,
                           open_string_penalty: float = 2.5) -> None:
        """
        내부 events 배열을 Viterbi 알고리즘을 사용해 최적화된 운지로 덮어씁니다.
        """
        if not self.events:
            print("⚠️ 최적화할 이벤트가 없습니다. 먼저 parse_f0_to_events를 실행하세요.")
            return
            
        decoder = ViterbiSmartFingering(
            weight_fret=weight_fret,
            weight_string=weight_string,
            shift_threshold=shift_threshold,
            shift_penalty=shift_penalty,
            open_string_penalty=open_string_penalty
        )
        
        # 최적화 수행 및 내부 상태 업데이트
        self.events = decoder.decode(self.events, self.get_fret_candidates)
        print("✅ Viterbi 운지법 최적화 완료.")
