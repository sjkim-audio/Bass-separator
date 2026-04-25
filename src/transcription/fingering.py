import numpy as np
import librosa
from typing import List, Tuple
from src.models.events import NoteEvent

class ViterbiSmartFingering:
    def __init__(self, weight_fret=1.0, weight_string=2.0, shift_threshold=3, shift_penalty=10.0, open_string_penalty=2.5, base_time_penalty=0.5):
        self.w_f = weight_fret
        self.w_s = weight_string
        self.shift_thresh = shift_threshold
        self.shift_penalty = shift_penalty
        self.open_penalty = open_string_penalty
        # [수정 1] 물리적 도약 한계치를 대변하는 시간 가중치 하한선 상수 (k)
        self.base_time_penalty = base_time_penalty 

    def _calculate_transition_cost(self, pos1: Tuple[int, int], pos2: Tuple[int, int], dt: float) -> float:
        s1, f1 = pos1
        s2, f2 = pos2
        safe_dt = max(dt, 0.05)
        
        # [수정 1] 박자가 무한히 길어져도 최소한의 물리적 도약 비용이 발생하도록 하한선 보장
        time_multiplier = (1.0 / safe_dt) + self.base_time_penalty
        
        cost_s = self.w_s * abs(s2 - s1)
        cost_height = 0.5 * f2
        cost_open = self.open_penalty if (f1 != 0 and f2 == 0) else 0.0
        
        cost_f = 0.0
        if f1 == 0 and f2 != 0:
            # [수정 2] Case B (개방현 -> 닫힌 현)
            # 0.5 계수: 왼손이 0프렛에 고정되어 있지 않고 가상의 중립 포지션(로우 프렛)에 
            # 대기하고 있음을 상정한 도메인 휴리스틱 거리 보정
            blind_jump_penalty = max(0, f2 - 7) ** 1.5
            cost_f = self.w_f * ((f2 * 0.5) + blind_jump_penalty) * time_multiplier
            
        elif f1 != 0 and f2 != 0:
            dist_f = abs(f2 - f1)
            cost_f = self.w_f * dist_f * time_multiplier
            if dist_f > self.shift_thresh:
                cost_f += self.shift_penalty * ((dist_f - self.shift_thresh) ** 2) * time_multiplier

        # 동음 유지 보너스 (-2.0) 포함 반환
        return cost_s + cost_height + cost_open + cost_f + (-2.0 if pos1 == pos2 else 0.0)

    # [수정 3] 학술적 명칭 정립: 단순 decode가 아닌 viterbi_decode로 명시
    def viterbi_decode(self, events: List[NoteEvent], get_candidates_fn) -> List[NoteEvent]:
        if not events: return []
        
        # [수정 4] State Space 초기화 및 방출 비용 제약 조건 내재화
        # get_candidates_fn을 통해 추출된 유효한 프렛 위치 집합(C_t)만 상태 공간에 등록됨.
        # 이 집합에 없는 상태는 아예 DP 테이블에 존재하지 않으므로 방출 비용이 무한대가 되는 수학적 제약을 만족함.
        state_sequence = []
        for event in events:
            hz = librosa.midi_to_hz(event.midi_note) if event.midi_note else 0
            candidates = get_candidates_fn(hz)
            state_sequence.append(candidates if candidates else [(0, 0)])

        n_steps = len(state_sequence)
        
        # DP 테이블 및 역추적 테이블 할당
        dp = [np.zeros(len(states)) for states in state_sequence]
        backpointers = [np.zeros(len(states), dtype=int) for states in state_sequence]

        # Forward Pass (순방향 누적 비용 연산)
        for t in range(1, n_steps):
            dt = events[t].time - events[t-1].time
            for curr_idx, curr_state in enumerate(state_sequence[t]):
                costs = [dp[t-1][p_idx] + self._calculate_transition_cost(p_state, curr_state, dt)
                         for p_idx, p_state in enumerate(state_sequence[t-1])]
                dp[t][curr_idx] = np.min(costs)
                backpointers[t][curr_idx] = np.argmin(costs)

        # Backward Pass (역추적을 통한 전역 최적해 복원)
        curr_idx = int(np.argmin(dp[-1]))
        best_path = [curr_idx]
        for t in range(n_steps - 1, 0, -1):
            curr_idx = backpointers[t][curr_idx]
            best_path.append(curr_idx)
        best_path.reverse()

        # 새로운 객체를 생성하여 반환 (불변성 유지)
        return [
            event.update(string_idx=state_sequence[t][best_path[t]][0], fret=state_sequence[t][best_path[t]][1])
            for t, event in enumerate(events)
        ]
