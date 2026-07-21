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
        block_span: int = 3,            # [신규] 스케일 블록(손가락 4개)이 커버하는 최대 프렛 거리
        block_discount: float = 0.3,    # [신규] 블록 내 프렛 이동 시 적용될 가중치 (70% 감면)
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
        
        # 1. 동적 시간 가중치
        time_multiplier = (1.0 / safe_dt) + self.base_time_penalty
        
        # 2. 이동 계층 분리 및 비용 산정 (Tier 1, 2, 3)
        cost_f = 0.0
        cost_s = self.w_s * abs(s2 - s1)

        if f1 != 0 and f2 != 0:
            dist_f = abs(f2 - f1)
            dist_s = abs(s2 - s1)
            
            # 기본 수평 거리 비용
            cost_f = self.w_f * dist_f
            
            # [Tier 1] 관용적 폼 (옥타브/5도)
            if (dist_s == 2 and dist_f == 2) or (dist_s == 1 and dist_f == 2):
                cost_s *= 0.3
                cost_f *= 0.5
            
            # [Tier 2] 스케일 블록 내 이동 (손가락만 움직임)
            elif dist_f <= self.block_span:
                cost_f *= self.block_discount  # 수평 이동 페널티 대폭 감면
                cost_s *= 0.8                  # 앵커 고정으로 인한 수직 이동 안정성 반영
            
            # [Tier 3] 포지션 시프트 (손목/팔 이동)
            else:
                if dist_f > self.shift_thresh:
                    cost_f += self.shift_penalty * ((dist_f - self.shift_thresh) ** 1.5)

        # 3. 시간 가중치 결합 (물리적 비대칭성)
        physical_move_cost = (cost_f * time_multiplier) + (cost_s * np.sqrt(time_multiplier))
        
        # 4. 개방현 비행 시간(Flight-time) 모델
        cost_open = 0.0
        if f1 != 0 and f2 == 0:
            cost_open = self.open_penalty
        elif f1 == 0 and f2 != 0:
            flight_urgency = 1.0 / safe_dt
            cost_open = max(0, f2 - 5) * 0.2 * flight_urgency

        # 5. 환경 요인
        cost_height = max(0, f2 - 12) * self.w_high_fret
        cost_stay = -self.w_stay if pos1 == pos2 else 0.0

        return physical_move_cost + cost_open + cost_height + cost_stay
