from dataclasses import dataclass, replace
from typing import Optional

@dataclass(frozen=True)
class NoteEvent:
    """
    파이프라인 전체를 관통하는 불변(Immutable) 악보 이벤트 모델
    """
    time: float
    midi_note: int  # [Fix] 기본값이 없는 속성을 상단으로 이동
    duration: float = 0.0
    string_idx: Optional[int] = None
    fret: Optional[int] = None
    grid_index: Optional[int] = None
    quantized_time: Optional[float] = None
    quantized_duration: Optional[float] = None
    confidence: float = 1.0

    def update(self, **kwargs) -> 'NoteEvent':
        """기존 객체 상태를 보존하며 변경된 값을 가진 새로운 객체를 반환한다."""
        return replace(self, **kwargs)