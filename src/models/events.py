from dataclasses import dataclass, replace
from typing import Optional

@dataclass(frozen=True)
class NoteEvent:
    """
    파이프라인 전체를 관통하는 단일 진실 공급원(SSOT) 역할의 불변(Immutable) 이벤트 모델.
    양자화, 운지법 할당 등 각 파이프라인 단계를 거칠 때마다 기존 데이터를 100% 보존합니다.
    """
    # 1. 필수 기본 속성 (피치/Onset 추출 단계에서 확정)
    time: float
    midi_note: int
    
    # 2. 선택적 기본 속성
    duration: float = 0.0
    velocity: int = 100               # 렌더링 시 악센트 처리를 대비한 강세 (기본값 100)
    confidence: float = 1.0           # 모델의 피치 추론 신뢰도

    # 3. 양자화(Quantization) 단계에서 채워지는 리듬 속성
    grid_index: Optional[int] = None
    quantized_time: Optional[float] = None
    quantized_duration: Optional[float] = None

    # 4. 운지법(Smart Fingering) 단계에서 채워지는 생체역학 좌표 속성
    string_idx: Optional[int] = None
    fret: Optional[int] = None

    def update(self, **kwargs) -> 'NoteEvent':
        """
        기존 객체의 모든 상태(시간, 양자화, 신뢰도 등)를 원형 그대로 보존하면서,
        인자로 전달받은 속성(예: string_idx=2, fret=5)만 업데이트된 '새로운 불변 객체'를 반환한다.
        """
        return replace(self, **kwargs)
