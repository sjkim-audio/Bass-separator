from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class TranscriptionMetadata(BaseModel):
    task_id: str
    model_version: str = "demucs-htdemucs-v4.1_crepe-tiny"
    processing_time_ms: float

class BassNoteEvent(BaseModel):
    start_time: float
    duration: float = 0.0 
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
    bpm: float            # [Fix] BPM 데이터 누락 복원
    ascii_tab: str        # [Fix] ASCII 타브 악보 누락 복원
    metadata: TranscriptionMetadata
    events: List[BassNoteEvent]
