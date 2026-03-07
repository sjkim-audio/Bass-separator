from pydantic import BaseModel
from typing import List, Optional

class NoteDto(BaseModel):
    time: float
    midi_note: int
    string_idx: Optional[int] = None
    fret: Optional[int] = None
    grid_index: Optional[int] = None
    quantized_time: Optional[float] = None

class TranscriptionResponse(BaseModel):
    status: str = "success"
    bpm: float
    ascii_tab: str
    notes: List[NoteDto]
