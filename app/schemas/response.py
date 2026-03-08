# app/schemas/response.py 
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import time

class TranscriptionMetadata(BaseModel):
    task_id: str
    model_version: str = "demucs-htdemucs-v4.1_crepe-tiny"
    processing_time_ms: float

class BassNoteEvent(BaseModel):
    start_time: float
    duration: float = 0.0 # 향후 Onset-Offset 추적 고도화를 위한 예약 필드
    midi_note: int
    string_idx: Optional[int] = None
    fret: Optional[int] = None
    # CREPE 모델의 예측 신뢰도 (Ghost Note 및 시각화용)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0) 

    @field_validator('start_time', 'duration', 'confidence')
    @classmethod
    def round_floats(cls, v: float) -> float:
        """
        [최적화] 부동소수점 무한 소수 직렬화 방지. 
        밀리초(ms) 해상도인 소수점 3자리까지만 보존하여 페이로드 크기를 최소화한다.
        """
        return round(v, 3)

class TranscriptionResponse(BaseModel):
    status: str = "SUCCESS"
    metadata: TranscriptionMetadata
    events: List[BassNoteEvent]
