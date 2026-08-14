import numpy as np
import librosa
from typing import List, Tuple
from src.models.events import NoteEvent

class ViterbiSmartFingering:
    def __init__(
        self, 
        weight_fret: float = 1.0, 
        weight_string: float = 1.8, 
        weight_high_fret: float = 0.5,
        weight_stay: float = 2.5,
        block_span: int = 3,            
        block_discount: float = 0.3,    
        shift_threshold: int = 4, 
        shift_penalty: float = 6.0, 
        open_string_penalty: float = 2.0, 
        base_time_penalty: float = 0.1
    ):
        self.w_f = weight_fret
        self.w_s = weight_string
        self.w_high_fret = weight_high_fret
        self.w_stay = weight_stay
        self.block_span = block_span
        self.block_discount = block_discount
        self.shift_thresh = shift_threshold
        self.shift_penalty = shift_penalty
        self.open_penalty = open_string_penalty
        self.base_time_penalty = base_time_penalty

    def _calculate_transition_cost(self, pos1: Tuple[int, int], pos2: Tuple[int, int], dt: float) -> float:
        s1, f1 = pos1
        s2, f2 = pos2
        safe_dt = max(dt, 0.05)
        
        time_multiplier = (1.0 / safe_dt) + self.base_time_penalty
        
        cost_f = 0.0
        cost_s = self.w_s * abs(s2 - s1)

        if f1 != 0 and f2 != 0:
            dist_f = abs(f2 - f1)
            dist_s = abs(s2 - s1)
            
            cost_f = self.w_f * dist_f
            
            if (dist_s == 2 and dist_f == 2) or (dist_s == 1 and dist_f == 2):
                cost_s *= 0.3
                cost_f *= 0.5
            
            elif dist_f <= self.block_span:
                cost_f *= self.block_discount  
                cost_s *= 0.8                  
            
            else:
                if dist_f > self.shift_thresh:
                    cost_f += self.shift_penalty * ((dist_f - self.shift_thresh) ** 1.5)

        physical_move_cost = (cost_f * time_multiplier) + (cost_s * np.sqrt(time_multiplier))
        
        cost_open = 0.0
        if f1 != 0 and f2 == 0:
            cost_open = self.open_penalty
        elif f1 == 0 and f2 != 0:
            flight_urgency = 1.0 / safe_dt
            cost_open = max(0, f2 - 5) * 0.2 * flight_urgency

        cost_height = max(0, f2 - 12) * self.w_high_fret
        cost_stay = -self.w_stay if pos1 == pos2 else 0.0

        return physical_move_cost + cost_open + cost_height + cost_stay

    def viterbi_decode(self, events: List[NoteEvent], get_candidates_fn) -> List[NoteEvent]:
        if not events: return []
        
        state_sequence = []
        for event in events:
            midi_val = getattr(event, 'midi_note', getattr(event, 'pitch', 0))
            hz = librosa.midi_to_hz(midi_val) if midi_val else 0
            
            candidates = get_candidates_fn(hz)
            # Low B(5현) 개방현(0, 0)을 Fallback으로 수정하여 배열 크래시 방지
            state_sequence.append(candidates if candidates else [(0, 0)])

        n_steps = len(state_sequence)
        
        dp = [np.zeros(len(states)) for states in state_sequence]
        backpointers = [np.zeros(len(states), dtype=int) for states in state_sequence]

        for t in range(1, n_steps):
            t_curr = getattr(events[t], 'time', getattr(events[t], 'start_time', 0.0))
            t_prev = getattr(events[t-1], 'time', getattr(events[t-1], 'start_time', 0.0))
            dt = t_curr - t_prev
            
            for curr_idx, curr_state in enumerate(state_sequence[t]):
                costs = [dp[t-1][p_idx] + self._calculate_transition_cost(p_state, curr_state, dt)
                         for p_idx, p_state in enumerate(state_sequence[t-1])]
                dp[t][curr_idx] = np.min(costs)
                backpointers[t][curr_idx] = np.argmin(costs)

        curr_idx = int(np.argmin(dp[-1]))
        best_path = [curr_idx]
        for t in range(n_steps - 1, 0, -1):
            curr_idx = backpointers[t][curr_idx]
            best_path.append(curr_idx)
        best_path.reverse()

        for t, event in enumerate(events):
            best_string, best_fret = state_sequence[t][best_path[t]]
            
            if hasattr(event, 'update'):
                try:
                    event.update(string_idx=best_string, fret=best_fret)
                except TypeError:
                    event.update(string=best_string, fret=best_fret)
            else:
                event.string = best_string
                event.fret = best_fret

        return events