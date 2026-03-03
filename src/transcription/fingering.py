import numpy as np
import librosa
from typing import List, Tuple, Dict, Any

class ViterbiSmartFingering:
    def __init__(self, weight_fret=1.0, weight_string=2.0, shift_threshold=3, 
                 shift_penalty=10.0, open_string_penalty=2.5):
        self.w_f = weight_fret
        self.w_s = weight_string
        self.shift_thresh = shift_threshold
        self.shift_penalty = shift_penalty
        self.open_penalty = open_string_penalty

    def _calculate_transition_cost(self, pos1: Tuple[int, int], pos2: Tuple[int, int], dt: float) -> float:
        s1, f1 = pos1
        s2, f2 = pos2
        safe_dt = max(dt, 0.05)
        time_multiplier = 1.0 / safe_dt
        
        cost_s = self.w_s * abs(s2 - s1)
        cost_height = 0.5 * f2
        cost_open = self.open_penalty if (f1 != 0 and f2 == 0) else 0.0
        
        cost_f = 0.0
        if f1 == 0 and f2 != 0:
            cost_f = self.w_f * f2 * 0.5 * time_multiplier
        elif f1 != 0 and f2 != 0:
            dist_f = abs(f2 - f1)
            cost_f = self.w_f * dist_f * time_multiplier
            if dist_f > self.shift_thresh:
                cost_f += self.shift_penalty * ((dist_f - self.shift_thresh) ** 2) * time_multiplier

        return cost_s + cost_height + cost_open + cost_f + (-2.0 if pos1 == pos2 else 0.0)

    def decode(self, events: List[Dict[str, Any]], get_candidates_fn) -> List[Dict[str, Any]]:
        if not events: return []
        state_sequence = []
        for event in events:
            hz = librosa.midi_to_hz(event['midi_note']) if event['midi_note'] else 0
            candidates = get_candidates_fn(hz) or [(0, 0)]
            state_sequence.append(candidates)

        n_steps = len(state_sequence)
        dp = [np.zeros(len(states)) for states in state_sequence]
        backpointers = [np.zeros(len(states), dtype=int) for states in state_sequence]

        for t in range(1, n_steps):
            dt = events[t]['time'] - events[t-1]['time']
            for curr_idx, curr_state in enumerate(state_sequence[t]):
                costs = [dp[t-1][p_idx] + self._calculate_transition_cost(p_state, curr_state, dt)
                         for p_idx, p_state in enumerate(state_sequence[t-1])]
                dp[t][curr_idx] = np.min(costs)
                backpointers[t][curr_idx] = np.argmin(costs)

        curr_idx = np.argmin(dp[-1])
        for t in range(n_steps - 1, -1, -1):
            s_idx, f_idx = state_sequence[t][curr_idx]
            events[t].update({'string_idx': s_idx, 'fret': f_idx})
            curr_idx = backpointers[t][curr_idx]
        return events
