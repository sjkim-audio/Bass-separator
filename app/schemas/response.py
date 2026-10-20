from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class TranscriptionMetadata(BaseModel):
    task_id: str
    model_version: str = "demucs-htdemucs-v4.1_crepe-tiny"
    processing_time_ms: float
    
    # [Fix] Pydantic 직렬화 과정에서 증발하는 URL 필드 명시적 복원
    bass_audio_url: Optional[str] = None
    bassless_audio_url: Optional[str] = None
    midi_url: Optional[str] = None

class BassNoteEvent(BaseModel):
    start_time: float
    # 🔴 [핵심 수정] 기본값(0.0)을 제거하고, 양수(gt=0.0) 검증 강제
    duration: float = Field(..., gt=0.0, description="노트의 지속 시간은 0보다 커야 합니다.") 
    midi_note: int
    string_idx: Optional[int] = None
    fret: Optional[int] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0) 

    @field_validator('start_time', 'duration', 'confidence')
    @classmethod
    def round_floats(cls, v: float) -> float:
        return round(v, 3)

class TranscriptionResponse(BaseModel):
    status: str = "SUCCESS"
    bpm: float
    ascii_tab: str
    metadata: TranscriptionMetadata
    events: List[BassNoteEvent]
